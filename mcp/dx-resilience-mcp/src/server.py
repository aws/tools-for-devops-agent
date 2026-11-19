"""dx-resilience-mcp — read-only MCP server for Direct Connect VIF resilience analysis.

Designed exclusively for AWS DevOps Agent (Streamable HTTP + SigV4 via Lambda
Function URL). All tools are non-mutative: the only AWS calls made are
directconnect Describe*/List*/Get* operations.

Tools:
  get_dx_topology          — joined view: connections, resiliency groups, VIFs, gateways
  analyze_vif_resilience   — fetch routes for a redundant VIF set (both directions)
                             and run deterministic CIDR coverage analysis
  compare_prefix_sets      — pure coverage math on caller-supplied prefix lists
"""

from __future__ import annotations

import os
import time
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError
from fastmcp import FastMCP

from coverage_engine import analyse

mcp = FastMCP("dx-resilience-mcp")

_ROUTE_PAGE_SIZE = 100

# Cross-account support: when TARGET_ROLE_ARN is set (fixed at deploy time —
# never taken from tool input, so the agent cannot redirect the server at an
# arbitrary role), all Direct Connect calls are made with credentials assumed
# from that role. Typical use: DX lives in a dedicated network account while
# this server runs in the ops account hosting the Agent Space.
_TARGET_ROLE_ARN = os.environ.get("TARGET_ROLE_ARN", "").strip()
# DX APIs are regional and DX estates commonly span regions (a resilient
# setup often terminates in two locations homed to different regions).
# DX_REGIONS lists every region holding DX resources; default = own region.
_DX_REGIONS = [r.strip() for r in os.environ.get("DX_REGIONS", "").split(",") if r.strip()]
_assumed_creds = {"expiry": 0.0, "creds": None}


def _credential_kwargs():
    if not _TARGET_ROLE_ARN:
        return {}
    # Reuse cached temporary credentials across warm invocations; refresh
    # 5 minutes before expiry.
    if time.time() > _assumed_creds["expiry"] - 300:
        resp = boto3.client("sts").assume_role(
            RoleArn=_TARGET_ROLE_ARN,
            RoleSessionName="dx-resilience-mcp",
        )
        creds = resp["Credentials"]
        _assumed_creds["creds"] = creds
        _assumed_creds["expiry"] = creds["Expiration"].timestamp()
    creds = _assumed_creds["creds"]
    return {
        "aws_access_key_id": creds["AccessKeyId"],
        "aws_secret_access_key": creds["SecretAccessKey"],
        "aws_session_token": creds["SessionToken"],
    }


def _dx_clients():
    """One directconnect client per configured region (own region if unset)."""
    regions = _DX_REGIONS or [None]
    creds = _credential_kwargs()
    clients = []
    for region in regions:
        kwargs = dict(creds)
        if region:
            kwargs["region_name"] = region
        client = boto3.client("directconnect", **kwargs)
        clients.append((client.meta.region_name, client))
    return clients


# ─── Data collection helpers (all read-only) ─────────────────────────────────

def _describe_vifs(vif_ids: Optional[List[str]] = None) -> List[dict]:
    """VIFs across all configured regions; each dict gains a '_client' key."""
    vifs = []
    for region, client in _dx_clients():
        for v in client.describe_virtual_interfaces()["virtualInterfaces"]:
            v["_client"] = client
            v["_region"] = v.get("region") or region
            vifs.append(v)
    if vif_ids:
        wanted = set(vif_ids)
        vifs = [v for v in vifs if v["virtualInterfaceId"] in wanted]
        missing = wanted - {v["virtualInterfaceId"] for v in vifs}
        if missing:
            regions = [r for r, _ in _dx_clients()]
            raise ValueError(
                f"VIFs not found in this account in regions {regions}: {sorted(missing)}. "
                "If they live in another region, add it to the DX_REGIONS deployment parameter.")
    return vifs


def _vif_summary(v: dict) -> dict:
    return {
        "vif_id": v["virtualInterfaceId"],
        "region": v.get("_region") or v.get("region"),
        "name": v.get("virtualInterfaceName"),
        "type": v.get("virtualInterfaceType"),
        "state": v.get("virtualInterfaceState"),
        "connection_id": v.get("connectionId"),
        "direct_connect_gateway_id": v.get("directConnectGatewayId") or None,
        "virtual_gateway_id": v.get("virtualGatewayId") or None,
        "customer_asn": v.get("asn"),
        "amazon_side_asn": v.get("amazonSideAsn"),
        "aws_logical_device_id": v.get("awsLogicalDeviceId"),
        "location": v.get("location"),
        "bgp_peers": [
            {
                "address_family": p.get("addressFamily"),
                "bgp_status": p.get("bgpStatus"),
                "bgp_peer_state": p.get("bgpPeerState"),
            }
            for p in v.get("bgpPeers", [])
        ],
    }


def _bgp_up(v: dict) -> bool:
    peers = v.get("bgpPeers", [])
    return bool(peers) and any(p.get("bgpStatus") == "up" for p in peers)


