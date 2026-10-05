# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AWS Network Architecture Review MCP Server for AWS DevOps Agent.

Read-only assessment of hybrid network architecture using standard AWS SDK
(boto3) control-plane calls only: Direct Connect, Transit Gateway, Site-to-Site
VPN, Virtual Private Gateway, Cloud WAN, VPC endpoints, and DX CloudWatch
metrics and alarms. Provides DX resiliency scoring, architecture-wide
resiliency scoring, and BGP status analysis.

All AWS calls are Describe*/List*/Get* operations made with the Lambda
function's execution role, so the server inspects the account it is deployed
in. No mutating calls are made.

Transport: Streamable HTTP (via Lambda Web Adapter + Function URL, SigV4 auth).
"""

import json
from collections import defaultdict

import boto3
from fastmcp import FastMCP

mcp = FastMCP(
    "aws-network-architecture-review-mcp",
    instructions=(
        "Read-only AWS hybrid network architecture review. For Direct Connect, "
        "Transit Gateway, Site-to-Site VPN, Cloud WAN, and VPC endpoint questions, "
        "prefer these tools over direct AWS API calls: they correlate data across "
        "layers, apply a deterministic resiliency scoring method, and detect "
        "resources shared from other accounts (for example a Transit Gateway whose "
        "route tables only the owner can see). Start with "
        "network_architecture_summary for a whole-region view (DX, TGW, VPN, "
        "VGW, Cloud WAN, VPC endpoints, DX alarms, resiliency score), then use "
        "the focused tools to drill into a layer. All tools take a 'region' "
        "argument and inspect the account the server is deployed in. If a "
        "result includes 'data_errors' or an 'error' field, that data source "
        "could not be read; report it as unavailable rather than as a finding."
    ),
)


def get_client(service: str, region: str = "us-east-1"):
    """Get a boto3 client for the specified service and region."""
    return boto3.client(service, region_name=region)



# ─── Direct Connect Tools ───────────────────────────────────────────────────


@mcp.tool()
def analyze_dx_topology(region: str = "us-east-1") -> str:
    """
    Direct Connect topology review in one call: connections, virtual interfaces, DX
    gateways, BGP peer status, and a scored resiliency assessment. Use instead of
    separate directconnect Describe* calls.

    Args:
        region: AWS region (default us-east-1)
    """
    dx = get_client("directconnect", region)

    connections = dx.describe_connections().get("connections", [])
    vifs = dx.describe_virtual_interfaces().get("virtualInterfaces", [])
    gateways = dx.describe_direct_connect_gateways().get("directConnectGateways", [])

    result = {
        "region": region,
        "summary": {
            "total_connections": len(connections),
            "total_virtual_interfaces": len(vifs),
            "total_dx_gateways": len(gateways),
        },
        "connections": [_format_connection(c) for c in connections],
        "virtual_interfaces": [_format_vif(v) for v in vifs],
        "dx_gateways": [_format_gateway(g) for g in gateways],
        "bgp_status": _analyze_bgp(vifs),
        "resiliency_assessment": _assess_resiliency(connections, vifs, gateways),
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def check_dx_resiliency(region: str = "us-east-1") -> str:
    """
    Scored Direct Connect resiliency assessment (AWS Maximum/High Resiliency model):
    location diversity, connections per location, BGP health, MTU consistency, and
    MACsec, with severity-classified findings. Use for any "is our Direct Connect
    resilient" question rather than judging from raw API output.

    Args:
        region: AWS region (default us-east-1)
    """
    dx = get_client("directconnect", region)

    connections = dx.describe_connections().get("connections", [])
    vifs = dx.describe_virtual_interfaces().get("virtualInterfaces", [])
    gateways = dx.describe_direct_connect_gateways().get("directConnectGateways", [])

    assessment = _assess_resiliency(connections, vifs, gateways)
    return json.dumps(assessment, indent=2, default=str)


@mcp.tool()
def get_bgp_status(region: str = "us-east-1") -> str:
    """
    BGP peer status across all Direct Connect virtual interfaces, with up/down counts
    and the list of down peers. Use instead of reading describe-virtual-interfaces.

    Args:
        region: AWS region (default us-east-1)
    """
    dx = get_client("directconnect", region)
    vifs = dx.describe_virtual_interfaces().get("virtualInterfaces", [])
    bgp = _analyze_bgp(vifs)
    return json.dumps(bgp, indent=2, default=str)


@mcp.tool()
def get_dx_vif_details(region: str = "us-east-1", vif_id: str = "") -> str:
    """
    Detailed Direct Connect virtual interface review: VLAN, MTU, BGP peers, route filter
    prefixes, and the associated DX gateway, for one VIF or all.

    Args:
        region: AWS region (default us-east-1)
        vif_id: Optional specific VIF ID (dxvif-xxx). If empty, returns all VIFs.
    """
    dx = get_client("directconnect", region)

    if vif_id:
        vifs = dx.describe_virtual_interfaces(virtualInterfaceId=vif_id).get("virtualInterfaces", [])
    else:
        vifs = dx.describe_virtual_interfaces().get("virtualInterfaces", [])

    if not vifs:
        return json.dumps({"region": region, "message": "No VIFs found"}, indent=2)

    vifs_detail = []
    for v in vifs:
        vifs_detail.append({
            "vif_id": v.get("virtualInterfaceId"),
            "name": v.get("virtualInterfaceName", ""),
            "type": v.get("virtualInterfaceType"),
            "state": v.get("virtualInterfaceState"),
            "connection_id": v.get("connectionId"),
            "location": v.get("location"),
            "vlan": v.get("vlan"),
            "mtu": v.get("mtu"),
            "jumbo_frame_capable": v.get("jumboFrameCapable", False),
            "amazon_address": v.get("amazonAddress"),
            "customer_address": v.get("customerAddress"),
            "address_family": v.get("addressFamily"),
            "amazon_side_asn": v.get("amazonSideAsn"),
            "customer_asn": v.get("asn"),
            "dx_gateway_id": v.get("directConnectGatewayId"),
            "virtual_gateway_id": v.get("virtualGatewayId"),
            "route_filter_prefixes": [p.get("cidr") for p in v.get("routeFilterPrefixes", [])],
            "bgp_peers": [
                {
                    "asn": p.get("asn"),
                    "address_family": p.get("addressFamily"),
                    "amazon_address": p.get("amazonAddress"),
                    "customer_address": p.get("customerAddress"),
                    "state": p.get("bgpPeerState"),
                    "status": p.get("bgpStatus"),
                }
                for p in v.get("bgpPeers", [])
            ],
        })

    return json.dumps({"region": region, "total_vifs": len(vifs_detail), "virtual_interfaces": vifs_detail}, indent=2, default=str)


@mcp.tool()
def get_dx_gateway_details(region: str = "us-east-1", dx_gateway_id: str = "") -> str:
    """
    Direct Connect gateway review: associated VGWs/TGWs, attached VIFs, and allowed
    prefixes per association, correlated in one call.

    Args:
        region: AWS region (default us-east-1)
        dx_gateway_id: Optional specific DX Gateway ID. If empty, returns all.
    """
    dx = get_client("directconnect", region)

    if dx_gateway_id:
        gateways = dx.describe_direct_connect_gateways(directConnectGatewayId=dx_gateway_id).get("directConnectGateways", [])
    else:
        gateways = dx.describe_direct_connect_gateways().get("directConnectGateways", [])

    if not gateways:
        return json.dumps({"region": region, "message": "No DX Gateways found"}, indent=2)

    gateways_detail = []
    for gw in gateways:
        gw_id = gw.get("directConnectGatewayId")

        associations = dx.describe_direct_connect_gateway_associations(
            directConnectGatewayId=gw_id
        ).get("directConnectGatewayAssociations", [])

        attachments = dx.describe_direct_connect_gateway_attachments(
            directConnectGatewayId=gw_id
        ).get("directConnectGatewayAttachments", [])

        gateways_detail.append({
            "dx_gateway_id": gw_id,
            "name": gw.get("directConnectGatewayName"),
            "state": gw.get("directConnectGatewayState"),
            "amazon_side_asn": gw.get("amazonSideAsn"),
            "owner_account": gw.get("ownerAccount"),
            "associations": [
                {
                    "association_state": a.get("associationState"),
                    "associated_gateway_id": a.get("associatedGateway", {}).get("id"),
                    "associated_gateway_type": a.get("associatedGateway", {}).get("type"),
                    "associated_gateway_region": a.get("associatedGateway", {}).get("region"),
                    "allowed_prefixes": [p.get("cidr") for p in a.get("allowedPrefixesToDirectConnectGateway", [])],
                }
                for a in associations
            ],
            "attachments": [
                {
                    "virtual_interface_id": att.get("virtualInterfaceId"),
                    "virtual_interface_region": att.get("virtualInterfaceRegion"),
                    "attachment_state": att.get("attachmentState"),
                }
                for att in attachments
            ],
        })

    return json.dumps({"region": region, "dx_gateways": gateways_detail}, indent=2, default=str)


# ─── Transit Gateway Tools ──────────────────────────────────────────────────


@mcp.tool()
def analyze_tgw_topology(region: str = "us-east-1") -> str:
    """
    Transit Gateway topology review in one call: TGWs (including owner account for
    RAM-shared TGWs), attachments by type (VPC, VPN, peering, DX gateway), and route
    tables. Use instead of separate ec2 Describe* calls for TGW questions.

    Args:
        region: AWS region (default us-east-1)
    """
    ec2 = get_client("ec2", region)

    tgws = ec2.describe_transit_gateways().get("TransitGateways", [])
    if not tgws:
        return json.dumps({"region": region, "transit_gateways": [], "summary": "No TGWs found"}, indent=2)

    attachments = ec2.describe_transit_gateway_attachments().get("TransitGatewayAttachments", [])
    route_tables = ec2.describe_transit_gateway_route_tables().get("TransitGatewayRouteTables", [])

    result = {
        "region": region,
        "summary": {
            "total_tgws": len(tgws),
            "total_attachments": len(attachments),
            "total_route_tables": len(route_tables),
            "attachments_by_type": _count_by_key(attachments, "ResourceType"),
        },
        "transit_gateways": [
            {
                "id": t.get("TransitGatewayId"),
                "name": _get_name_tag(t.get("Tags", [])),
                "state": t.get("State"),
                "owner_id": t.get("OwnerId"),
                "asn": t.get("Options", {}).get("AmazonSideAsn"),
                "dns_support": t.get("Options", {}).get("DnsSupport"),
                "vpn_ecmp": t.get("Options", {}).get("VpnEcmpSupport"),
                "multicast": t.get("Options", {}).get("MulticastSupport"),
            }
            for t in tgws
        ],
        "attachments": [
            {
                "attachment_id": a.get("TransitGatewayAttachmentId"),
                "name": _get_name_tag(a.get("Tags", [])),
                "resource_type": a.get("ResourceType"),
                "resource_id": a.get("ResourceId"),
                "state": a.get("State"),
                "tgw_id": a.get("TransitGatewayId"),
            }
            for a in attachments
        ],
        "route_tables": [
            {
                "id": rt.get("TransitGatewayRouteTableId"),
                "name": _get_name_tag(rt.get("Tags", [])),
                "tgw_id": rt.get("TransitGatewayId"),
                "default_association": rt.get("DefaultAssociationRouteTable", False),
                "default_propagation": rt.get("DefaultPropagationRouteTable", False),
            }
            for rt in route_tables
        ],
    }
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
def get_tgw_route_table_details(region: str = "us-east-1", tgw_id: str = "") -> str:
    """
    Transit Gateway route table review: associations, propagations, and routes for every
    route table in one call. Detects TGWs shared from another account, whose route
    tables only the owner can see. Use instead of describe-transit-gateway-route-tables.

    Args:
        region: AWS region (default us-east-1)
        tgw_id: Optional TGW ID to filter. If empty, analyzes all TGWs.
    """
    ec2 = get_client("ec2", region)

    filters = [{"Name": "transit-gateway-id", "Values": [tgw_id]}] if tgw_id else []
    rt_list = ec2.describe_transit_gateway_route_tables(
        Filters=filters if filters else []
    ).get("TransitGatewayRouteTables", [])

    if not rt_list:
        # Route tables of a Transit Gateway shared through AWS RAM are visible
        # only in the owning account. Say so explicitly, so "no route tables"
        # is not read as "no Transit Gateway".
        account_id = get_client("sts", region).get_caller_identity()["Account"]
        tgws = ec2.describe_transit_gateways(
            **({"TransitGatewayIds": [tgw_id]} if tgw_id else {})
        ).get("TransitGateways", [])
        shared = [
            {"tgw_id": t.get("TransitGatewayId"), "owner_id": t.get("OwnerId"),
             "name": _get_name_tag(t.get("Tags", []))}
            for t in tgws if t.get("OwnerId") != account_id
        ]
        if shared:
            return json.dumps({
                "region": region,
                "message": (
                    "Transit Gateway(s) exist but are shared from another account through AWS RAM. "
                    "Their route tables, associations, propagations, and routes are visible only in "
                    "the owning account; review them there."
                ),
                "shared_transit_gateways": shared,
            }, indent=2)
        return json.dumps({"region": region, "message": "No TGW route tables found"}, indent=2)

    route_tables_detail = []
    for rt in rt_list:
        rt_id = rt.get("TransitGatewayRouteTableId")

        associations = ec2.get_transit_gateway_route_table_associations(
            TransitGatewayRouteTableId=rt_id
        ).get("Associations", [])

        propagations = ec2.get_transit_gateway_route_table_propagations(
            TransitGatewayRouteTableId=rt_id
        ).get("TransitGatewayRouteTablePropagations", [])

        routes = ec2.search_transit_gateway_routes(
            TransitGatewayRouteTableId=rt_id,
            Filters=[{"Name": "state", "Values": ["active", "blackhole"]}]
        ).get("Routes", [])

        route_tables_detail.append({
            "route_table_id": rt_id,
            "name": _get_name_tag(rt.get("Tags", [])),
            "tgw_id": rt.get("TransitGatewayId"),
            "associations": [
                {"attachment_id": a.get("TransitGatewayAttachmentId"), "resource_type": a.get("ResourceType"), "resource_id": a.get("ResourceId")}
                for a in associations
            ],
            "propagations": [
                {"attachment_id": p.get("TransitGatewayAttachmentId"), "resource_type": p.get("ResourceType"), "resource_id": p.get("ResourceId")}
                for p in propagations
            ],
            "routes": [
                {
                    "cidr": r.get("DestinationCidrBlock"),
                    "type": r.get("Type"),
                    "state": r.get("State"),
                    "attachments": [{"attachment_id": att.get("TransitGatewayAttachmentId"), "resource_type": att.get("ResourceType"), "resource_id": att.get("ResourceId")} for att in r.get("TransitGatewayAttachments", [])],
                }
                for r in routes
            ],
            "summary": {
                "total_associations": len(associations),
                "total_propagations": len(propagations),
                "total_routes": len(routes),
                "blackhole_routes": sum(1 for r in routes if r.get("State") == "blackhole"),
            },
        })

    return json.dumps({"region": region, "route_tables": route_tables_detail}, indent=2, default=str)


@mcp.tool()
def get_virtual_gateway_details(region: str = "us-east-1") -> str:
    """
    Virtual private gateway review: VGWs, Amazon-side ASN, and attached VPCs.

    Args:
        region: AWS region (default us-east-1)
    """
    ec2 = get_client("ec2", region)
    vgws = ec2.describe_vpn_gateways().get("VpnGateways", [])

    if not vgws:
        return json.dumps({"region": region, "message": "No Virtual Gateways found"}, indent=2)

    return json.dumps({
        "region": region,
        "virtual_gateways": [
            {
                "vgw_id": v.get("VpnGatewayId"),
                "name": _get_name_tag(v.get("Tags", [])),
                "state": v.get("State"),
                "type": v.get("Type"),
                "amazon_side_asn": v.get("AmazonSideAsn"),
                "vpc_attachments": [{"vpc_id": a.get("VpcId"), "state": a.get("State")} for a in v.get("VpcAttachments", [])],
            }
            for v in vgws
        ],
    }, indent=2, default=str)


# ─── Cloud WAN Tools ────────────────────────────────────────────────────────


@mcp.tool()
def analyze_cloudwan_topology(region: str = "us-east-1") -> str:
    """
    Cloud WAN topology review in one call: global networks, core networks, attachments
    by type and edge location, and peerings. Use instead of separate networkmanager calls.

    Args:
        region: AWS region (default us-east-1)
    """
    nm = get_client("networkmanager", region)

    global_networks = nm.describe_global_networks().get("GlobalNetworks", [])
    if not global_networks:
        return json.dumps({"region": region, "message": "No Cloud WAN global networks found"}, indent=2)

    core_networks = nm.list_core_networks().get("CoreNetworks", [])
    attachments = nm.list_attachments().get("Attachments", [])
    peerings = nm.list_peerings().get("Peerings", [])

    result = {
        "region": region,
        "summary": {
            "total_global_networks": len(global_networks),
            "total_core_networks": len(core_networks),
            "total_attachments": len(attachments),
            "total_peerings": len(peerings),
            "attachments_by_type": _count_by_key(attachments, "AttachmentType"),
        },
        "global_networks": [{"id": g.get("GlobalNetworkId"), "state": g.get("State"), "description": g.get("Description", "")} for g in global_networks],
        "core_networks": [{"id": cn.get("CoreNetworkId"), "state": cn.get("State"), "description": cn.get("Description", "")} for cn in core_networks],
        "attachments": [
            {
                "attachment_id": a.get("AttachmentId"),
                "core_network_id": a.get("CoreNetworkId"),
                "attachment_type": a.get("AttachmentType"),
                "state": a.get("State"),
                "edge_location": a.get("EdgeLocation"),
                "segment_name": a.get("SegmentName", ""),
            }
            for a in attachments
        ],
        "peerings": [
            {"peering_id": p.get("PeeringId"), "peering_type": p.get("PeeringType"), "state": p.get("State"), "edge_location": p.get("EdgeLocation")}
            for p in peerings
        ],
    }
    return json.dumps(result, indent=2, default=str)


# ─── VPC Endpoints Tool ─────────────────────────────────────────────────────


@mcp.tool()
def get_vpc_endpoints(region: str = "us-east-1") -> str:
    """
    VPC endpoint review: endpoints by type and service, and whether the deployment
    follows a centralized or distributed endpoint pattern.

    Args:
        region: AWS region (default us-east-1)
    """
    ec2 = get_client("ec2", region)
    endpoints = []
    paginator = ec2.get_paginator("describe_vpc_endpoints")
    for page in paginator.paginate():
        endpoints.extend(page.get("VpcEndpoints", []))

    if not endpoints:
        return json.dumps({"region": region, "message": "No VPC endpoints found"}, indent=2)

    by_vpc = defaultdict(int)
    by_type = defaultdict(int)
    entries = []

    for ep in endpoints:
        ep_type = ep.get("VpcEndpointType", "Unknown")
        vpc_id = ep.get("VpcId", "")
        by_type[ep_type] += 1
        by_vpc[vpc_id] += 1
        entries.append({
            "endpoint_id": ep.get("VpcEndpointId"),
            "service": ep.get("ServiceName", "").split(".")[-1],
            "type": ep_type,
            "vpc_id": vpc_id,
            "state": ep.get("State"),
            "private_dns": ep.get("PrivateDnsEnabled", False),
        })

    max_vpc = max(by_vpc, key=by_vpc.get)
    pattern = "centralized" if by_vpc[max_vpc] > len(endpoints) * 0.5 else "distributed"

    return json.dumps({
        "region": region,
        "summary": {"total": len(endpoints), "by_type": dict(by_type), "pattern": pattern},
        "endpoints": entries,
    }, indent=2, default=str)


# ─── VPN Tool ────────────────────────────────────────────────────────────────


@mcp.tool()
def get_vpn_details(region: str = "us-east-1") -> str:
    """
    Site-to-Site VPN review: tunnel status and accepted route count per tunnel, static
    routes, and the attached TGW or VGW for every connection. Use for "do we have a VPN
    backup path" questions.

    Args:
        region: AWS region (default us-east-1)
    """
    ec2 = get_client("ec2", region)
    vpns = ec2.describe_vpn_connections().get("VpnConnections", [])

    if not vpns:
        return json.dumps({"region": region, "message": "No VPN connections found"}, indent=2)

    vpn_details = []
    for v in vpns:
        tunnels = []
        for t in v.get("VgwTelemetry", []):
            tunnels.append({
                "outside_ip": t.get("OutsideIpAddress"),
                "status": t.get("Status"),
                "status_message": t.get("StatusMessage", ""),
                "accepted_routes": t.get("AcceptedRouteCount", 0),
            })

        vpn_details.append({
            "vpn_id": v.get("VpnConnectionId"),
            "state": v.get("State"),
            "type": v.get("Type"),
            "category": v.get("Category"),
            "tgw_id": v.get("TransitGatewayId"),
            "vgw_id": v.get("VpnGatewayId"),
            "customer_gateway_id": v.get("CustomerGatewayId"),
            "customer_gateway_ip": v.get("customerGatewayConfiguration", "")[:0],  # Don't expose config
            "tunnels": tunnels,
            "static_routes": [r.get("DestinationCidrBlock") for r in v.get("Routes", [])],
            "tags": {tag["Key"]: tag["Value"] for tag in v.get("Tags", []) if tag.get("Key")},
        })

    tunnels_up = sum(1 for vpn in vpn_details for t in vpn["tunnels"] if t["status"] == "UP")
    tunnels_total = sum(len(vpn["tunnels"]) for vpn in vpn_details)

    return json.dumps({
        "region": region,
        "total_vpns": len(vpn_details),
        "tunnels_up": tunnels_up,
        "tunnels_total": tunnels_total,
        "vpn_connections": vpn_details,
    }, indent=2, default=str)


# ─── CloudWatch Metrics Tool ────────────────────────────────────────────────


@mcp.tool()
def get_dx_cloudwatch_metrics(region: str = "us-east-1", connection_id: str = "", hours: int = 3) -> str:
    """
    Direct Connect CloudWatch metrics per connection: ingress/egress bandwidth,
    connection state, error counts, and optical light levels over a lookback window.

    Args:
        region: AWS region (default us-east-1)
        connection_id: DX connection ID (dxcon-xxx). If empty, gets metrics for all connections.
        hours: Lookback period in hours (default 3)
    """
    from datetime import datetime, timedelta, timezone

    dx = get_client("directconnect", region)
    cw = get_client("cloudwatch", region)

    # Get connection IDs if not specified
    if connection_id:
        conn_ids = [connection_id]
    else:
        connections = dx.describe_connections().get("connections", [])
        conn_ids = [c["connectionId"] for c in connections if c.get("connectionState") == "available"]

    if not conn_ids:
        return json.dumps({"region": region, "message": "No available DX connections found"}, indent=2)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)
    period = 300  # 5-minute intervals

    metrics_result = []
    for cid in conn_ids:
        dimensions = [{"Name": "ConnectionId", "Value": cid}]

        # Fetch key metrics
        metric_queries = [
            {"id": "ingress", "metric": "ConnectionBpsIngress", "stat": "Average"},
            {"id": "egress", "metric": "ConnectionBpsEgress", "stat": "Average"},
            {"id": "ingress_max", "metric": "ConnectionBpsIngress", "stat": "Maximum"},
            {"id": "egress_max", "metric": "ConnectionBpsEgress", "stat": "Maximum"},
            {"id": "state", "metric": "ConnectionState", "stat": "Minimum"},
            {"id": "errors_in", "metric": "ConnectionErrorCount", "stat": "Sum"},
            {"id": "light_in", "metric": "ConnectionLightLevelRx", "stat": "Average"},
            {"id": "light_out", "metric": "ConnectionLightLevelTx", "stat": "Average"},
        ]

        queries = []
        for i, mq in enumerate(metric_queries):
            queries.append({
                "Id": mq["id"],
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/DX",
                        "MetricName": mq["metric"],
                        "Dimensions": dimensions,
                    },
                    "Period": period,
                    "Stat": mq["stat"],
                },
            })

        try:
            resp = cw.get_metric_data(
                MetricDataQueries=queries,
                StartTime=start_time,
                EndTime=end_time,
            )

            metrics = {}
            for result in resp.get("MetricDataResults", []):
                values = result.get("Values", [])
                if values:
                    metrics[result["Id"]] = {
                        "avg": round(sum(values) / len(values), 2),
                        "max": round(max(values), 2),
                        "min": round(min(values), 2),
                        "datapoints": len(values),
                    }

            # Convert bps to readable
            ingress_avg = metrics.get("ingress", {}).get("avg", 0)
            egress_avg = metrics.get("egress", {}).get("avg", 0)
            ingress_max = metrics.get("ingress_max", {}).get("max", 0)
            egress_max = metrics.get("egress_max", {}).get("max", 0)

            metrics_result.append({
                "connection_id": cid,
                "period_hours": hours,
                "ingress": {
                    "avg_mbps": round(ingress_avg / 1_000_000, 2),
                    "peak_mbps": round(ingress_max / 1_000_000, 2),
                },
                "egress": {
                    "avg_mbps": round(egress_avg / 1_000_000, 2),
                    "peak_mbps": round(egress_max / 1_000_000, 2),
                },
                "connection_state": metrics.get("state", {}).get("min", "N/A"),
                "errors": metrics.get("errors_in", {}).get("avg", 0),
                "light_levels": {
                    "rx_dbm": metrics.get("light_in", {}).get("avg", "N/A"),
                    "tx_dbm": metrics.get("light_out", {}).get("avg", "N/A"),
                },
            })
        except Exception as e:
            metrics_result.append({"connection_id": cid, "error": str(e)})

    return json.dumps({"region": region, "metrics": metrics_result}, indent=2, default=str)


# ─── Architecture Summary Tool ──────────────────────────────────────────────


@mcp.tool()
def network_architecture_summary(region: str = "us-east-1") -> str:
    """
    Start here for any network architecture or resiliency review. One call
    covering Direct Connect, Transit Gateway, Site-to-Site VPN, virtual private
    gateways, Cloud WAN, VPC endpoints, and DX CloudWatch metrics and alarm
    coverage, with an architecture-wide resiliency score and severity-classified
    findings. Sources that could not be read are listed in data_errors.

    Args:
        region: AWS region (default us-east-1)
    """
    from datetime import datetime, timedelta, timezone

    dx = get_client("directconnect", region)
    ec2 = get_client("ec2", region)
    cw = get_client("cloudwatch", region)
    nm = get_client("networkmanager", region)

    # ─── DX Layer ───
    connections = dx.describe_connections().get("connections", [])
    vifs = dx.describe_virtual_interfaces().get("virtualInterfaces", [])
    gateways = dx.describe_direct_connect_gateways().get("directConnectGateways", [])

    # DX Gateway associations
    gw_details = []
    for gw in gateways:
        gw_id = gw.get("directConnectGatewayId")
        assocs = dx.describe_direct_connect_gateway_associations(
            directConnectGatewayId=gw_id
        ).get("directConnectGatewayAssociations", [])
        gw_details.append({
            "id": gw_id,
            "name": gw.get("directConnectGatewayName"),
            "asn": gw.get("amazonSideAsn"),
            "associations": len(assocs),
            "allowed_prefixes": sum(len(a.get("allowedPrefixesToDirectConnectGateway", [])) for a in assocs),
        })

    # Sources that failed are recorded here rather than silently returning empty
    # results, which would otherwise read as real findings (e.g. "no alarms").
    data_errors = []

    # ─── DX CloudWatch Metrics ───
    dx_metrics = []
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=3)
    for conn in connections:
        cid = conn.get("connectionId")
        if conn.get("connectionState") != "available":
            continue
        try:
            resp = cw.get_metric_data(
                MetricDataQueries=[
                    {"Id": "ingress", "MetricStat": {"Metric": {"Namespace": "AWS/DX", "MetricName": "ConnectionBpsIngress", "Dimensions": [{"Name": "ConnectionId", "Value": cid}]}, "Period": 300, "Stat": "Average"}},
                    {"Id": "egress", "MetricStat": {"Metric": {"Namespace": "AWS/DX", "MetricName": "ConnectionBpsEgress", "Dimensions": [{"Name": "ConnectionId", "Value": cid}]}, "Period": 300, "Stat": "Average"}},
                ],
                StartTime=start_time, EndTime=end_time,
            )
            metrics = {}
            for r in resp.get("MetricDataResults", []):
                vals = r.get("Values", [])
                if vals:
                    metrics[r["Id"]] = round(sum(vals) / len(vals) / 1_000_000, 2)
            dx_metrics.append({"connection_id": cid, "avg_ingress_mbps": metrics.get("ingress", 0), "avg_egress_mbps": metrics.get("egress", 0)})
        except Exception as e:
            dx_metrics.append({"connection_id": cid, "error": str(e)})
            data_errors.append({"source": "cloudwatch:GetMetricData", "resource": cid, "error": str(e)})

    # ─── CloudWatch Alarms for DX ───
    all_dx_alarms = []
    try:
        paginator = cw.get_paginator("describe_alarms")
        for page in paginator.paginate():
            for alarm in page.get("MetricAlarms", []):
                if alarm.get("Namespace") == "AWS/DX":
                    all_dx_alarms.append({
                        "name": alarm.get("AlarmName"),
                        "state": alarm.get("StateValue"),
                        "metric": alarm.get("MetricName"),
                        "threshold": alarm.get("Threshold"),
                        "comparison": alarm.get("ComparisonOperator"),
                        "connection_id": next(
                            (d["Value"] for d in alarm.get("Dimensions", []) if d["Name"] == "ConnectionId"), None
                        ),
                    })
    except Exception as e:
        alarms_error = str(e)
        data_errors.append({"source": "cloudwatch:DescribeAlarms", "error": alarms_error})
    else:
        alarms_error = None

    # ─── TGW Layer ───
    tgws = ec2.describe_transit_gateways().get("TransitGateways", [])
    tgw_attachments = ec2.describe_transit_gateway_attachments().get("TransitGatewayAttachments", []) if tgws else []

    tgw_details = []
    for t in tgws:
        tgw_details.append({
            "id": t.get("TransitGatewayId"),
            "name": _get_name_tag(t.get("Tags", [])),
            "asn": t.get("Options", {}).get("AmazonSideAsn"),
            "state": t.get("State"),
        })

    # ─── VPN Layer ───
    vpns = ec2.describe_vpn_connections().get("VpnConnections", [])
    vpn_details = []
    for v in vpns:
        tunnels = v.get("VgwTelemetry", [])
        vpn_details.append({
            "vpn_id": v.get("VpnConnectionId"),
            "name": _get_name_tag(v.get("Tags", [])),
            "state": v.get("State"),
            "tgw_id": v.get("TransitGatewayId"),
            "tunnels_up": sum(1 for t in tunnels if t.get("Status") == "UP"),
            "tunnels_total": len(tunnels),
        })

    # ─── VGW Layer ───
    vgws = ec2.describe_vpn_gateways().get("VpnGateways", [])
    vgw_details = [
        {
            "id": v.get("VpnGatewayId"),
            "name": _get_name_tag(v.get("Tags", [])),
            "asn": v.get("AmazonSideAsn"),
            "attached_vpcs": [a.get("VpcId") for a in v.get("VpcAttachments", []) if a.get("State") == "attached"],
        }
        for v in vgws
    ]

    # ─── Cloud WAN Layer ───
    cloudwan = {}
    try:
        global_networks = nm.describe_global_networks().get("GlobalNetworks", [])
        if global_networks:
            core_networks = nm.list_core_networks().get("CoreNetworks", [])
            cw_attachments = nm.list_attachments().get("Attachments", [])
            cloudwan = {
                "global_networks": len(global_networks),
                "core_networks": len(core_networks),
                "attachments": len(cw_attachments),
                "attachments_by_type": _count_by_key(cw_attachments, "AttachmentType"),
                "edge_locations": list(set(a.get("EdgeLocation", "") for a in cw_attachments)),
            }
    except Exception as e:
        # cloudwan stays {} so pattern detection and scoring are unchanged; the
        # error is reported in the output so "no Cloud WAN" is not assumed.
        cloudwan_error = str(e)
        data_errors.append({"source": "networkmanager", "error": cloudwan_error})
    else:
        cloudwan_error = None

    # ─── VPC Endpoints ───
    endpoints = []
    try:
        paginator = ec2.get_paginator("describe_vpc_endpoints")
        for page in paginator.paginate():
            endpoints.extend(page.get("VpcEndpoints", []))
    except Exception as e:
        endpoints_error = str(e)
        data_errors.append({"source": "ec2:DescribeVpcEndpoints", "error": endpoints_error})
    else:
        endpoints_error = None

    endpoint_summary = {}
    if endpoints:
        by_type = defaultdict(int)
        for ep in endpoints:
            by_type[ep.get("VpcEndpointType", "Unknown")] += 1
        endpoint_summary = {"total": len(endpoints), "by_type": dict(by_type)}

    # ─── VPCs ───
    vpcs = ec2.describe_vpcs().get("Vpcs", [])

    # ─── Detect Pattern ───
    if tgws and connections and cloudwan:
        pattern = "Cloud WAN + TGW + Direct Connect (hybrid multi-region)"
    elif cloudwan:
        pattern = "Cloud WAN with VPC attachments"
    elif tgws and connections:
        pattern = "Hub-spoke via TGW with Direct Connect"
    elif tgws and vpns:
        pattern = "Hub-spoke via TGW with VPN"
    elif connections:
        pattern = "Direct Connect with VGW (no TGW)"
    else:
        pattern = "Standalone VPCs"

    locations = list(set(c.get("location", "") for c in connections))

    result = {
        "region": region,
        "connectivity_pattern": pattern,
        "dx": {
            "connections": [_format_connection(c) for c in connections],
            "virtual_interfaces": [_format_vif(v) for v in vifs],
            "gateways": gw_details,
            "locations": locations,
            "bgp_health": _analyze_bgp(vifs),
            "metrics": dx_metrics,
        },
        "tgw": {
            "transit_gateways": tgw_details,
            "total_attachments": len(tgw_attachments),
            "attachments_by_type": _count_by_key(tgw_attachments, "ResourceType"),
        },
        "vpn": {
            "connections": vpn_details,
            "tunnels_up": sum(v["tunnels_up"] for v in vpn_details),
            "tunnels_total": sum(v["tunnels_total"] for v in vpn_details),
        },
        "vgw": vgw_details,
        "cloud_wan": {"error": cloudwan_error} if cloudwan_error else cloudwan,
        "vpc_endpoints": {"error": endpoints_error} if endpoints_error else endpoint_summary,
        "vpcs": {"total": len(vpcs)},
        "resiliency": _assess_architecture_resiliency(
            connections, vifs, gateways, tgws, tgw_attachments, vpn_details, vgw_details, cloudwan
        ),
        "redundancy": {
            "dx_locations": len(locations),
            "dx_connections": len(connections),
            "vpn_backup": len(vpns) > 0,
            "macsec_capable": any(c.get("macSecCapable") for c in connections),
            "macsec_enabled": any(c.get("macSecKeys") for c in connections),
        },
        "cloudwatch_alarms": {
            # Alarms could not be read: do not report recommended alarms as
            # missing, since their absence was never observed.
            "error": alarms_error,
            "missing_recommended": None,
        } if alarms_error else {
            "total_dx_alarms": len(all_dx_alarms),
            "alarms_in_alarm_state": [a for a in all_dx_alarms if a["state"] == "ALARM"],
            "alarms_in_ok_state": len([a for a in all_dx_alarms if a["state"] == "OK"]),
            "alarms_insufficient_data": len([a for a in all_dx_alarms if a["state"] == "INSUFFICIENT_DATA"]),
            "all_alarms": all_dx_alarms,
            "missing_recommended": _check_missing_alarms(connections, all_dx_alarms),
        },
        "data_errors": data_errors,
    }
    return json.dumps(result, indent=2, default=str)


# ─── Helpers ────────────────────────────────────────────────────────────────


def _format_connection(c):
    return {
        "id": c.get("connectionId"),
        "name": c.get("connectionName", ""),
        "state": c.get("connectionState"),
        "bandwidth": c.get("bandwidth", ""),
        "location": c.get("location", ""),
        "region": c.get("region", ""),
        "partner": c.get("partnerName", ""),
        "lag_id": c.get("lagId"),
        "macsec_capable": c.get("macSecCapable", False),
    }


def _format_vif(v):
    return {
        "id": v.get("virtualInterfaceId"),
        "name": v.get("virtualInterfaceName", ""),
        "type": v.get("virtualInterfaceType"),
        "state": v.get("virtualInterfaceState"),
        "connection_id": v.get("connectionId"),
        "vlan": v.get("vlan"),
        "mtu": v.get("mtu"),
        "dx_gateway_id": v.get("directConnectGatewayId", ""),
        "bgp_peers": [
            {"asn": p.get("asn"), "state": p.get("bgpPeerState"), "status": p.get("bgpStatus")}
            for p in v.get("bgpPeers", [])
        ],
    }


def _format_gateway(gw):
    return {
        "id": gw.get("directConnectGatewayId"),
        "name": gw.get("directConnectGatewayName", ""),
        "state": gw.get("directConnectGatewayState"),
        "asn": gw.get("amazonSideAsn"),
    }


def _analyze_bgp(vifs):
    peers_up = peers_down = peers_total = 0
    issues = []
    for v in vifs:
        for p in v.get("bgpPeers", []):
            peers_total += 1
            if p.get("bgpStatus") == "up":
                peers_up += 1
            else:
                peers_down += 1
                issues.append({"vif": v.get("virtualInterfaceId"), "status": p.get("bgpStatus")})
    return {
        "total_peers": peers_total,
        "peers_up": peers_up,
        "peers_down": peers_down,
        # None (JSON null) when there are no peers: "nothing to measure", not 0% healthy.
        "health_pct": round(peers_up / peers_total * 100, 1) if peers_total > 0 else None,
        "down_peers": issues,
    }


def _assess_resiliency(connections, vifs, gateways):
    findings = []
    score = 100

    locations = [c.get("location", "") for c in connections if c.get("connectionState") == "available"]
    unique_locations = set(locations)

    if not connections:
        return {"resiliency_level": "N/A", "score": 0, "findings": [{"severity": "INFO", "check": "DX Presence", "finding": "No DX connections found."}]}

    # Location diversity
    if len(unique_locations) < 2:
        findings.append({"severity": "CRITICAL", "check": "Location Diversity", "finding": f"All connections in single location: {list(unique_locations)}"})
        score -= 40
    else:
        findings.append({"severity": "OK", "check": "Location Diversity", "finding": f"Connections span {len(unique_locations)} locations"})

    # Redundancy per location
    location_counts = defaultdict(int)
    for c in connections:
        if c.get("connectionState") == "available":
            location_counts[c.get("location", "unknown")] += 1
    for loc, count in location_counts.items():
        if count < 2:
            findings.append({"severity": "HIGH", "check": "Connection Redundancy", "finding": f"Location {loc} has only {count} connection(s)"})
            score -= 15

    # BGP health
    bgp = _analyze_bgp(vifs)
    if bgp["peers_down"] > 0:
        findings.append({"severity": "HIGH", "check": "BGP Health", "finding": f"{bgp['peers_down']}/{bgp['total_peers']} BGP peers DOWN"})
        score -= 10 * bgp["peers_down"]

    # MTU consistency
    mtus = set(v.get("mtu", 1500) for v in vifs)
    if len(mtus) > 1:
        findings.append({"severity": "MEDIUM", "check": "MTU Consistency", "finding": f"Mixed MTU values: {sorted(mtus)}"})
        score -= 5

    # MACsec
    macsec_capable = [c for c in connections if c.get("macSecCapable")]
    macsec_active = [c for c in connections if c.get("macSecKeys")]
    if macsec_capable and not macsec_active:
        findings.append({"severity": "MEDIUM", "check": "MACsec", "finding": f"{len(macsec_capable)} connection(s) MACsec-capable but not enabled"})
        score -= 5

    # Determine level
    if len(unique_locations) >= 2 and all(c >= 2 for c in location_counts.values()):
        level = "HIGH (Maximum Resiliency)"
    elif len(unique_locations) >= 2:
        level = "MEDIUM (High Resiliency)"
    else:
        level = "LOW (Single Location)"

    return {"resiliency_level": level, "score": max(0, score), "findings": findings}


def _assess_architecture_resiliency(connections, vifs, gateways, tgws, tgw_attachments, vpn_details, vgw_details, cloudwan):
    """Comprehensive resiliency assessment across DX, TGW, VPN, Cloud WAN."""
    findings = []
    score = 0
    max_score = 0

    # ─── Direct Connect (40 points max) ───
    if connections:
        max_score += 40
        locations = [c.get("location", "") for c in connections if c.get("connectionState") == "available"]
        unique_locations = set(locations)

        # Location diversity (20 pts)
        if len(unique_locations) >= 2:
            score += 20
            findings.append({"severity": "OK", "check": "DX Location Diversity", "finding": f"Connections span {len(unique_locations)} locations"})
        else:
            findings.append({"severity": "CRITICAL", "check": "DX Location Diversity", "finding": f"All connections in single location: {list(unique_locations)}"})

        # Connection redundancy (10 pts)
        location_counts = defaultdict(int)
        for c in connections:
            if c.get("connectionState") == "available":
                location_counts[c.get("location", "unknown")] += 1
        if all(count >= 2 for count in location_counts.values()):
            score += 10
            findings.append({"severity": "OK", "check": "DX Connection Redundancy", "finding": "All locations have 2+ connections"})
        else:
            single_locs = [loc for loc, count in location_counts.items() if count < 2]
            findings.append({"severity": "HIGH", "check": "DX Connection Redundancy", "finding": f"Single connection at: {single_locs}"})

        # BGP health (10 pts)
        bgp = _analyze_bgp(vifs)
        if bgp["total_peers"] > 0 and bgp["peers_down"] == 0:
            score += 10
            findings.append({"severity": "OK", "check": "BGP Health", "finding": f"All {bgp['total_peers']} BGP peers UP"})
        elif bgp["total_peers"] > 0:
            score += max(0, 10 - (bgp["peers_down"] * 3))
            findings.append({"severity": "HIGH", "check": "BGP Health", "finding": f"{bgp['peers_down']}/{bgp['total_peers']} BGP peers DOWN"})
        else:
            findings.append({"severity": "MEDIUM", "check": "BGP Health", "finding": "No BGP peers configured"})
    else:
        findings.append({"severity": "INFO", "check": "DX Presence", "finding": "No DX connections — DX resiliency not applicable"})

    # ─── Transit Gateway (25 points max) ───
    if tgws:
        max_score += 25

        # TGW exists and available (10 pts)
        available_tgws = [t for t in tgws if t.get("State") == "available" or t.get("state") == "available"]
        if available_tgws:
            score += 10
            findings.append({"severity": "OK", "check": "TGW Availability", "finding": f"{len(available_tgws)} TGW(s) available"})
        else:
            findings.append({"severity": "CRITICAL", "check": "TGW Availability", "finding": "No TGWs in available state"})

        # Multiple attachment types (10 pts) — indicates redundant paths
        attachment_types = set()
        for a in tgw_attachments:
            attachment_types.add(a.get("ResourceType", a.get("resourceType", "")))
        if len(attachment_types) >= 2:
            score += 10
            findings.append({"severity": "OK", "check": "TGW Path Diversity", "finding": f"Multiple attachment types: {list(attachment_types)}"})
        elif len(attachment_types) == 1:
            score += 5
            findings.append({"severity": "MEDIUM", "check": "TGW Path Diversity", "finding": f"Single attachment type only: {list(attachment_types)}"})

        # TGW peering for multi-region (5 pts)
        peering_attachments = [a for a in tgw_attachments if a.get("ResourceType") == "peering" or a.get("resourceType") == "peering"]
        if peering_attachments:
            score += 5
            findings.append({"severity": "OK", "check": "TGW Peering", "finding": f"{len(peering_attachments)} peering attachment(s) for cross-region connectivity"})
    else:
        findings.append({"severity": "INFO", "check": "TGW Presence", "finding": "No Transit Gateways deployed"})

    # ─── VPN Backup (15 points max) ───
    max_score += 15
    if vpn_details:
        tunnels_up = sum(v.get("tunnels_up", 0) for v in vpn_details)
        tunnels_total = sum(v.get("tunnels_total", 0) for v in vpn_details)
        if tunnels_up > 0:
            score += 15
            findings.append({"severity": "OK", "check": "VPN Backup", "finding": f"VPN active: {tunnels_up}/{tunnels_total} tunnels UP"})
        else:
            score += 5  # VPN exists but tunnels down
            findings.append({"severity": "HIGH", "check": "VPN Backup", "finding": f"VPN configured but 0/{tunnels_total} tunnels UP"})
    elif connections:
        # DX exists but no VPN backup
        findings.append({"severity": "MEDIUM", "check": "VPN Backup", "finding": "No VPN backup for DX — single connectivity method"})
    else:
        findings.append({"severity": "INFO", "check": "VPN Backup", "finding": "No VPN connections"})

    # ─── Cloud WAN (20 points max) ───
    if cloudwan and cloudwan.get("core_networks", 0) > 0:
        max_score += 20

        # Cloud WAN active (10 pts)
        score += 10
        findings.append({"severity": "OK", "check": "Cloud WAN", "finding": f"Cloud WAN active: {cloudwan.get('core_networks')} core network(s), {cloudwan.get('attachments', 0)} attachments"})

        # Multi-region edge locations (10 pts)
        edge_locations = cloudwan.get("edge_locations", [])
        if len(edge_locations) >= 2:
            score += 10
            findings.append({"severity": "OK", "check": "Cloud WAN Multi-Region", "finding": f"Edge locations: {edge_locations}"})
        elif len(edge_locations) == 1:
            score += 5
            findings.append({"severity": "MEDIUM", "check": "Cloud WAN Multi-Region", "finding": f"Single edge location: {edge_locations}"})

    # ─── Calculate final score ───
    if max_score == 0:
        # No networking resources at all
        return {
            "resiliency_level": "N/A",
            "score": 0,
            "max_possible_score": 0,
            "score_pct": 0,
            "findings": [{"severity": "INFO", "check": "Architecture", "finding": "No hybrid connectivity resources found (no DX, TGW, or Cloud WAN)"}],
        }

    score_pct = round((score / max_score) * 100)

    if score_pct >= 80:
        level = "HIGH"
    elif score_pct >= 50:
        level = "MEDIUM"
    elif score_pct > 0:
        level = "LOW"
    else:
        level = "CRITICAL"

    return {
        "resiliency_level": level,
        "score": score,
        "max_possible_score": max_score,
        "score_pct": score_pct,
        "findings": findings,
    }


def _check_missing_alarms(connections, existing_alarms):
    """Check if recommended DX alarms exist for each connection."""
    recommended = ["ConnectionState", "ConnectionBpsEgress", "ConnectionBpsIngress", "ConnectionErrorCount"]
    missing = []
    alarm_metrics = {(a["connection_id"], a["metric"]) for a in existing_alarms}

    for conn in connections:
        cid = conn.get("connectionId")
        if not cid:
            continue
        for metric in recommended:
            if (cid, metric) not in alarm_metrics:
                missing.append({"connection_id": cid, "missing_alarm": metric})
    return missing


def _count_by_key(items, key):
    counts = defaultdict(int)
    for item in items:
        counts[item.get(key, "unknown")] += 1
    return dict(counts)


def _get_name_tag(tags):
    for tag in tags:
        if tag.get("Key") == "Name" or tag.get("key") == "Name":
            return tag.get("Value", tag.get("value", ""))
    return ""


# ─── Entry point (Streamable HTTP via Lambda Web Adapter) ───────────────────

from fastmcp.server.middleware import Middleware  # noqa: E402


class _MethodLog(Middleware):
    """Log each MCP method (no arguments or results) to CloudWatch."""

    async def on_message(self, context, call_next):
        tool = ""
        if context.method == "tools/call":
            tool = f" tool={getattr(context.message, 'name', '?')}"
        print(f"mcp method={context.method}{tool}", flush=True)
        return await call_next(context)


mcp.add_middleware(_MethodLog())


class _SessionIdHeader:
    """ASGI middleware: return an Mcp-Session-Id header from a stateless server.

    The server runs stateless (see below), so it creates no MCP session and
    sends no Mcp-Session-Id. Some clients only continue past `initialize` when
    that header is present. This echoes the client's session ID if it sent
    one, or issues a random one, so those clients proceed. The value is never
    used for state: every request is handled independently, on any Lambda
    execution environment.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        import uuid

        incoming = dict(scope.get("headers") or []).get(b"mcp-session-id")
        session_id = incoming or uuid.uuid4().hex.encode()
        method = scope.get("method")

        # A stateless server has no session to terminate, so the SDK answers
        # DELETE with 405; answer it with 200 instead. GET (the optional
        # server-to-client stream) is left to the SDK's 405, which the spec
        # defines as "no stream offered" -- an empty stream that closes at once
        # makes clients reconnect in a tight loop.
        if method == "DELETE":
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"mcp-session-id", session_id), (b"content-length", b"1")]})
            await send({"type": "http.response.body", "body": b"\n"})
            return

        # Lambda Web Adapter in response_stream mode never terminates a response
        # whose body is empty (e.g. the 202 Accepted for notifications): headers
        # arrive, then the chunked body never ends and the client hangs. Give any
        # empty body a single newline so the stream closes. Clients ignore 202
        # bodies.
        state = {"start": None, "sent_body": False}

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers = [h for h in message.get("headers", []) if h[0].lower() != b"mcp-session-id"]
                headers.append((b"mcp-session-id", session_id))
                state["start"] = {**message, "headers": headers}
                return
            if message["type"] == "http.response.body":
                body, more = message.get("body", b""), message.get("more_body", False)
                if state["start"] is not None:
                    start = state["start"]
                    state["start"] = None
                    if not body and not more:
                        hdrs = [h for h in start["headers"] if h[0].lower() != b"content-length"]
                        await send({**start, "headers": hdrs + [(b"content-length", b"1")]})
                        await send({"type": "http.response.body", "body": b"\n"})
                        return
                    await send(start)
                await send(message)
                return
            await send(message)

        await self.app(scope, receive, send_with_header)


def http_transport_options():
    """Streamable HTTP options shared by the Lambda entry point and the tests.

    Stateless: Lambda may route consecutive requests from one client to
    different execution environments, so no request may depend on an
    in-memory MCP session created by another.
    """
    from starlette.middleware import Middleware as AsgiMiddleware

    return {"stateless_http": True, "middleware": [AsgiMiddleware(_SessionIdHeader)]}


if __name__ == "__main__":
    # On Lambda, run.sh starts this process and the Lambda Web Adapter proxies
    # Function URL requests (SigV4-authenticated) to port 8080. Locally, it
    # binds loopback only: this path has no SigV4 boundary in front of it.
    import os

    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("AWS_LWA_PORT", "8080"))
    mcp.run(transport="streamable-http", host=host, port=port, **http_transport_options())
