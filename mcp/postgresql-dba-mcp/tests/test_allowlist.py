"""Tests for PostgreSQL DBA MCP security boundaries and deployment contracts."""

import inspect
import json
import os
import ssl
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

# The server intentionally fails closed at import time. Force deterministic
# values so inherited shell variables cannot change the unit-test contract.
os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["STAGE_NAME"] = "test"
os.environ["SECRET_ARN"] = (
    "arn:aws:secretsmanager:us-west-2:111122223333:secret:test"
)
os.environ["ALLOWED_INSTANCES"] = "test-db-1,test-db-2"
os.environ["ALLOWED_DATABASES"] = "postgres,myapp"
os.environ["ALLOWED_ENDPOINTS"] = (
    "test-db-1.example.rds.amazonaws.com,test-db-2.example.rds.amazonaws.com,"
    "test-cluster.cluster-example.us-west-2.rds.amazonaws.com,"
    "test-cluster.cluster-ro-example.us-west-2.rds.amazonaws.com"
)
os.environ["EXPLAIN_QUERY_ENABLED"] = "true"


class TestQueryAllowlist:
    """Verify that the predefined diagnostic catalog is complete and read-only."""

    def test_all_categories_present(self):
        from server import QUERY_ALLOWLIST

        assert set(QUERY_ALLOWLIST) == {str(number) for number in range(1, 12)}

    def test_each_query_has_required_fields(self):
        from server import QUERY_ALLOWLIST

        for category_number, category in QUERY_ALLOWLIST.items():
            assert category.get("_category"), f"Category {category_number} missing metadata"
            for query_id, definition in category.items():
                if query_id.startswith("_"):
                    continue
                assert definition.get("name"), f"Query {query_id} missing name"
                assert definition.get("sql"), f"Query {query_id} missing SQL"

    def test_no_mutating_statement_starts_allowlisted_sql(self):
        from server import QUERY_ALLOWLIST

        blocked = {
            "ALTER", "CALL", "COPY", "CREATE", "DELETE", "DO", "DROP", "GRANT",
            "INSERT", "MERGE", "REVOKE", "TRUNCATE", "UPDATE", "VACUUM",
        }
        for category in QUERY_ALLOWLIST.values():
            for query_id, definition in category.items():
                if query_id.startswith("_"):
                    continue
                first_token = definition["sql"].lstrip().split(maxsplit=1)[0].upper()
                assert first_token not in blocked, f"Query {query_id} starts with {first_token}"

    def test_query_count_is_exact(self):
        from server import QUERY_ALLOWLIST

        total = sum(
            1
            for category in QUERY_ALLOWLIST.values()
            for query_id in category
            if not query_id.startswith("_")
        )
        assert total == 55


class TestValidation:
    """Verify explicit instance, database, and endpoint boundaries."""

    def test_validate_instance_database_and_endpoint(self):
        from server import validate_database, validate_endpoint, validate_instance

        assert validate_instance("test-db-1") == (True, "")
        assert validate_database("postgres") == (True, "")
        assert validate_endpoint("TEST-DB-1.EXAMPLE.RDS.AMAZONAWS.COM") == (True, "")
        assert validate_instance("unapproved-db")[0] is False
        assert validate_database("sensitive_db")[0] is False
        assert validate_endpoint("attacker.example.com")[0] is False

    def test_missing_or_wildcard_allowlist_fails_closed(self, monkeypatch):
        from server import _enforce_explicit_allowlists

        monkeypatch.setenv("ALLOWED_INSTANCES", "*")
        with pytest.raises(RuntimeError, match="ALLOWED_INSTANCES"):
            _enforce_explicit_allowlists()

    def test_endpoint_is_rejected_before_secret_retrieval(self, monkeypatch):
        import server

        secret_called = False

        def unexpected_secret_call(_):
            nonlocal secret_called
            secret_called = True
            return {"username": "unused", "password": "unused"}

        monkeypatch.setattr(server, "_get_db_credentials", unexpected_secret_call)
        with pytest.raises(ValueError, match="Endpoint"):
            server._get_connection("attacker.example.com", 5432, "postgres", "")
        assert secret_called is False


