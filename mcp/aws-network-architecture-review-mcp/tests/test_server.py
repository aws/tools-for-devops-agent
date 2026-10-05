# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""Offline tests for the AWS Network Architecture Review MCP server."""

import asyncio
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import server  # noqa: E402

EXPECTED_TOOLS = {
    "analyze_cloudwan_topology", "analyze_dx_topology", "analyze_tgw_topology",
    "check_dx_resiliency", "get_bgp_status", "get_dx_cloudwatch_metrics",
    "get_dx_gateway_details", "get_dx_vif_details", "get_tgw_route_table_details",
    "get_virtual_gateway_details", "get_vpc_endpoints", "get_vpn_details",
    "network_architecture_summary",
}
SERVICE_PREFIX = {"dx": "directconnect", "ec2": "ec2", "cw": "cloudwatch", "nm": "networkmanager"}


def _called_operations():
    """Every AWS operation the server calls, as IAM action names."""
    code = (SRC / "server.py").read_text()
    ops = set()
    for var, op in re.findall(r"\b(dx|ec2|cw|nm)\.([a-z_]+)\(", code):
        if op == "get_paginator":
            continue
        ops.add(f"{SERVICE_PREFIX[var]}:{op}")
    for var, op in re.findall(r'\b(dx|ec2|cw|nm)\.get_paginator\("([a-z_]+)"\)', code):
        ops.add(f"{SERVICE_PREFIX[var]}:{op}")
    return {f"{svc}:{''.join(w.title() for w in op.split('_'))}" for svc, op in (o.split(":") for o in ops)}


def test_registers_exactly_13_tools():
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS


def test_only_read_operations_are_called():
    for action in _called_operations():
        verb = action.split(":")[1]
        assert re.match(r"^(Describe|List|Get|Search)", verb), action


def test_iam_policy_covers_every_call_and_is_read_only():
    template = (ROOT / "template.yaml").read_text()
    granted = set(re.findall(r"-\s+((?:directconnect|ec2|networkmanager|cloudwatch):[A-Za-z]+)", template))
    assert _called_operations() <= granted, _called_operations() - granted
    for action in granted:
        assert re.match(r"^[a-z0-9]+:(Describe|List|Get|Search)", action), action


def _denied(op):
    return ClientError({"Error": {"Code": "AccessDenied", "Message": f"not authorized: {op}"}}, op)


@pytest.fixture
def clients(monkeypatch):
    dx, ec2, cw, nm = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    dx.describe_connections.return_value = {"connections": [
        {"connectionId": "dxcon-test1", "connectionState": "available", "location": "LOC1"}]}
    dx.describe_virtual_interfaces.return_value = {"virtualInterfaces": []}
    dx.describe_direct_connect_gateways.return_value = {"directConnectGateways": []}
    for method, key in [("describe_transit_gateways", "TransitGateways"),
                        ("describe_vpn_connections", "VpnConnections"),
                        ("describe_vpn_gateways", "VpnGateways"), ("describe_vpcs", "Vpcs")]:
        getattr(ec2, method).return_value = {key: []}
    nm.describe_global_networks.return_value = {"GlobalNetworks": []}
    cw.get_metric_data.return_value = {"MetricDataResults": []}
    cw.get_paginator.return_value.paginate.return_value = [{"MetricAlarms": []}]
    ec2.get_paginator.return_value.paginate.return_value = [{"VpcEndpoints": []}]
    by_service = {"directconnect": dx, "ec2": ec2, "cloudwatch": cw, "networkmanager": nm}
    monkeypatch.setattr(server, "get_client", lambda svc, region="us-east-1": by_service[svc])
    return by_service


def test_summary_success_has_no_data_errors(clients):
    result = json.loads(server.network_architecture_summary("us-east-1"))
    assert result["data_errors"] == []
    missing = result["cloudwatch_alarms"]["missing_recommended"]
    assert {m["missing_alarm"] for m in missing} == {
        "ConnectionState", "ConnectionBpsEgress", "ConnectionBpsIngress", "ConnectionErrorCount"}


