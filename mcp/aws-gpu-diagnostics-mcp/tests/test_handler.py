import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("ARTIFACTS_BUCKET", "test-artifacts")
os.environ.setdefault("COLLECTION_DOCUMENT", "test-document")
os.environ.setdefault("ALLOWED_REGIONS", "us-west-2")
os.environ.setdefault(
    "TRUSTED_INSTANCE_PROFILE_ARNS",
    "arn:aws:iam::123456789012:instance-profile/test-profile",
)
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "lambda"))
import handler  # noqa: E402


def test_collect_requires_trusted_instance_profile():
    ec2 = MagicMock()
    ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"State": {"Name": "running"}}]}]
    }
    with patch.object(handler.boto3, "client", return_value=ec2):
        with pytest.raises(ValueError, match="trusted instance profile"):
            handler.collect_gpu_diagnostics(
                {"instanceId": "i-0123456789abcdef0", "region": "us-west-2"}
            )


def test_collect_starts_automated_collection():
    ec2 = MagicMock()
    ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "State": {"Name": "running"},
                "Tags": [{"Key": "DevOpsGpuDiagnostics", "Value": "true"}],
                "IamInstanceProfile": {
                    "Arn": "arn:aws:iam::123456789012:instance-profile/test-profile"
                },
            }]
        }]
    }
    ssm = MagicMock()
    ssm.start_automation_execution.return_value = {"AutomationExecutionId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}
    with patch.object(handler.boto3, "client", side_effect=[ec2, ssm]):
        response = handler.collect_gpu_diagnostics(
            {"instanceId": "i-0123456789abcdef0", "region": "us-west-2", "profile": "extended"}
        )
    assert response["status"] == "started"
    assert response["profile"] == "extended"
    assert ssm.start_automation_execution.call_args.kwargs["Parameters"]["Profile"] == ["extended"]


def test_collect_requires_diagnostics_opt_in_tag():
    ec2 = MagicMock()
    ec2.describe_instances.return_value = {
        "Reservations": [{
            "Instances": [{
                "State": {"Name": "running"},
                "IamInstanceProfile": {
                    "Arn": "arn:aws:iam::123456789012:instance-profile/test-profile"
                },
            }]
        }]
    }
    with patch.object(handler.boto3, "client", return_value=ec2):
        with pytest.raises(ValueError, match="not opted in"):
            handler.collect_gpu_diagnostics(
                {"instanceId": "i-0123456789abcdef0", "region": "us-west-2"}
            )


def test_gateway_rejects_unknown_tool():
    context = SimpleNamespace(
        client_context=SimpleNamespace(custom={"bedrockAgentCoreToolName": "target___nope"})
    )
    response = handler.lambda_handler({}, context)
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["success"] is False


@pytest.mark.parametrize("key", ["../secret", "collections/i-notvalid/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/test.txt"])
def test_artifact_key_must_match_server_shape(key):
    with pytest.raises(ValueError, match="artifactKey"):
        handler.read_gpu_artifact({"artifactKey": key})