class TestSecretValidation:
    """Verify one same-Region secret with an exact schema is enforced."""

    class FakeSecretsClient:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        def get_secret_value(self, **kwargs):
            self.calls.append(kwargs)
            return self.payload

    def test_accepts_exact_secret_schema(self, monkeypatch):
        import server

        client = self.FakeSecretsClient(
            {"SecretString": json.dumps({"username": "reader", "password": "value"})}
        )
        monkeypatch.setattr(server, "secretsmanager_client", client)
        credentials = server._get_db_credentials(os.environ["SECRET_ARN"])
        assert credentials == {"username": "reader", "password": "value"}
        assert client.calls == [{"SecretId": os.environ["SECRET_ARN"]}]

    @pytest.mark.parametrize(
        "payload",
        [
            {"SecretBinary": b"ignored"},
            {"SecretString": "not-json"},
            {"SecretString": json.dumps({"username": "reader"})},
            {
                "SecretString": json.dumps(
                    {"username": "reader", "password": "value", "host": "unexpected"}
                )
            },
            {"SecretString": json.dumps({"username": "", "password": "value"})},
        ],
    )
    def test_rejects_invalid_secret_schema(self, monkeypatch, payload):
        import server

        monkeypatch.setattr(server, "secretsmanager_client", self.FakeSecretsClient(payload))
        with pytest.raises(ValueError):
            server._get_db_credentials(os.environ["SECRET_ARN"])

    def test_rejects_different_secret_and_region(self, monkeypatch):
        import server

        client = self.FakeSecretsClient({})
        monkeypatch.setattr(server, "secretsmanager_client", client)
        with pytest.raises(ValueError, match="requested secret"):
            server._get_db_credentials(
                "arn:aws:secretsmanager:us-west-2:111122223333:secret:other"
            )
        monkeypatch.setenv(
            "SECRET_ARN",
            "arn:aws:secretsmanager:us-east-1:111122223333:secret:test",
        )
        with pytest.raises(ValueError, match="same Region"):
            server._get_db_credentials("")
        assert client.calls == []


class TestCABundleIntegrity:
    """Verify CA digest checks remain active with Python optimization enabled."""

    def test_sha_verifier_rejects_mismatch_under_optimization(self, tmp_path):
        bundle = tmp_path / "bundle.pem"
        bundle.write_bytes(b"test CA bundle")
        verifier = REPOSITORY_ROOT / "layers" / "dependencies" / "verify_sha256.py"

        result = subprocess.run(
            [sys.executable, "-O", str(verifier), str(bundle), "0" * 64],
            capture_output=True,
            check=False,
            text=True,
        )

        assert result.returncode != 0
        assert "SHA-256 mismatch" in result.stderr


class TestConnectionSafety:
    """Verify TLS bundle use and explicit read-only transaction ordering."""

    class FakeConnection:
        def __init__(self, transaction_mode="on"):
            self.transaction_mode = transaction_mode
            self.calls = []
            self.closed = False

        def run(self, sql):
            self.calls.append(sql)
            if sql == "SHOW transaction_read_only":
                return [[self.transaction_mode]]
            return []

        def close(self):
            self.closed = True

    def test_connection_uses_ca_and_verified_read_only_transaction(self, monkeypatch, tmp_path):
        import server

        bundle = tmp_path / "rds-global-bundle.pem"
        bundle.write_text("test bundle", encoding="utf-8")
        monkeypatch.setenv("RDS_CA_BUNDLE", str(bundle))
        monkeypatch.setattr(
            server,
            "_get_db_credentials",
            lambda _: {"username": "reader", "password": "value"},
        )

        ca_calls = []
        fake_context = object()
        monkeypatch.setattr(
            ssl,
            "create_default_context",
            lambda *, cafile: ca_calls.append(cafile) or fake_context,
        )
        connection = self.FakeConnection()
        connection_kwargs = []
        monkeypatch.setattr(
            server.pg8000.native,
            "Connection",
            lambda **kwargs: connection_kwargs.append(kwargs) or connection,
        )

        result = server._get_connection(
            "test-db-1.example.rds.amazonaws.com", 5432, "postgres", os.environ["SECRET_ARN"]
        )
        assert result is connection
        assert ca_calls == [str(bundle)]
        assert connection_kwargs[0]["ssl_context"] is fake_context
        assert connection.calls == [
            "BEGIN READ ONLY",
            "SHOW transaction_read_only",
            "SET LOCAL statement_timeout = '60s'",
            "SET LOCAL lock_timeout = '5s'",
            "SET LOCAL idle_in_transaction_session_timeout = '170s'",
        ]

    def test_connection_timeout_never_exceeds_subsecond_deadline(self, monkeypatch, tmp_path):
        import server

        bundle = tmp_path / "rds-global-bundle.pem"
        bundle.write_text("test bundle", encoding="utf-8")
        monkeypatch.setenv("RDS_CA_BUNDLE", str(bundle))
        monkeypatch.setattr(server, "monotonic", lambda: 100.0)
        monkeypatch.setattr(
            server,
            "_get_db_credentials",
            lambda _: {"username": "reader", "password": "value"},
        )
        monkeypatch.setattr(ssl, "create_default_context", lambda *, cafile: object())
        connection = self.FakeConnection()
        connection_kwargs = []
        monkeypatch.setattr(
            server.pg8000.native,
            "Connection",
            lambda **kwargs: connection_kwargs.append(kwargs) or connection,
        )

        server._get_connection(
            "test-db-1.example.rds.amazonaws.com",
            5432,
            "postgres",
            os.environ["SECRET_ARN"],
            deadline=100.5,
        )
        assert connection_kwargs[0]["timeout"] == pytest.approx(0.5)

    def test_connection_deadline_is_rechecked_after_secret_retrieval(self, monkeypatch):
        import server

        times = iter([100.0, 101.0])
        monkeypatch.setattr(server, "monotonic", lambda: next(times))
        monkeypatch.setattr(
            server,
            "_get_db_credentials",
            lambda _: {"username": "reader", "password": "value"},
        )
        database_called = False

        def unexpected_connection(**kwargs):
            nonlocal database_called
            database_called = True
            raise AssertionError("database connection must not start after deadline")

        monkeypatch.setattr(server.pg8000.native, "Connection", unexpected_connection)
        with pytest.raises(TimeoutError, match="credential retrieval"):
            server._get_connection(
                "test-db-1.example.rds.amazonaws.com",
                5432,
                "postgres",
                os.environ["SECRET_ARN"],
                deadline=100.5,
            )
        assert database_called is False

    def test_connection_closes_if_read_only_mode_is_not_active(self, monkeypatch, tmp_path):
        import server

        bundle = tmp_path / "rds-global-bundle.pem"
        bundle.write_text("test bundle", encoding="utf-8")
        monkeypatch.setenv("RDS_CA_BUNDLE", str(bundle))
        monkeypatch.setattr(
            server,
            "_get_db_credentials",
            lambda _: {"username": "reader", "password": "value"},
        )
        monkeypatch.setattr(ssl, "create_default_context", lambda *, cafile: object())
        connection = self.FakeConnection(transaction_mode="off")
        monkeypatch.setattr(server.pg8000.native, "Connection", lambda **kwargs: connection)

        with pytest.raises(RuntimeError, match="read-only transaction"):
            server._get_connection(
                "test-db-1.example.rds.amazonaws.com", 5432, "postgres", ""
            )
        assert connection.closed is True