def test_summary_reports_unreadable_sources_instead_of_false_findings(clients):
    clients["cloudwatch"].get_metric_data.side_effect = _denied("GetMetricData")
    clients["cloudwatch"].get_paginator.return_value.paginate.side_effect = _denied("DescribeAlarms")
    clients["ec2"].get_paginator.return_value.paginate.side_effect = _denied("DescribeVpcEndpoints")
    clients["networkmanager"].describe_global_networks.side_effect = _denied("DescribeGlobalNetworks")

    result = json.loads(server.network_architecture_summary("us-east-1"))

    alarms = result["cloudwatch_alarms"]
    assert alarms["missing_recommended"] is None
    assert "AccessDenied" in alarms["error"]
    assert "error" in result["dx"]["metrics"][0]
    assert "error" in result["cloud_wan"]
    assert "error" in result["vpc_endpoints"]
    assert sorted(e["source"] for e in result["data_errors"]) == [
        "cloudwatch:DescribeAlarms", "cloudwatch:GetMetricData",
        "ec2:DescribeVpcEndpoints", "networkmanager"]


def test_bgp_health_pct_is_null_without_peers_and_a_percentage_with_peers():
    assert server._analyze_bgp([])["health_pct"] is None
    vifs = [{"virtualInterfaceId": "dxvif-1", "bgpPeers": [{"bgpStatus": "up"}, {"bgpStatus": "down"},
                                                            {"bgpStatus": "up"}, {"bgpStatus": "up"}]}]
    result = server._analyze_bgp(vifs)
    assert result["health_pct"] == 75.0
    assert result["peers_down"] == 1 and result["down_peers"] == [{"vif": "dxvif-1", "status": "down"}]


def test_vpn_and_vgw_read_pascalcase_ec2_fields(clients):
    clients["ec2"].describe_vpn_connections.return_value = {"VpnConnections": [{
        "VpnConnectionId": "vpn-1", "State": "available", "Type": "ipsec.1", "VpnGatewayId": "vgw-1",
        "VgwTelemetry": [
            {"OutsideIpAddress": "192.0.2.1", "Status": "UP", "StatusMessage": "", "AcceptedRouteCount": 7},
            {"OutsideIpAddress": "192.0.2.2", "Status": "DOWN", "StatusMessage": "", "AcceptedRouteCount": 0}],
        "Routes": [{"DestinationCidrBlock": "192.168.50.0/24"}]}]}
    clients["ec2"].describe_vpn_gateways.return_value = {"VpnGateways": [{
        "VpnGatewayId": "vgw-1", "State": "available", "Type": "ipsec.1", "AmazonSideAsn": 64700,
        "VpcAttachments": [{"VpcId": "vpc-1", "State": "attached"}]}]}

    vpn = json.loads(server.get_vpn_details("us-east-1"))
    conn = vpn["vpn_connections"][0]
    assert conn["state"] == "available"
    assert [t["status"] for t in conn["tunnels"]] == ["UP", "DOWN"]
    assert [t["accepted_routes"] for t in conn["tunnels"]] == [7, 0]
    assert conn["static_routes"] == ["192.168.50.0/24"]
    assert (vpn["tunnels_up"], vpn["tunnels_total"]) == (1, 2)

    vgw = json.loads(server.get_virtual_gateway_details("us-east-1"))["virtual_gateways"][0]
    assert vgw["state"] == "available"
    assert vgw["vpc_attachments"] == [{"vpc_id": "vpc-1", "state": "attached"}]


def test_vif_details_reads_camelcase_directconnect_fields(clients):
    clients["directconnect"].describe_virtual_interfaces.return_value = {"virtualInterfaces": [{
        "virtualInterfaceId": "dxvif-1", "virtualInterfaceType": "private", "vlan": 100, "mtu": 8500,
        "asn": 65051, "amazonSideAsn": 64512, "bgpPeers": []}]}
    vif = json.loads(server.get_dx_vif_details("us-east-1"))["virtual_interfaces"][0]
    assert vif["amazon_side_asn"] == 64512 and vif["customer_asn"] == 65051 and vif["mtu"] == 8500


@pytest.mark.parametrize("tool", ["analyze_dx_topology", "check_dx_resiliency", "get_dx_cloudwatch_metrics"])
def test_dx_tools_call_describe_connections_once(clients, tool):
    getattr(server, tool)("us-east-1")
    assert clients["directconnect"].describe_connections.call_count == 1
