#!/usr/bin/env python3
"""Launch and validate the GPU diagnostics MCP on a Capacity Block."""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, WaiterError


DEFAULT_STATE_FILE = Path(".gpu-diagnostics-validation-state.json")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("launch", "collect", "resume", "run"),
        help="launch starts the host; collect starts diagnostics; resume completes a pending collection; run performs each step.",
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--reservation-id", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--subnet-id", required=True)
    parser.add_argument("--security-group-id", required=True)
    parser.add_argument("--instance-profile-name", required=True)
    parser.add_argument("--stack-name", default="AwsGpuDiagnosticsMcpStack")
    parser.add_argument("--profile", default="standard", choices=("standard", "extended"))
    parser.add_argument("--instance-id")
    parser.add_argument("--collection-id")
    parser.add_argument("--execution-id")
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument("--ssm-timeout-seconds", type=int, default=900)
    parser.add_argument("--approval-timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=15)
    return parser.parse_args()


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_state_value(arguments: argparse.Namespace, state: dict[str, Any], key: str) -> str:
    state_keys = {
        "instance_id": "instanceId",
        "collection_id": "collectionId",
        "execution_id": "executionId",
    }
    value = getattr(arguments, key) or state.get(state_keys[key])
    if not isinstance(value, str) or not value:
        flag = key.replace("_", "-")
        raise ValueError(
            f"{key} is required for {arguments.action}; supply --{flag} or use the saved state file."
        )
    return value


def wait_for_reservation(ec2: Any, reservation_id: str) -> dict[str, Any]:
    response = ec2.describe_capacity_reservations(CapacityReservationIds=[reservation_id])
    reservation = response["CapacityReservations"][0]
    if reservation.get("ReservationType") != "capacity-block":
        raise ValueError("reservation-id must identify a Capacity Block.")
    if reservation.get("State") != "active":
        raise ValueError(
            f"Capacity Block is {reservation.get('State')}; it must be active before launch."
        )
    return reservation


def launch_instance(arguments: argparse.Namespace, ec2: Any, reservation: dict[str, Any]) -> str:
    subnet = ec2.describe_subnets(SubnetIds=[arguments.subnet_id])["Subnets"][0]
    if subnet["AvailabilityZone"] != reservation["AvailabilityZone"]:
        raise ValueError("subnet and Capacity Block must be in the same Availability Zone.")

    response = ec2.run_instances(
        ImageId=arguments.image_id,
        InstanceType=reservation["InstanceType"],
        MinCount=1,
        MaxCount=1,
        SubnetId=arguments.subnet_id,
        SecurityGroupIds=[arguments.security_group_id],
        IamInstanceProfile={"Name": arguments.instance_profile_name},
        MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled"},
        InstanceMarketOptions={"MarketType": "capacity-block"},
        CapacityReservationSpecification={
            "CapacityReservationTarget": {"CapacityReservationId": reservation["CapacityReservationId"]}
        },
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "aws-gpu-diagnostics-mcp-p6-validation"},
                    {"Key": "DevOpsGpuDiagnostics", "Value": "true"},
                    {"Key": "Purpose", "Value": "pre-merge-mcp-validation"},
                ],
            }
        ],
    )
    return response["Instances"][0]["InstanceId"]


