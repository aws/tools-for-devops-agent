"""Direct-function end-to-end tests against an approved non-production database.

These tests exercise the Python tool functions, TLS verification, the configured
secret, endpoint/database allowlists, and read-only transaction setup. They do
not replace Function URL, SigV4, MCP discovery, or AWS DevOps Agent tests.

Run with:
    RUN_E2E_TESTS=1 \
    AWS_PROFILE=<profile> \
    AWS_REGION=<region> \
    STAGE_NAME=test \
    PG_ENDPOINT=<approved-endpoint> \
    SECRET_ARN=<approved-secret-arn> \
    RDS_CA_BUNDLE=.aws-sam/build/DependenciesLayer/python/rds-global-bundle.pem \
    ALLOWED_ENDPOINTS=<approved-endpoint> \
    ALLOWED_INSTANCES=<approved-instance-id> \
    ALLOWED_DATABASES=postgres \
    PGDATABASE=postgres \
    PGPORT=5432 \
    pytest tests/e2e_test.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _required_environment_is_present() -> bool:
    required = (
        "PG_ENDPOINT",
        "SECRET_ARN",
        "RDS_CA_BUNDLE",
        "ALLOWED_ENDPOINTS",
        "ALLOWED_INSTANCES",
        "ALLOWED_DATABASES",
    )
    return all(os.environ.get(name) for name in required)


@pytest.mark.skipif(
    not os.environ.get("RUN_E2E_TESTS"),
    reason="Set RUN_E2E_TESTS=1 to run end-to-end tests",
)
class TestE2E:
    """Run read-only diagnostics against an explicitly approved target."""

    def test_environment_is_explicit(self):
        assert _required_environment_is_present(), (
            "E2E tests require explicit endpoint, secret, instance, and database allowlists"
        )

    def test_list_health_queries(self):
        from server import list_health_queries

        result = list_health_queries()
        assert result.count("### Category ") == 11
        assert result.count("| 1.") >= 3
        assert "| 11.6 |" in result

    def test_execute_health_query_version(self):
        if not _required_environment_is_present():
            pytest.skip("Explicit E2E environment is incomplete")

        from server import execute_health_query

        result = execute_health_query(
            category="1",
            query_id="1.1",
            instance_endpoint=os.environ["PG_ENDPOINT"],
            database=os.environ.get("PGDATABASE", "postgres"),
            port=int(os.environ.get("PGPORT", "5432")),
            secret_arn=os.environ["SECRET_ARN"],
        )
        assert not result.startswith("ERROR"), result
        assert "PostgreSQL Version" in result
        assert "PostgreSQL" in result

    def test_run_full_health_check(self):
        if not _required_environment_is_present():
            pytest.skip("Explicit E2E environment is incomplete")

        from server import run_full_health_check

        result = run_full_health_check(
            instance_endpoint=os.environ["PG_ENDPOINT"],
            database=os.environ.get("PGDATABASE", "postgres"),
            port=int(os.environ.get("PGPORT", "5432")),
            secret_arn=os.environ["SECRET_ARN"],
            instance_id=os.environ["ALLOWED_INSTANCES"].split(",", 1)[0],
        )
        text = result.content[0].text
        assert result.structured_content["complete"] is True
        assert result.structured_content["represented_section_count"] == 26
        assert "BEGIN_COMPLETE_POSTGRESQL_HEALTH_CHECK_26" in text
        assert "# PostgreSQL Health Check" in text
        assert "### 9. Top 10 Biggest Tables" in text
        assert "### 17. Top 10 Most Bloated Tables" in text
        assert "END_COMPLETE_POSTGRESQL_HEALTH_CHECK_26" in text