class TestExplainSafety:
    """Exercise the parsed SQL validator used by explain_query."""

    def test_disabled_explain_returns_before_parse_or_connection(self, monkeypatch):
        import server

        monkeypatch.setenv("EXPLAIN_QUERY_ENABLED", "false")
        monkeypatch.setattr(
            server,
            "_validate_explain_query",
            lambda query: (_ for _ in ()).throw(
                AssertionError("disabled explain must not parse SQL")
            ),
        )
        monkeypatch.setattr(
            server,
            "_get_connection",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("disabled explain must not connect")
            ),
        )

        result = server.explain_query(
            "SELECT public.attacker_view.* FROM public.attacker_view",
            "test-db-1.example.rds.amazonaws.com",
        )

        assert result == "ERROR: explain_query is disabled in this deployment."

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * FROM users",
            "SELECT id FROM users WHERE status = 'active' AND score >= 10",
            "SELECT '-- text containing update is a string' AS note;",
            "WITH recent AS (SELECT 1 AS id) SELECT * FROM recent",
        ],
    )
    def test_allows_single_select(self, query):
        from server import _validate_explain_query

        allowed, message, normalized = _validate_explain_query(query)
        assert allowed is True
        assert message == ""
        assert normalized

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT 1; DELETE FROM users",
            "WITH removed AS (DELETE FROM users RETURNING *) SELECT * FROM removed",
            "SELECT * INTO copied_users FROM users",
            "SELECT * FROM users FOR UPDATE",
            "SELECT set_config('work_mem', '1GB', false)",
            "SELECT public.\"dblink_exec\"('connection', 'DELETE FROM t')",
            "SELECT \"nextval\"('sequence_name')",
            "ANALYZE SELECT * FROM users",
            "COPY users TO STDOUT",
        ],
    )
    def test_rejects_unsafe_input(self, query):
        from server import _validate_explain_query

        allowed, message, normalized = _validate_explain_query(query)
        assert allowed is False
        assert message.startswith("ERROR:")
        assert normalized == ""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT foo()",
            "SELECT public.foo()",
            "SELECT extensions.bar()",
        ],
    )
    def test_rejects_every_function_call(self, query):
        from server import _validate_explain_query

        allowed, message, normalized = _validate_explain_query(query)
        assert allowed is False
        assert "Function call" in message
        assert "not permitted" in message
        assert normalized == ""

    def test_rejects_when_ast_walk_cannot_complete(self, monkeypatch):
        import server

        monkeypatch.setattr(
            server._ExplainSafetyVisitor,
            "inspect",
            lambda self, syntax_tree: (_ for _ in ()).throw(RuntimeError("walk failed")),
        )

        allowed, message, normalized = server._validate_explain_query(
            "SELECT id FROM users WHERE score > 10"
        )
        assert allowed is False
        assert message == "ERROR: Parsed SQL could not be fully inspected."
        assert normalized == ""

    def test_explain_restricts_search_path_before_planning(self, monkeypatch):
        import server

        class Connection:
            def __init__(self):
                self.commands = []
                self.closed = False

            def run(self, sql):
                self.commands.append(sql)
                return []

            def close(self):
                self.closed = True

        connection = Connection()
        executed = []
        monkeypatch.setattr(server, "_get_connection", lambda *args, **kwargs: connection)
        monkeypatch.setattr(
            server,
            "_execute_query",
            lambda conn, sql: executed.append((conn, sql)) or [{"QUERY PLAN": "Seq Scan"}],
        )

        result = server.explain_query(
            "SELECT id FROM users WHERE score >= 10",
            "test-db-1.example.rds.amazonaws.com",
        )

        assert connection.commands == ["SET LOCAL search_path = pg_catalog"]
        assert executed == [
            (
                connection,
                "EXPLAIN (FORMAT TEXT) SELECT id FROM users WHERE score >= 10",
            )
        ]
        assert "Seq Scan" in result
        assert connection.closed is True

    @pytest.mark.parametrize(
        "function_name",
        [
            "dblink_exec",
            "nextval",
            "pg_backup_start",
            "pg_backup_stop",
            "pg_cancel_backend",
            "pg_create_logical_replication_slot",
            "pg_create_physical_replication_slot",
            "pg_create_restore_point",
            "pg_drop_replication_slot",
            "pg_export_snapshot",
            "pg_logical_emit_message",
            "pg_notify",
            "pg_promote",
            "pg_reload_conf",
            "pg_replication_slot_advance",
            "pg_rotate_logfile",
            "pg_start_backup",
            "pg_stat_reset",
            "pg_stat_reset_shared",
            "pg_stat_reset_single_function_counters",
            "pg_stat_reset_single_table_counters",
            "pg_stat_reset_slru",
            "pg_stat_statements_reset",
            "pg_stop_backup",
            "pg_switch_wal",
            "pg_terminate_backend",
            "pg_wal_replay_pause",
            "pg_wal_replay_resume",
            "set_config",
            "setval",
        ],
    )
    def test_rejects_known_side_effecting_builtins(self, function_name):
        from server import _validate_explain_query

        query = f'SELECT pg_catalog."{function_name}"()'
        allowed, message, normalized = _validate_explain_query(query)
        assert allowed is False
        assert function_name in message
        assert normalized == ""

    @pytest.mark.parametrize(
        "query",
        [
            'SELECT pg_catalog."lo_unlink"(1)',
            "SELECT lo_get(1)",
            "SELECT pg_catalog.pg_advisory_lock(1)",
            'SELECT public."pg_advisory_unlock"(1)',
        ],
    )
    def test_rejects_blocked_function_families(self, query):
        from server import _validate_explain_query

        allowed, message, normalized = _validate_explain_query(query)
        assert allowed is False
        assert "not permitted" in message
        assert normalized == ""


