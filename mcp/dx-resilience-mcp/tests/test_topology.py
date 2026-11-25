"""get_dx_topology tests using botocore Stubber — no AWS account or live
Direct Connect required.

Covers the resiliency-group lookup against the real botocore service model
(which validates both request parameters and response shapes), so a drift
between this code and the actual API surfaces here:
  - ListResiliencyGroups / ListResiliencyGroupAssociations return `items`
  - associations reference connections by `connectionArn`, not `connectionId`
  - nextToken pagination on both operations
  - non-hosted VIFs: connection <-> group join works end to end
  - hosted VIFs: membership reported INDETERMINATE, never "no group"
  - listing errors are reported, never silently swallowed

Needs botocore/boto3 (same as the server). fastmcp is not required: when it
is absent a minimal stand-in is injected so the tool functions import as
plain callables.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:  # pragma: no cover - exercised implicitly by the import below
    import fastmcp  # noqa: F401
except ModuleNotFoundError:
    class _FastMCPStub:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self, *args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        def http_app(self, *args, **kwargs):
            return None

        def run(self):
            pass

    _module = types.ModuleType("fastmcp")
    _module.FastMCP = _FastMCPStub
    sys.modules["fastmcp"] = _module

import boto3  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

import server  # noqa: E402

# Real fastmcp wraps the decorated function in a Tool object exposing `.fn`;
# the stub leaves it a plain function. Support both.
get_dx_topology = getattr(server.get_dx_topology, "fn", server.get_dx_topology)

REGION = "eu-west-1"
ACCOUNT = "111122223333"
GROUP_ID = "rg-0123456789abcdef01234"
GROUP_ARN = f"arn:aws:directconnect:{REGION}:{ACCOUNT}:resiliency-group/{GROUP_ID}"


def _conn_arn(conn_id):
    return f"arn:aws:directconnect:{REGION}:{ACCOUNT}:dxcon/{conn_id}"


def _connection(conn_id, device="device-1", location="LOC1"):
    return {
        "connectionId": conn_id,
        "connectionName": f"conn-{conn_id}",
        "connectionState": "available",
        "region": REGION,
        "location": location,
        "bandwidth": "1Gbps",
        "awsLogicalDeviceId": device,
    }


def _vif(vif_id, conn_id, device="device-1", location="LOC1"):
    return {
        "virtualInterfaceId": vif_id,
        "virtualInterfaceName": f"vif-{vif_id}",
        "virtualInterfaceType": "private",
        "virtualInterfaceState": "available",
        "connectionId": conn_id,
        "region": REGION,
        "location": location,
        "awsLogicalDeviceId": device,
        "asn": 65000,
        "amazonSideAsn": 64512,
        "directConnectGatewayId": "dxgw-1",
        "bgpPeers": [
            {"addressFamily": "ipv4", "bgpStatus": "up", "bgpPeerState": "available"},
        ],
    }


def _group(group_id=GROUP_ID, name="prod-pair"):
    return {
        "resiliencyGroupId": group_id,
        "resiliencyGroupArn": GROUP_ARN,
        "resiliencyGroupName": name,
        "resiliencyGroupType": "CLASSIC",
        "ownerAccount": ACCOUNT,
        "state": "available",
    }


def _association(conn_id, group_id=GROUP_ID):
    return {
        "resiliencyGroupId": group_id,
        "connectionArn": _conn_arn(conn_id),
        "state": "associated",
    }


class _StubbedTopology(unittest.TestCase):
    """Base: one stubbed directconnect client wired into server._dx_clients."""

    def setUp(self):
        self.client = boto3.client(
            "directconnect",
            region_name=REGION,
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        self.stubber = Stubber(self.client)
        patcher = mock.patch.object(
            server, "_dx_clients", return_value=[(REGION, self.client)]
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_topology(self):
        with self.stubber:
            result = get_dx_topology()
        self.stubber.assert_no_pending_responses()
        return result


class TestResiliencyGroupsNonHosted(_StubbedTopology):
    """Connections owned by this account (non-hosted VIFs): the full
    connection <-> resiliency-group join must work."""

    def test_group_membership_joined_to_connections(self):
        self.stubber.add_response(
            "describe_connections",
            {"connections": [_connection("dxcon-aaaa1111"),
                             _connection("dxcon-bbbb2222", device="device-2",
                                         location="LOC2")]},
            {},
        )
        self.stubber.add_response(
            "list_resiliency_groups", {"items": [_group()]}, {},
        )
        self.stubber.add_response(
            "list_resiliency_group_associations",
            {"items": [_association("dxcon-aaaa1111"),
                       _association("dxcon-bbbb2222")]},
            {"resiliencyGroupId": GROUP_ID},
        )
        self.stubber.add_response(
            "describe_virtual_interfaces",
            {"virtualInterfaces": [
                _vif("dxvif-aaaa1111", "dxcon-aaaa1111"),
                _vif("dxvif-bbbb2222", "dxcon-bbbb2222", device="device-2",
                     location="LOC2"),
            ]},
            {},
        )

        topo = self.run_topology()

        self.assertEqual(len(topo["resiliency_groups"]), 1)
        group = topo["resiliency_groups"][0]
        self.assertEqual(group["resiliency_group_id"], GROUP_ID)
        self.assertEqual(group["name"], "prod-pair")
        # connectionArn -> connection ID extraction
        self.assertEqual(group["member_connection_ids"],
                         ["dxcon-aaaa1111", "dxcon-bbbb2222"])
        # join back onto the connection view
        by_id = {c["connection_id"]: c for c in topo["connections"]}
        self.assertEqual(by_id["dxcon-aaaa1111"]["resiliency_group_id"], GROUP_ID)
        self.assertEqual(by_id["dxcon-bbbb2222"]["resiliency_group_id"], GROUP_ID)
        # all parent connections visible -> nothing indeterminate
        vis = topo["connection_visibility"]
        self.assertTrue(vis["all_vif_connections_visible"])
        self.assertEqual(vis["invisible_connection_ids"], [])
        self.assertEqual(topo["resiliency_group_errors"], [])


class TestResiliencyGroupPagination(_StubbedTopology):
    """Both list operations paginate via nextToken with results under `items`."""

    def test_groups_and_associations_paginate(self):
        self.stubber.add_response(
            "describe_connections",
            {"connections": [_connection("dxcon-aaaa1111"),
                             _connection("dxcon-bbbb2222")]},
            {},
        )
        # groups: two pages, fetched fully before any association call
        self.stubber.add_response(
            "list_resiliency_groups",
            {"items": [_group()], "nextToken": "page2"},
            {},
        )
        self.stubber.add_response(
            "list_resiliency_groups",
            {"items": [_group(group_id="rg-fedcba9876543210fedcb", name="empty")]},
            {"nextToken": "page2"},
        )
        # first group's associations: two pages
        self.stubber.add_response(
            "list_resiliency_group_associations",
            {"items": [_association("dxcon-aaaa1111")], "nextToken": "assoc2"},
            {"resiliencyGroupId": GROUP_ID},
        )
        self.stubber.add_response(
            "list_resiliency_group_associations",
            {"items": [_association("dxcon-bbbb2222")]},
            {"resiliencyGroupId": GROUP_ID, "nextToken": "assoc2"},
        )
        # second group: no members
        self.stubber.add_response(
            "list_resiliency_group_associations",
            {"items": []},
            {"resiliencyGroupId": "rg-fedcba9876543210fedcb"},
        )
        self.stubber.add_response(
            "describe_virtual_interfaces", {"virtualInterfaces": []}, {},
        )

        topo = self.run_topology()

        self.assertEqual(len(topo["resiliency_groups"]), 2)
        first = topo["resiliency_groups"][0]
        self.assertEqual(first["member_connection_ids"],
                         ["dxcon-aaaa1111", "dxcon-bbbb2222"])
        self.assertEqual(topo["resiliency_groups"][1]["member_connection_ids"], [])


class TestHostedVifsIndeterminate(_StubbedTopology):
    """Hosted VIFs: parent connections invisible -> membership must read as
    INDETERMINATE, not as 'no resiliency group'."""

    def test_invisible_connections_flagged(self):
        self.stubber.add_response("describe_connections", {"connections": []}, {})
        self.stubber.add_response("list_resiliency_groups", {"items": []}, {})
        self.stubber.add_response(
            "describe_virtual_interfaces",
            {"virtualInterfaces": [_vif("dxvif-hosted01", "dxcon-partner1")]},
            {},
        )

        topo = self.run_topology()

        vis = topo["connection_visibility"]
        self.assertFalse(vis["all_vif_connections_visible"])
        self.assertEqual(vis["invisible_connection_ids"], ["dxcon-partner1"])
        self.assertIn("INDETERMINATE", vis["note"])


class TestGroupListingErrorNotSilent(_StubbedTopology):
    """A failing resiliency-group listing is reported in the output instead of
    being silently swallowed; the rest of the topology still returns."""

    def test_error_surfaces_in_output(self):
        self.stubber.add_response(
            "describe_connections",
            {"connections": [_connection("dxcon-aaaa1111")]},
            {},
        )
        self.stubber.add_client_error(
            "list_resiliency_groups",
            service_error_code="AccessDeniedException",
            service_message="not authorized",
        )
        self.stubber.add_response(
            "describe_virtual_interfaces",
            {"virtualInterfaces": [_vif("dxvif-aaaa1111", "dxcon-aaaa1111")]},
            {},
        )

        topo = self.run_topology()

        self.assertEqual(len(topo["resiliency_group_errors"]), 1)
        err = topo["resiliency_group_errors"][0]
        self.assertEqual(err["region"], REGION)
        self.assertEqual(err["error"], "AccessDeniedException")
        self.assertIn("INDETERMINATE", err["note"])
        # topology still useful
        self.assertEqual(len(topo["connections"]), 1)
        self.assertEqual(len(topo["virtual_interfaces"]), 1)
        self.assertIsNone(topo["connections"][0]["resiliency_group_id"])


class TestConnectionArnParsing(unittest.TestCase):
    def test_standard_arn(self):
        self.assertEqual(
            server._connection_id_from_arn(_conn_arn("dxcon-abc123")),
            "dxcon-abc123",
        )

    def test_missing_or_empty(self):
        self.assertIsNone(server._connection_id_from_arn(None))
        self.assertIsNone(server._connection_id_from_arn(""))
        self.assertIsNone(server._connection_id_from_arn("arn:aws:directconnect:::dxcon/"))


if __name__ == "__main__":
    unittest.main()