def _paginate_items(call, **kwargs) -> List[dict]:
    """Collect every `items` page of a nextToken-paginated DX list call
    (botocore ships no paginators for the resiliency-group operations)."""
    items: List[dict] = []
    token = None
    while True:
        if token:
            kwargs["nextToken"] = token
        resp = call(**kwargs)
        items.extend(resp.get("items", []))
        token = resp.get("nextToken")
        if not token:
            return items


def _connection_id_from_arn(arn: str) -> Optional[str]:
    """arn:aws:directconnect:<region>:<account>:dxcon/dxcon-xxxx -> dxcon-xxxx."""
    if not arn:
        return None
    return arn.rsplit("/", 1)[-1] or None


def _fetch_routes(client, vif_id: str, direction: str) -> List[dict]:
    """Paginate ListVirtualInterfaceRoutes for one VIF and direction."""
    routes: List[dict] = []
    token = None
    while True:
        kwargs = {
            "virtualInterfaceId": vif_id,
            "filters": {"routeDirection": direction},
            "maxResults": _ROUTE_PAGE_SIZE,
        }
        if token:
            kwargs["nextToken"] = token
        resp = client.list_virtual_interface_routes(**kwargs)
        routes.extend(resp.get("routes", []))
        token = resp.get("nextToken")
        if not token:
            return routes


# ─── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_dx_topology() -> dict:
    """Read-only joined view of the Direct Connect estate in this account/region:
    connections (with resiliency-group membership and billing mode), virtual
    interfaces (with gateway attachment, BGP state, device), and resiliency
    groups, aggregated across every configured region (DX_REGIONS).
    Use this to propose redundant VIF sets before analysis.
    """
    conn_view = []
    groups = []
    group_errors = []
    memberships = {}  # connection_id -> resiliency_group_id

    for region, client in _dx_clients():
        connections = client.describe_connections()["connections"]

        try:
            for g in _paginate_items(client.list_resiliency_groups):
                gid = g["resiliencyGroupId"]
                assocs = _paginate_items(client.list_resiliency_group_associations,
                                         resiliencyGroupId=gid)
                # Associations reference connections by ARN, not ID.
                member_ids = [cid for a in assocs
                              if (cid := _connection_id_from_arn(a.get("connectionArn")))]
                for cid in member_ids:
                    memberships[cid] = gid
                groups.append({
                    "resiliency_group_id": gid,
                    "region": region,
                    "name": g.get("resiliencyGroupName"),
                    "type": g.get("resiliencyGroupType"),
                    "state": g.get("state"),
                    "member_connection_ids": member_ids,
                })
        except ClientError as e:
            # Not fatal (pair inference still works), but never silent: an
            # unavailable API and a parse bug must look different in output.
            group_errors.append({
                "region": region,
                "error": e.response.get("Error", {}).get("Code", "ClientError"),
                "note": "Resiliency groups could not be listed in this region; "
                        "group membership is INDETERMINATE here, not absent.",
            })

        conn_view.extend({
            "connection_id": c["connectionId"],
            "region": c.get("region") or region,
            "name": c.get("connectionName"),
            "state": c.get("connectionState"),
            "location": c.get("location"),
            "bandwidth": c.get("bandwidth"),
            "billing_mode": c.get("billingMode"),
            "aws_logical_device_id": c.get("awsLogicalDeviceId"),
            "lag_id": c.get("lagId"),
            "resiliency_group_id": memberships.get(c["connectionId"]),
        } for c in connections)

    vif_views = [_vif_summary(v) for v in _describe_vifs()]

    # Hosted VIFs are owned by this account while their PARENT CONNECTION is
    # owned by the partner/another account — so DescribeConnections returns
    # nothing for them. When we can see VIFs but not their connections, the
    # connection-derived signals (resiliency-group membership, LAG, connection
    # location) are INDETERMINATE, not absent. Say so, rather than implying
    # "no resiliency group". Device and DX location still come from the VIF.
    vif_conn_ids = {v.get("connection_id") for v in vif_views if v.get("connection_id")}
    seen_conn_ids = {c["connection_id"] for c in conn_view}
    invisible_conns = sorted(vif_conn_ids - seen_conn_ids)

    return {
        "regions_scanned": [r for r, _ in _dx_clients()],
        "connections": conn_view,
        "virtual_interfaces": vif_views,
        "resiliency_groups": groups,
        "resiliency_group_errors": group_errors,
        "connection_visibility": {
            "all_vif_connections_visible": not invisible_conns,
            "invisible_connection_ids": invisible_conns,
            "note": ("Some VIFs' parent connections are not owned by this account "
                     "(hosted VIFs / cross-account). Resiliency-group, LAG, and "
                     "connection-location checks are INDETERMINATE for those — not "
                     "'none'. Device and DX-location diversity are still valid "
                     "(read from the VIF).") if invisible_conns else None,
        },
    }