class TestControlPlaneFiltering:
    """Verify account-wide RDS responses are filtered before formatting."""

    def test_list_instances_omits_non_allowlisted_identifiers(self, monkeypatch):
        import server

        class Paginator:
            def paginate(self, **kwargs):
                return [
                    {
                        "DBInstances": [
                            {
                                "DBInstanceIdentifier": "test-db-1",
                                "Engine": "postgres",
                                "EngineVersion": "16.1",
                                "DBInstanceClass": "db.t4g.small",
                                "DBInstanceStatus": "available",
                                "Endpoint": {"Address": "test-db-1.example.rds.amazonaws.com"},
                                "MultiAZ": False,
                                "StorageEncrypted": True,
                            },
                            {
                                "DBInstanceIdentifier": "unapproved-db",
                                "Engine": "postgres",
                                "EngineVersion": "16.1",
                                "DBInstanceClass": "db.t4g.small",
                                "DBInstanceStatus": "available",
                                "Endpoint": {"Address": "unapproved.example.com"},
                                "MultiAZ": False,
                                "StorageEncrypted": True,
                            },
                        ]
                    }
                ]

        class RDSClient:
            def get_paginator(self, name):
                assert name == "describe_db_instances"
                return Paginator()

        monkeypatch.setattr(server, "rds_client", RDSClient())
        result = server.list_rds_instances()
        assert "test-db-1" in result
        assert "unapproved-db" not in result
        assert "unapproved.example.com" not in result

    def test_aurora_config_blocks_generic_shared_buffers_percentage(self, monkeypatch):
        import server

        class RDSClient:
            def describe_db_instances(self, **kwargs):
                assert kwargs == {"DBInstanceIdentifier": "test-db-1"}
                return {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "test-db-1",
                            "DBClusterIdentifier": "test-cluster",
                            "Engine": "aurora-postgresql",
                            "EngineVersion": "16.11",
                            "DBInstanceClass": "db.r6g.large",
                            "DBInstanceStatus": "available",
                            "Endpoint": {
                                "Address": "test-db-1.example.rds.amazonaws.com",
                                "Port": 5432,
                            },
                            "DBParameterGroups": [
                                {
                                    "DBParameterGroupName": "aurora-pg16-demo-instance",
                                    "ParameterApplyStatus": "in-sync",
                                }
                            ],
                        }
                    ]
                }

            def describe_db_clusters(self, **kwargs):
                assert kwargs == {"DBClusterIdentifier": "test-cluster"}
                return {
                    "DBClusters": [
                        {
                            "DBClusterIdentifier": "test-cluster",
                            "Endpoint": (
                                "test-cluster.cluster-example.us-west-2.rds.amazonaws.com"
                            ),
                            "ReaderEndpoint": (
                                "test-cluster.cluster-ro-example.us-west-2.rds.amazonaws.com"
                            ),
                            "AvailabilityZones": ["us-west-2a", "us-west-2b", "us-west-2c"],
                            "StorageEncrypted": True,
                            "DeletionProtection": True,
                            "StorageType": "aurora",
                            "BackupRetentionPeriod": 7,
                            "PreferredBackupWindow": "06:00-06:30",
                            "DBClusterParameterGroup": "aurora-pg16-demo-cluster",
                            "DBClusterMembers": [
                                {
                                    "DBInstanceIdentifier": "test-db-1",
                                    "IsClusterWriter": True,
                                    "PromotionTier": 1,
                                },
                                {
                                    "DBInstanceIdentifier": "test-db-2",
                                    "IsClusterWriter": False,
                                    "PromotionTier": 2,
                                },
                            ],
                        }
                    ]
                }

        class EC2Client:
            def describe_instance_types(self, **kwargs):
                assert kwargs == {"InstanceTypes": ["r6g.large"]}
                return {
                    "InstanceTypes": [
                        {"MemoryInfo": {"SizeInMiB": 16384}}
                    ]
                }

        monkeypatch.setattr(server, "rds_client", RDSClient())
        monkeypatch.setattr(server, "ec2_client", EC2Client())

        result = server.get_instance_config("test-db-1")

        assert "| Platform | Aurora PostgreSQL |" in result
        assert "| Advertised Instance Memory | 16.0 GiB |" in result
        assert "| Aurora Cluster | test-cluster |" in result
        assert "| Cluster Role | Writer |" in result
        assert "| Current Writer Instance | test-db-1 |" in result
        assert (
            "| Cluster Writer Endpoint | "
            "test-cluster.cluster-example.us-west-2.rds.amazonaws.com |"
        ) in result
        assert "| Allowlisted Reader Instances | test-db-2 |" in result
        assert (
            "| Aurora Cluster Parameter Group | aurora-pg16-demo-cluster "
            "(attached; values not inspected) |" in result
        )
        assert "| Availability / Multi-AZ | Aurora cluster storage is distributed" in result
        assert "| Storage Encrypted (Aurora DB cluster) | True |" in result
        assert "| Deletion Protection (Aurora DB cluster) | True |" in result
        assert "DBInstance.AllocatedStorage is not current used storage" in result
        assert "| Sizing Status | INSUFFICIENT_EVIDENCE |" in result
        assert "| Exact Engine Default | NOT VERIFIED |" in result
        assert "CLUSTER_PROVENANCE_GATE: UNKNOWN" in result
        assert "ENGINE_DEFAULT_GATE: UNKNOWN" in result
        assert "MEMORY_SIZING_GATE: INSUFFICIENT_EVIDENCE" in result
        assert "INDIRECT_MEMORY_DERIVATION_GATE: PROHIBITED" in result
        assert (
            "SHARED_BUFFERS_RECOMMENDED_POLICY: USE_VERIFIED_AURORA_ENGINE_DEFAULT"
            in result
        )
        assert "do not calculate a page, byte, or GiB target" in result
        assert "Never back-solve DBInstanceClassMemory" in result
        assert "DBInstanceClassMemory" in result
        assert "numeric target remain UNKNOWN" in result
        assert "list_rds_instances(expected_writer_id=<writer-id>)" in server.mcp.instructions
        assert "SHARED_BUFFERS_FINAL_GATE: PASS" in server.mcp.instructions
        assert "CACHE_FIT_GATE remains OBSERVATION_ONLY" in server.mcp.instructions
        assert "INDIRECT_MEMORY_DERIVATION_GATE is PROHIBITED" in server.mcp.instructions
        assert "SHARED_BUFFERS_RECOMMENDED_POLICY is" in server.mcp.instructions
        assert "USE_VERIFIED_AURORA_ENGINE_DEFAULT" in server.mcp.instructions
        assert "perfect BufferCacheHitRatio does not change" in server.mcp.instructions
        assert "Source=system formulas are not user overrides" in server.mcp.instructions
        assert "never call it wasted or unused" in server.mcp.instructions
        assert "effective_cache_size is only a planner assumption" in server.mcp.instructions
        assert "around 75%" not in result
        assert "4.5%" not in result
        assert "around 75%" not in server.mcp.instructions
        assert "4.5%" not in server.mcp.instructions

        platform, guidance = server._platform_parameter_guidance(
            "postgres", "db.r6g.large"
        )
        assert platform == "RDS for PostgreSQL"
        assert "numeric target remains UNKNOWN" in guidance

    def test_aurora_parameter_group_output_fails_closed_on_unknown_scope(
        self, monkeypatch
    ):
        import server

        class Paginator:
            def paginate(self, **kwargs):
                assert kwargs == {
                    "DBParameterGroupName": "default.aurora-postgresql16"
                }
                return [
                    {
                        "Parameters": [
                            {
                                "ParameterName": "shared_buffers",
                                "ParameterValue": "SUM({DBInstanceClassMemory/12038},-50003)",
                                "ApplyType": "static",
                                "Source": "system",
                            }
                        ]
                    }
                ]

        class RDSClient:
            def describe_db_instances(self, **kwargs):
                assert kwargs == {"DBInstanceIdentifier": "test-db-1"}
                return {
                    "DBInstances": [
                        {
                            "Engine": "aurora-postgresql",
                            "DBParameterGroups": [
                                {
                                    "DBParameterGroupName": "default.aurora-postgresql16"
                                }
                            ],
                        }
                    ]
                }

            def get_paginator(self, name):
                assert name == "describe_db_parameters"
                return Paginator()

        monkeypatch.setattr(server, "rds_client", RDSClient())

        result = server.get_parameter_group("test-db-1")
        all_values = server.get_parameter_group("test-db-1", filter_modified=False)

        assert "**DB Instance Parameter Group:**" in result
        assert "Scope: DB_INSTANCE_PARAMETER_GROUP_ONLY" in result
        assert "CLUSTER_PROVENANCE_GATE: UNKNOWN" in result
        assert "ENGINE_DEFAULT_GATE: UNKNOWN" in result
        assert "INDIRECT_MEMORY_DERIVATION_GATE: PROHIBITED" in result
        assert (
            "SHARED_BUFFERS_RECOMMENDED_POLICY: USE_VERIFIED_AURORA_ENGINE_DEFAULT"
            in result
        )
        assert "No AWS Source=user values were returned" in result
        assert "Source=system formulas are not user overrides" in result
        assert "does not prove that every effective live value" in result
        assert "Aurora DB cluster parameter group" in result
        assert "cluster overrides" in result
        assert "remain UNKNOWN" in result
        assert "SUM({DBInstanceClassMemory/12038},-50003)" not in result
        assert "SUM({DBInstanceClassMemory/12038},-50003)" in all_values
        assert "All parameters are at engine defaults" not in result
        assert "AWS Source (DB instance group only)" in all_values

    @pytest.mark.parametrize("family", ["r8gd", "r6gd", "r6id"])
    def test_aurora_optimized_reads_memory_exception(self, family):
        import server

        platform, guidance = server._platform_parameter_guidance(
            "aurora-postgresql", f"db.{family}.large"
        )

        assert platform == "Aurora PostgreSQL"
        assert f"This {family} class uses Aurora Optimized Reads" in guidance
        assert "requires exact engine-family evidence" in guidance
        assert "4.5%" not in guidance

    def test_upgrade_readiness_omits_non_allowlisted_replica_identifiers(
        self, monkeypatch
    ):
        import server

        class RDSClient:
            def describe_db_instances(self, **kwargs):
                assert kwargs == {"DBInstanceIdentifier": "test-db-1"}
                return {
                    "DBInstances": [
                        {
                            "DBInstanceIdentifier": "test-db-1",
                            "Engine": "postgres",
                            "EngineVersion": "15.5",
                            "DBInstanceClass": "db.m6g.large",
                            "MasterUsername": "monitor",
                            "ReadReplicaDBInstanceIdentifiers": [
                                "test-db-2",
                                "unapproved-replica",
                            ],
                            "MultiAZ": False,
                        }
                    ]
                }

            def describe_db_engine_versions(self, **kwargs):
                return {
                    "DBEngineVersions": [
                        {"ValidUpgradeTarget": [{"EngineVersion": "16.4"}]}
                    ]
                }

            def describe_pending_maintenance_actions(self, **kwargs):
                return {"PendingMaintenanceActions": []}

        class CloudWatchClient:
            def get_metric_statistics(self, **kwargs):
                return {"Datapoints": []}

        monkeypatch.setattr(server, "rds_client", RDSClient())
        monkeypatch.setattr(server, "cloudwatch_client", CloudWatchClient())

        result = server.check_upgrade_readiness("test-db-1", 16)

        assert "test-db-2" in result
        assert "unapproved-replica" not in result
        assert "non-allowlisted identifiers omitted" in result


