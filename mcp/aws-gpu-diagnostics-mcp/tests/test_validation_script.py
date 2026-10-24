import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import run_reserved_gpu_validation as validation  # noqa: E402


def test_require_state_value_uses_hyphenated_cli_flag():
    arguments = argparse.Namespace(action="resume", instance_id=None)

    try:
        validation.require_state_value(arguments, {}, "instance_id")
    except ValueError as error:
        assert "--instance-id" in str(error)
        assert "--instance_id" not in str(error)
    else:
        raise AssertionError("Expected a missing state value to fail")


def test_main_handles_corrupt_state_file(tmp_path, capsys):
    state_file = tmp_path / "state.json"
    state_file.write_text("{not-json", encoding="utf-8")
    arguments = SimpleNamespace(
        action="resume",
        region="us-west-2",
        reservation_id="cr-0123456789abcdef0",
        image_id="ami-0123456789abcdef0",
        subnet_id="subnet-0123456789abcdef0",
        security_group_id="sg-0123456789abcdef0",
        instance_profile_name="gpu-diagnostics-node",
        stack_name="AwsGpuDiagnosticsMcpStack",
        profile="standard",
        instance_id=None,
        collection_id=None,
        execution_id=None,
        state_file=state_file,
        ssm_timeout_seconds=1,
        approval_timeout_seconds=1,
        poll_seconds=1,
    )
    session = MagicMock()

    with (
        patch.object(validation, "parse_arguments", return_value=arguments),
        patch.object(validation.boto3, "Session", return_value=session),
    ):
        assert validation.main() == 1

    assert "Validation failed:" in capsys.readouterr().err


def test_optional_gpu_features_do_not_fail_collection(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture_dir = tmp_path / "capture"
    nvidia_smi = bin_dir / "nvidia-smi"
    nvidia_smi.write_text(
        """#!/usr/bin/env bash
case "$*" in
  "nvlink -s"|"nvlink -e"|"-q -d ECC"|"-q -d ROW_REMAPPER")
    echo "Feature not supported"
    exit 3
    ;;
  *)
    echo "healthy"
    ;;
esac
""",
        encoding="utf-8",
    )
    nvidia_smi.chmod(0o755)
    timeout = bin_dir / "timeout"
    timeout.write_text(
        """#!/usr/bin/env bash
shift
shift
exec "$@"
""",
        encoding="utf-8",
    )
    timeout.chmod(0o755)
    date = bin_dir / "date"
    date.write_text(
        """#!/usr/bin/env bash
echo "2026-10-24T00:00:00+00:00"
""",
        encoding="utf-8",
    )
    date.chmod(0o755)
    aws = bin_dir / "aws"
    aws.write_text(
        """#!/usr/bin/env bash
mkdir -p "$CAPTURE_DEST"
cp -R "$3"/. "$CAPTURE_DEST"/
""",
        encoding="utf-8",
    )
    aws.chmod(0o755)
    collector = Path(__file__).parents[1] / "collector" / "gpu-diag-collect.sh"
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "CAPTURE_DEST": str(capture_dir),
    }

    subprocess.run(
        [
            "bash",
            str(collector),
            "--bucket",
            "test-bucket",
            "--prefix",
            "collections/i-0123456789abcdef0/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "--region",
            "us-west-2",
            "--profile",
            "standard",
        ],
        check=True,
        env=environment,
        capture_output=True,
        text=True,
    )

    manifest = json.loads((capture_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["collectionComplete"] is True
    assert manifest["failedCaptures"] == []
    assert manifest["unavailableCaptures"] == [
        "nvlink-status",
        "nvlink-errors",
        "ecc-errors",
        "row-remap-state",
    ]
