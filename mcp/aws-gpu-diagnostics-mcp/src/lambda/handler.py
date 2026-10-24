"""AWS DevOps Agent Gateway target for GPU diagnostics."""

import json
import logging
import os
import re
import time
import unicodedata
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError


ARTIFACTS_BUCKET = os.environ["ARTIFACTS_BUCKET"]
COLLECTION_DOCUMENT = os.environ["COLLECTION_DOCUMENT"]
ALLOWED_REGIONS = frozenset(filter(None, os.environ["ALLOWED_REGIONS"].split(",")))
TRUSTED_INSTANCE_PROFILE_ARNS = frozenset(
    filter(None, os.environ["TRUSTED_INSTANCE_PROFILE_ARNS"].split(","))
)
REQUIRE_HUMAN_APPROVAL = os.environ.get("REQUIRE_HUMAN_APPROVAL", "false").lower() == "true"
INSTANCE_ID_PATTERN = re.compile(r"^i-[0-9a-f]{8,17}$")
COLLECTION_ID_PATTERN = re.compile(r"^[0-9a-f-]{36}$")
ARTIFACT_KEY_PATTERN = re.compile(
    r"^collections/(i-[0-9a-f]{8,17})/([0-9a-f-]{36})/([A-Za-z0-9][A-Za-z0-9._-]{0,127})$"
)
MAX_READ_BYTES = 262_144
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
ALLOWED_CONTROL_CHARACTERS = frozenset({"\n", "\t"})
LOGGER = logging.getLogger(__name__)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Route the Gateway-selected MCP tool to a bounded implementation."""
    started_at = time.time()
    tool_name = _get_tool_name(context)
    tools = {
        "collect_gpu_diagnostics": collect_gpu_diagnostics,
        "collection_status": collection_status,
        "validate_gpu_bundle": validate_gpu_bundle,
        "get_gpu_findings": get_gpu_findings,
        "read_gpu_artifact": read_gpu_artifact,
    }
    if tool_name not in tools:
        return _error(400, "Unknown tool.", {"availableTools": sorted(tools)})
    if not isinstance(event, dict):
        return _error(400, "Tool arguments must be a JSON object.")

    try:
        response = tools[tool_name](event)
        response["tool"] = tool_name
        response["durationMs"] = round((time.time() - started_at) * 1000)
        return _success(response)
    except ClientError as error:
        LOGGER.exception(
            "AWS service call failed for tool %s: operation=%s code=%s",
            tool_name,
            error.operation_name,
            error.response["Error"].get("Code", "Unknown"),
        )
        return _error(
            502,
            "AWS service call failed.",
            {"code": error.response["Error"].get("Code", "Unknown")},
        )
    except ValueError as error:
        return _error(400, str(error))
    except Exception:
        LOGGER.exception("Unexpected error handling tool %s", tool_name)
        return _error(500, "Unexpected server error.")


def collect_gpu_diagnostics(arguments: dict[str, Any]) -> dict[str, Any]:
    instance_id = _instance_id(arguments.get("instanceId"))
    region = _region(arguments.get("region"))
    profile = arguments.get("profile", "standard")
    if profile not in {"standard", "extended"}:
        raise ValueError("profile must be standard or extended.")

    instance = _get_instance(region, instance_id)
    if instance.get("State", {}).get("Name") != "running":
        raise ValueError("Target instance must be running.")
    profile_arn = instance.get("IamInstanceProfile", {}).get("Arn")
    if profile_arn not in TRUSTED_INSTANCE_PROFILE_ARNS:
        raise ValueError("Target instance does not use a trusted instance profile.")
    tags = {tag.get("Key"): tag.get("Value") for tag in instance.get("Tags", [])}
    if tags.get("DevOpsGpuDiagnostics") != "true":
        raise ValueError("Target instance is not opted in for GPU diagnostics collection.")

    collection_id = str(uuid.uuid4())
    prefix = f"collections/{instance_id}/{collection_id}"
    execution = boto3.client("ssm", region_name=region).start_automation_execution(
        DocumentName=COLLECTION_DOCUMENT,
        Parameters={
            "InstanceId": [instance_id],
            "CollectionPrefix": [prefix],
            "Profile": [profile],
        },
    )
    execution_id = execution["AutomationExecutionId"]
    return {
        "collectionId": collection_id,
        "executionId": execution_id,
        "instanceId": instance_id,
        "region": region,
        "profile": profile,
        "artifactPrefix": prefix,
        "status": "pending_approval" if REQUIRE_HUMAN_APPROVAL else "started",
        "nextAction": (
            "A configured human approver must approve the SSM Automation execution. "
            "Poll collection_status; do not submit another collection."
            if REQUIRE_HUMAN_APPROVAL
            else "Collection started. Poll collection_status; do not submit another collection."
        ),
    }


def collection_status(arguments: dict[str, Any]) -> dict[str, Any]:
    execution_id = _automation_execution_id(arguments.get("executionId"))
    region = _region(arguments.get("region"))
    response = boto3.client("ssm", region_name=region).get_automation_execution(
        AutomationExecutionId=execution_id
    )
    execution = response["AutomationExecution"]
    if execution.get("DocumentName") != COLLECTION_DOCUMENT:
        raise ValueError("executionId does not belong to the GPU diagnostics document.")
    steps = [
        {
            "name": step.get("StepName"),
            "action": step.get("Action"),
            "status": step.get("StepStatus"),
            "failureMessage": step.get("FailureMessage"),
        }
        for step in execution.get("StepExecutions", [])
    ]
    return {
        "executionId": execution_id,
        "region": region,
        "status": execution.get("AutomationExecutionStatus"),
        "currentStep": execution.get("CurrentStepName"),
        "failureMessage": execution.get("FailureMessage"),
        "steps": steps,
    }


def validate_gpu_bundle(arguments: dict[str, Any]) -> dict[str, Any]:
    instance_id = _instance_id(arguments.get("instanceId"))
    collection_id = _collection_id(arguments.get("collectionId"))
    prefix = _collection_prefix(instance_id, collection_id)
    manifest_key = f"{prefix}/manifest.json"
    manifest = _read_json(manifest_key)
    expected = set(manifest.get("expectedFiles", []))
    artifacts = {item["key"] for item in manifest.get("artifacts", [])}
    missing = sorted(expected - {key.rsplit("/", 1)[-1] for key in artifacts})
    return {
        "collectionId": collection_id,
        "instanceId": instance_id,
        "manifestKey": manifest_key,
        "complete": bool(manifest.get("collectionComplete")) and not missing,
        "profile": manifest.get("profile"),
        "artifactCount": len(artifacts),
        "missingExpectedFiles": missing,
        "failedCaptures": manifest.get("failedCaptures", []),
        "unavailableCaptures": manifest.get("unavailableCaptures", []),
        "artifacts": manifest.get("artifacts", []),
    }


def get_gpu_findings(arguments: dict[str, Any]) -> dict[str, Any]:
    instance_id = _instance_id(arguments.get("instanceId"))
    collection_id = _collection_id(arguments.get("collectionId"))
    minimum_severity = arguments.get("severity")
    if minimum_severity and minimum_severity not in SEVERITY_ORDER:
        raise ValueError("severity must be critical, high, medium, low, or info.")

    findings_key = f"{_collection_prefix(instance_id, collection_id)}/findings.json"
    findings = _sanitize_findings(_read_json(findings_key).get("findings", []))
    if minimum_severity:
        threshold = SEVERITY_ORDER[minimum_severity]
        findings = [
            finding
            for finding in findings
            if SEVERITY_ORDER.get(finding.get("severity", "info"), 4) <= threshold
        ]
    return {
        "collectionId": collection_id,
        "instanceId": instance_id,
        "findingsKey": findings_key,
        "findings": findings[:200],
        "returnedCount": min(len(findings), 200),
        "truncated": len(findings) > 200,
    }


def read_gpu_artifact(arguments: dict[str, Any]) -> dict[str, Any]:
    artifact_key = arguments.get("artifactKey")
    if not isinstance(artifact_key, str) or not ARTIFACT_KEY_PATTERN.fullmatch(artifact_key):
        raise ValueError("artifactKey must be an exact text artifact key returned by this server.")
    if artifact_key.endswith((".gz", ".tar", ".tgz")):
        raise ValueError("Compressed artifacts cannot be streamed. Use validate_gpu_bundle to locate them.")
    start_byte = arguments.get("startByte", 0)
    max_bytes = arguments.get("maxBytes", 65_536)
    if not isinstance(start_byte, int) or start_byte < 0:
        raise ValueError("startByte must be a non-negative integer.")
    if not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("maxBytes must be a positive integer.")
    max_bytes = min(max_bytes, MAX_READ_BYTES)

    response = boto3.client("s3").get_object(
        Bucket=ARTIFACTS_BUCKET,
        Key=artifact_key,
        Range=f"bytes={start_byte}-{start_byte + max_bytes - 1}",
    )
    body = response["Body"].read()
    return {
        "artifactKey": artifact_key,
        "startByte": start_byte,
        "bytesReturned": len(body),
        "content": _sanitize_text(body.decode("utf-8", errors="replace"), MAX_READ_BYTES),
        "contentRange": response.get("ContentRange"),
    }


def _get_instance(region: str, instance_id: str) -> dict[str, Any]:
    response = boto3.client("ec2", region_name=region).describe_instances(
        InstanceIds=[instance_id]
    )
    reservations = response.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        raise ValueError("Target instance was not found.")
    return reservations[0]["Instances"][0]


def _read_json(key: str) -> dict[str, Any]:
    try:
        response = boto3.client("s3").get_object(Bucket=ARTIFACTS_BUCKET, Key=key)
    except ClientError as error:
        if error.response["Error"].get("Code") in {"NoSuchKey", "404"}:
            raise ValueError("Collection artifact is not available yet.") from error
        raise
    return json.loads(response["Body"].read().decode("utf-8"))


def _sanitize_findings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sanitized = []
    for finding in value:
        if not isinstance(finding, dict):
            continue
        item = dict(finding)
        evidence = item.get("evidence")
        if isinstance(evidence, str):
            item["evidence"] = _sanitize_text(evidence, 500)
        sanitized.append(item)
    return sanitized


def _sanitize_text(value: str, limit: int) -> str:
    return "".join(
        character for character in value if not _is_control_character(character)
    )[:limit]


def _is_control_character(character: str) -> bool:
    return (
        character not in ALLOWED_CONTROL_CHARACTERS
        and unicodedata.category(character).startswith("C")
    )


def _get_tool_name(context: Any) -> str:
    custom = getattr(getattr(context, "client_context", None), "custom", {}) or {}
    name = custom.get("bedrockAgentCoreToolName", "")
    return name.rsplit("___", 1)[-1]


def _instance_id(value: Any) -> str:
    if not isinstance(value, str) or not INSTANCE_ID_PATTERN.fullmatch(value):
        raise ValueError("instanceId must be a valid EC2 instance ID.")
    return value


def _automation_execution_id(value: Any) -> str:
    if not isinstance(value, str) or not COLLECTION_ID_PATTERN.fullmatch(value):
        raise ValueError("executionId must be a UUID.")
    return value


def _collection_id(value: Any) -> str:
    if not isinstance(value, str) or not COLLECTION_ID_PATTERN.fullmatch(value):
        raise ValueError("collectionId must be a UUID.")
    return value


def _region(value: Any) -> str:
    if not isinstance(value, str) or value not in ALLOWED_REGIONS:
        raise ValueError(f"region must be one of: {', '.join(sorted(ALLOWED_REGIONS))}.")
    return value


def _collection_prefix(instance_id: str, collection_id: str) -> str:
    return f"collections/{instance_id}/{collection_id}"


def _success(data: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": 200, "body": json.dumps({"success": True, **data}, default=str)}


def _error(status_code: int, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"success": False, "error": message}
    if details:
        body["details"] = details
    return {"statusCode": status_code, "body": json.dumps(body)}