@mcp.tool()
def analyze_vif_resilience(
    vif_ids: List[str],
    directions: Optional[List[str]] = None,
) -> dict:
    """Analyse BGP prefix coverage across a redundant set of Direct Connect VIFs.

    Fetches live routes for each VIF via ListVirtualInterfaceRoutes (paginated,
    inside this server — route tables never enter the model context) and runs
    deterministic CIDR coverage analysis for each requested direction.

    Args:
      vif_ids: 2+ VIF IDs forming one intended redundant set.
      directions: subset of ["accepted", "advertised"]; defaults to both.
        "accepted"   = routes received from the customer network (on-prem -> AWS)
        "advertised" = routes advertised to the customer network (AWS -> on-prem)

    Returns per direction: gaps (no failover coverage), partial_supernet
    (supernet only partly covered by more-specifics — exact uncovered residual
    computed), partial, covered, default-route/empty-table flags, and a
    pairwise "if VIF X fails" view. Also returns BGP health, device-diversity
    check, and which VIFs were excluded (BGP down) and why.
    """
    directions = directions or ["accepted", "advertised"]
    for d in directions:
        if d not in ("accepted", "advertised"):
            raise ValueError(f"Invalid direction '{d}': use 'accepted' or 'advertised'.")
    if len(vif_ids) < 2:
        raise ValueError("Provide at least 2 VIF IDs forming a redundant set.")

    vifs = _describe_vifs(vif_ids)

    health = [_vif_summary(v) for v in vifs]
    excluded = [
        {"vif_id": v["virtualInterfaceId"],
         "reason": "BGP session not up — comparing a stale/empty table against live "
                   "tables produces false positives; VIF excluded from route comparison."}
        for v in vifs if not _bgp_up(v)
    ]
    active = [v for v in vifs if _bgp_up(v)]

    result = {
        "vif_health": health,
        "excluded_vifs": excluded,
        "physical_diversity": _physical_diversity(vifs),
        "analysis": {},
    }

    if len(active) < 2:
        result["analysis_skipped"] = ("Fewer than 2 VIFs with BGP up — coverage "
                                      "comparison not possible. Fix BGP health first.")
        return result

    for direction in directions:
        engine_input = []
        route_counts = {}
        for v in active:
            vid = v["virtualInterfaceId"]
            routes = _fetch_routes(v["_client"], vid, direction)
            route_counts[vid] = len(routes)
            engine_input.append({
                "id": vid,
                "name": v.get("virtualInterfaceName") or vid,
                "prefixes": [r["cidr"] for r in routes if r.get("cidr")],
            })
        report = analyse(direction, engine_input)
        report["route_counts"] = route_counts
        result["analysis"][direction] = report

    return result


@mcp.tool()
def compare_prefix_sets(direction: str, vifs: List[dict]) -> dict:
    """Deterministic CIDR coverage comparison on caller-supplied prefix lists
    (no AWS calls). Use when routes were obtained elsewhere.

    Args:
      direction: label for the report ("accepted" or "advertised").
      vifs: [{"id": str, "name": str, "prefixes": ["10.0.0.0/8", ...]}, ...] (2+ entries)
    """
    return analyse(direction, vifs)


def _physical_diversity(vifs: List[dict]) -> dict:
    """Two independent levels of physical redundancy, both read from the VIF
    object (no connection lookup needed, so this works for hosted/cross-account
    VIFs too):
      - device diversity  : different awsLogicalDeviceId → survives a device fault
      - location diversity : different DX location        → survives a site fault

    A set can be device-diverse yet location-shared (both VIFs at one DX
    location on different devices) — that still fails together on a site event,
    so the two levels are reported separately.
    """
    by_device = {}
    by_location = {}
    for v in vifs:
        by_device.setdefault(v.get("awsLogicalDeviceId") or "unknown", []).append(v["virtualInterfaceId"])
        by_location.setdefault(v.get("location") or "unknown", []).append(v["virtualInterfaceId"])

    shared_device = {d: ids for d, ids in by_device.items() if d != "unknown" and len(ids) > 1}
    known_locs = [loc for loc in by_location if loc != "unknown"]
    location_diverse = len(known_locs) > 1

    warnings = []
    if shared_device:
        warnings.append("Multiple VIFs terminate on the same AWS logical device — "
                        "a device failure takes them down together.")
    if not location_diverse and known_locs:
        warnings.append(f"All VIFs terminate at the same Direct Connect location "
                        f"({known_locs[0]}) — a site-level event (power, cross-connect, "
                        f"local fiber) takes the whole set down regardless of device or "
                        f"prefix diversity.")

    return {
        "device_diverse": not shared_device,
        "location_diverse": location_diverse,
        "vifs_by_device": by_device,
        "vifs_by_location": by_location,
        "warnings": warnings,
    }


# ASGI app served by uvicorn behind the Lambda Web Adapter (Function URL).
# - path="/": bare Function URL works without a 307 redirect (redirects break
#   SigV4-signed requests, which are path-specific).
# - stateless_http=True: each request is self-contained with no server-side
#   session persistence. Required on Lambda — invocations don't share memory,
#   so a session from `initialize` is gone on the next call, surfacing to the
#   client as "Session terminated".
handler = mcp.http_app(path="/", stateless_http=True)

if __name__ == "__main__":
    mcp.run()