class TestSharedBuffersDeterminism:
    """Lock writer resolution and platform-specific cache evidence behavior."""

    @staticmethod
    def _aurora_cluster():
        return {
            "DBClusterIdentifier": "test-cluster",
            "Endpoint": "test-cluster.cluster-example.us-west-2.rds.amazonaws.com",
            "ReaderEndpoint": (
                "test-cluster.cluster-ro-example.us-west-2.rds.amazonaws.com"
            ),
            "DBClusterMembers": [
                {
                    "DBInstanceIdentifier": "test-db-1",
                    "IsClusterWriter": True,
                    "PromotionTier": 1,
                },
                {
                    "DBInstanceIdentifier": "test-db-2",
                    "IsClusterWriter": False,
                    "PromotionTier": 2,
                },
            ],
        }

    def test_instance_listing_resolves_current_writer_once(self, monkeypatch):
        import server

        instances = [
            {
                "DBInstanceIdentifier": instance_id,
                "DBClusterIdentifier": "test-cluster",
                "Engine": "aurora-postgresql",
                "EngineVersion": "16.11",
                "Endpoint": {"Address": endpoint},
            }
            for instance_id, endpoint in (
                ("test-db-1", "test-db-1.example.rds.amazonaws.com"),
                ("test-db-2", "test-db-2.example.rds.amazonaws.com"),
            )
        ]
        cluster_calls = []

        class Paginator:
            def paginate(self, **kwargs):
                return [{"DBInstances": instances}]

        class RDSClient:
            def get_paginator(self, name):
                assert name == "describe_db_instances"
                return Paginator()

            def describe_db_clusters(self, **kwargs):
                cluster_calls.append(kwargs)
                return {"DBClusters": [self_outer._aurora_cluster()]}

        self_outer = self
        monkeypatch.setattr(server, "rds_client", RDSClient())

        result = server.list_rds_instances()
        final_result = server.list_rds_instances(expected_writer_id="test-db-1")

        assert "| test-db-1 | aurora-postgresql 16.11 | Writer |" in result
        assert "| test-db-2 | aurora-postgresql 16.11 | Reader |" in result
        assert "test-cluster.cluster-example.us-west-2.rds.amazonaws.com" in result
        assert "test-cluster.cluster-ro-example.us-west-2.rds.amazonaws.com" not in result
        assert "Not used; select an allowlisted reader instance endpoint" in result
        assert "SHARED_BUFFERS_FINAL_GATE" not in result
        assert "SHARED_BUFFERS_FINAL_GATE: PASS" in final_result
        assert (
            "REQUIRED_READER_QUESTION: Would you like me to repeat the same "
            "analysis for the allowlisted Aurora readers?"
        ) in final_result
        assert cluster_calls == [
            {"DBClusterIdentifier": "test-cluster"},
            {"DBClusterIdentifier": "test-cluster"},
        ]

    def test_instance_listing_re_resolves_writer_after_failover(self, monkeypatch):
        import server

        instances = [
            {
                "DBInstanceIdentifier": instance_id,
                "DBClusterIdentifier": "test-cluster",
                "Engine": "aurora-postgresql",
                "EngineVersion": "16.11",
                "Endpoint": {"Address": endpoint},
            }
            for instance_id, endpoint in (
                ("test-db-1", "test-db-1.example.rds.amazonaws.com"),
                ("test-db-2", "test-db-2.example.rds.amazonaws.com"),
            )
        ]
        topologies = []
        for writer_id in ("test-db-1", "test-db-2"):
            cluster = self._aurora_cluster()
            for member in cluster["DBClusterMembers"]:
                member["IsClusterWriter"] = (
                    member["DBInstanceIdentifier"] == writer_id
                )
            topologies.append(cluster)

        class Paginator:
            def paginate(self, **kwargs):
                return [{"DBInstances": instances}]

        class RDSClient:
            def get_paginator(self, name):
                return Paginator()

            def describe_db_clusters(self, **kwargs):
                return {"DBClusters": [topologies.pop(0)]}

        monkeypatch.setattr(server, "rds_client", RDSClient())

        before = server.list_rds_instances()
        after = server.list_rds_instances(expected_writer_id="test-db-1")

        assert "| test-db-1 | aurora-postgresql 16.11 | Writer |" in before
        assert "| test-db-2 | aurora-postgresql 16.11 | Writer |" in after
        assert "SHARED_BUFFERS_FINAL_GATE: FAIL" in after
        assert "Discard mixed evidence and restart" in after
        assert "REQUIRED_READER_QUESTION" not in after
        assert topologies == []

    @pytest.mark.parametrize(
        ("engine", "expects_cloudwatch_ratio"),
        [("aurora-postgresql", True), ("postgres", False)],
    )
    def test_metrics_select_cache_evidence_by_platform(
        self, monkeypatch, engine, expects_cloudwatch_ratio
    ):
        import server
        from datetime import datetime, timezone

        class RDSClient:
            def describe_db_instances(self, **kwargs):
                assert kwargs == {"DBInstanceIdentifier": "test-db-1"}
                return {"DBInstances": [{"Engine": engine}]}

        class CloudWatchClient:
            def __init__(self):
                self.calls = []

            def get_metric_statistics(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "Datapoints": [
                        {
                            "Timestamp": datetime(2026, 8, 20, tzinfo=timezone.utc),
                            "Average": 99.25,
                            "Maximum": 99.75,
                        }
                    ]
                }

        cloudwatch = CloudWatchClient()
        monkeypatch.setattr(server, "rds_client", RDSClient())
        monkeypatch.setattr(server, "cloudwatch_client", cloudwatch)

        result = server.get_instance_metrics("test-db-1", period_minutes=60)
        metric_names = [call["MetricName"] for call in cloudwatch.calls]

        assert ("BufferCacheHitRatio" in metric_names) is expects_cloudwatch_ratio
        assert len(metric_names) == (10 if expects_cloudwatch_ratio else 9)
        assert all(call["Namespace"] == "AWS/RDS" for call in cloudwatch.calls)
        assert all(call["Period"] == 300 for call in cloudwatch.calls)
        assert all(
            call["Statistics"] == ["Average", "Minimum", "Maximum"]
            for call in cloudwatch.calls
        )
        assert all(
            call["Dimensions"]
            == [{"Name": "DBInstanceIdentifier", "Value": "test-db-1"}]
            for call in cloudwatch.calls
        )
        assert "CACHE_FIT_GATE: OBSERVATION_ONLY" in result
        assert "MEMORY_SIZING_GATE: INSUFFICIENT_EVIDENCE" in result
        assert "INDIRECT_MEMORY_DERIVATION_GATE: PROHIBITED" in result
        expected_policy = (
            "USE_VERIFIED_AURORA_ENGINE_DEFAULT"
            if engine == "aurora-postgresql"
            else "VERIFY_ENGINE_DEFAULT_AND_WORKLOAD"
        )
        assert f"SHARED_BUFFERS_RECOMMENDED_POLICY: {expected_policy}" in result
        assert "Availability/reclaimability observation only" in result
        assert "do not call it wasted or unused" in result
        assert "Even a 100% observation does not prove" in result
        if expects_cloudwatch_ratio:
            assert (
                "| BufferCacheHitRatio | 99.2% | 99.2% | 99.2% | 99.8% | 1 | "
                "2026-08-20T00:00:00+00:00 |" in result
            )
            assert "required for Aurora" in result
        else:
            assert "BufferCacheHitRatio" not in result.split("| Metric |")[1]
            assert "run allowlisted query 6.3" in result

    def test_query_2_1_separates_live_settings_from_aws_provenance(self):
        import server

        query = server.QUERY_ALLOWLIST["2"]["2.1"]

        assert query["name"] == (
            "Effective Live PostgreSQL Settings (Not AWS Parameter Provenance)"
        )
        assert "source AS pg_settings_source" in query["sql"]
        assert "context AS pg_settings_context" in query["sql"]

    def test_rds_cache_fallback_is_scoped_to_connected_database(self):
        import server

        query = server.QUERY_ALLOWLIST["6"]["6.3"]

        assert query["name"] == "Cache Hit Ratio for Current Database"
        assert "SELECT datname" in query["sql"]
        assert "100.0 * blks_hit" in query["sql"]
        assert "NULLIF(blks_hit + blks_read, 0)" in query["sql"]
        assert "datname = current_database()" in query["sql"]
        assert "AND blks_hit + blks_read > 0" in query["sql"]

    @pytest.mark.parametrize("period_minutes", [0, -1, 50401])
    def test_metrics_reject_invalid_period(self, period_minutes):
        import server

        result = server.get_instance_metrics(
            "test-db-1", period_minutes=period_minutes
        )

        assert result == "ERROR: period_minutes must be between 1 and 50400."