def wait_for_ssm(ssm: Any, instance_id: str, timeout_seconds: int, poll_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        instances = response.get("InstanceInformationList", [])
        if instances and instances[0].get("PingStatus") == "Online":
            return
        time.sleep(poll_seconds)
    raise TimeoutError(f"SSM did not report {instance_id} online within {timeout_seconds} seconds.")


def get_handler_name(cloudformation: Any, stack_name: str) -> str:
    resources = cloudformation.describe_stack_resources(StackName=stack_name)["StackResources"]
    for resource in resources:
        if (
            resource["ResourceType"] == "AWS::Lambda::Function"
            and resource["LogicalResourceId"].startswith("McpHandler")
        ):
            return resource["PhysicalResourceId"]
    raise ValueError(f"Could not find the MCP handler Lambda in stack {stack_name}.")


def invoke_tool(lambda_client: Any, function_name: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    client_context = base64.b64encode(
        json.dumps({"custom": {"bedrockAgentCoreToolName": f"validation___{tool_name}"}}).encode()
    ).decode()
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        ClientContext=client_context,
        Payload=json.dumps(arguments).encode(),
    )
    if response.get("FunctionError"):
        raise RuntimeError(response["Payload"].read().decode())
    payload = json.loads(response["Payload"].read().decode())
    body = json.loads(payload["body"])
    if payload["statusCode"] >= 400 or not body.get("success"):
        raise RuntimeError(json.dumps(body))
    return body


def wait_for_collection(
    lambda_client: Any,
    function_name: str,
    region: str,
    execution_id: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = invoke_tool(
            lambda_client,
            function_name,
            "collection_status",
            {"executionId": execution_id, "region": region},
        )
        print(json.dumps({"status": status["status"], "currentStep": status.get("currentStep")}))
        if status["status"] == "Success":
            return status
        if status["status"] in {"Cancelled", "Failed", "TimedOut"}:
            raise RuntimeError(json.dumps(status))
        time.sleep(poll_seconds)
    raise TimeoutError("Collection did not complete before the approval timeout.")


def validate_collection(
    lambda_client: Any,
    function_name: str,
    instance_id: str,
    collection_id: str,
) -> dict[str, Any]:
    bundle = invoke_tool(
        lambda_client,
        function_name,
        "validate_gpu_bundle",
        {"instanceId": instance_id, "collectionId": collection_id},
    )
    findings = invoke_tool(
        lambda_client,
        function_name,
        "get_gpu_findings",
        {"instanceId": instance_id, "collectionId": collection_id},
    )
    return {"bundle": bundle, "findings": findings}


def main() -> int:
    arguments = parse_arguments()
    try:
        session = boto3.Session(profile_name=None)
        ec2 = session.client("ec2", region_name=arguments.region)
        ssm = session.client("ssm", region_name=arguments.region)
        cloudformation = session.client("cloudformation", region_name=arguments.region)
        lambda_client = session.client("lambda", region_name=arguments.region)
        state = read_state(arguments.state_file)
        state.update({"region": arguments.region, "reservationId": arguments.reservation_id})

        if arguments.action in {"launch", "run"}:
            reservation = wait_for_reservation(ec2, arguments.reservation_id)
            instance_id = launch_instance(arguments, ec2, reservation)
            state["instanceId"] = instance_id
            write_state(arguments.state_file, state)
            print(f"Launched {instance_id}; waiting for SSM.")
            wait_for_ssm(ssm, instance_id, arguments.ssm_timeout_seconds, arguments.poll_seconds)
            print(f"SSM is online for {instance_id}.")

        if arguments.action in {"collect", "run"}:
            instance_id = require_state_value(arguments, state, "instance_id")
            function_name = get_handler_name(cloudformation, arguments.stack_name)
            collection = invoke_tool(
                lambda_client,
                function_name,
                "collect_gpu_diagnostics",
                {"instanceId": instance_id, "region": arguments.region, "profile": arguments.profile},
            )
            state.update(
                {
                    "collectionId": collection["collectionId"],
                    "executionId": collection["executionId"],
                    "instanceId": instance_id,
                }
            )
            write_state(arguments.state_file, state)
            print(
                "Collection started. Use resume only if this invocation stops before "
                "collection completion."
            )
            print(json.dumps({"executionId": collection["executionId"], "collectionId": collection["collectionId"]}))
            if arguments.action == "collect":
                return 0

            wait_for_collection(
                lambda_client,
                function_name,
                arguments.region,
                collection["executionId"],
                arguments.approval_timeout_seconds,
                arguments.poll_seconds,
            )
            result = validate_collection(
                lambda_client,
                function_name,
                instance_id,
                collection["collectionId"],
            )
            state["validationCompleteAt"] = datetime.now(UTC).isoformat()
            write_state(arguments.state_file, state)
            print(json.dumps(result, indent=2))
            return 0

        if arguments.action == "resume":
            instance_id = require_state_value(arguments, state, "instance_id")
            collection_id = require_state_value(arguments, state, "collection_id")
            execution_id = require_state_value(arguments, state, "execution_id")
            function_name = get_handler_name(cloudformation, arguments.stack_name)
            wait_for_collection(
                lambda_client,
                function_name,
                arguments.region,
                execution_id,
                arguments.approval_timeout_seconds,
                arguments.poll_seconds,
            )
            result = validate_collection(
                lambda_client,
                function_name,
                instance_id,
                collection_id,
            )
            state["validationCompleteAt"] = datetime.now(UTC).isoformat()
            write_state(arguments.state_file, state)
            print(json.dumps(result, indent=2))
    except (ClientError, WaiterError, TimeoutError, ValueError, RuntimeError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