class TestDocumentationContracts:
    """Keep template and server metadata aligned with actual tool schemas."""

    def test_tool_signatures_match_server_instructions(self):
        import server

        topology_parameters = inspect.signature(server.list_rds_instances).parameters
        metrics_parameters = inspect.signature(server.get_instance_metrics).parameters
        parameter_group_parameters = inspect.signature(server.get_parameter_group).parameters
        assert "For RDS PostgreSQL" in server.mcp.instructions
        assert "query 2.1, and query 6.3" in server.mcp.instructions
        assert "REQUIRED_READER_QUESTION" in server.mcp.instructions
        assert set(topology_parameters) == {"expected_writer_id"}
        assert set(metrics_parameters) == {"instance_id", "period_minutes"}
        assert set(parameter_group_parameters) == {"instance_id", "filter_modified"}

    def test_template_contains_runtime_security_contracts(self):
        template = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")
        for required in (
            "ALLOWED_ENDPOINTS",
            "AllowedPattern: '^arn:aws:secretsmanager:",
            "RDS_CA_BUNDLE: /opt/python/rds-global-bundle.pem",
            "EndpointSubnetId",
            "SourceSecurityGroupId: !Ref SecurityGroupId",
            "com.amazonaws.${AWS::Region}.secretsmanager",
            "com.amazonaws.${AWS::Region}.rds",
            "com.amazonaws.${AWS::Region}.ec2",
            "com.amazonaws.${AWS::Region}.monitoring",
            "rds:DescribeDBLogFiles",
            "rds:DescribePendingMaintenanceActions",
            "ec2:AssignPrivateIpAddresses",
            "ec2:UnassignPrivateIpAddresses",
        ):
            assert required in template
        assert template.count("Type: AWS::EC2::VPCEndpoint") == 4
        assert template.count("PrivateDnsEnabled: true") == 4
        assert "cloudwatch:GetMetricData" not in template
        # Client-side HTML delivery: no report S3 bucket, endpoint, or IAM.
        assert "AWS::S3::Bucket" not in template
        assert "s3:PutObject" not in template
        assert "REPORT_PUBLISH_ENABLED" not in template
