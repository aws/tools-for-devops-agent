import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from coverage_engine import analyse  # noqa: E402


def vif(vid, *prefixes, name=None):
    return {"id": vid, "name": name or vid, "prefixes": list(prefixes)}


class TestCoverage(unittest.TestCase):
    def test_exact_match_covered(self):
        r = analyse("accepted", [vif("a", "10.0.0.0/8"), vif("b", "10.0.0.0/8")])
        self.assertEqual(r["summary"]["gaps"], 0)
        self.assertEqual(r["summary"]["covered"], 1)

    def test_hard_gap(self):
        r = analyse("accepted", [vif("a", "10.10.1.0/24"), vif("b", "10.10.2.0/24")])
        self.assertEqual(r["summary"]["gaps"], 2)
        gap_prefixes = {g["prefix"] for g in r["ipv4"]["gaps"]}
        self.assertEqual(gap_prefixes, {"10.10.1.0/24", "10.10.2.0/24"})

    def test_supernet_residual_design_case(self):
        # VIF-A has 10.10.1.0/24; VIF-B has 10.10.0.0/22.
        # A→B: /24 covered by the /22.
        # B→A: /22 only partially covered → residual = 10.10.0.0/24 + 10.10.2.0/23.
        r = analyse("accepted", [vif("a", "10.10.1.0/24"), vif("b", "10.10.0.0/22")])
        self.assertEqual(r["summary"]["gaps"], 0)
        self.assertEqual(r["summary"]["partial_supernet"], 1)
        entry = r["ipv4"]["partial_supernet"][0]
        self.assertEqual(entry["prefix"], "10.10.0.0/22")
        residual = entry["peer_coverage"]["a"]["uncovered_residual"]
        self.assertEqual(residual, ["10.10.0.0/24", "10.10.2.0/23"])
        # /24 itself is fully covered
        self.assertEqual(r["ipv4"]["covered"][0]["prefix"], "10.10.1.0/24")
        # pairwise: if b fails, residual space is partially blackholed via a
        pw = next(p for p in r["pairwise"] if p["if_this_vif_fails"] == "b")
        self.assertEqual(pw["partially_blackholed"][0]["uncovered_residual"],
                         ["10.10.0.0/24", "10.10.2.0/23"])

    def test_default_route_separated(self):
        r = analyse("accepted", [vif("a", "0.0.0.0/0", "10.0.0.0/8"), vif("b", "10.0.0.0/8")])
        self.assertEqual(r["default_route_present"]["ipv4"], ["a"])
        self.assertEqual(r["summary"]["covered"], 1)  # default excluded from universe

    def test_empty_vif_flagged(self):
        r = analyse("accepted", [vif("a", "10.0.0.0/8"), vif("b")])
        self.assertIn("b", r["empty_vifs"])
        self.assertEqual(r["summary"]["gaps"], 1)

    def test_three_vifs_partial(self):
        r = analyse("accepted", [
            vif("a", "192.168.1.0/24"),
            vif("b", "192.168.1.0/24"),
            vif("c", "10.0.0.0/8"),
        ])
        partial = {p["prefix"] for p in r["ipv4"]["partial"]}
        self.assertIn("192.168.1.0/24", partial)  # on a+b, missing from c
        gaps = {g["prefix"] for g in r["ipv4"]["gaps"]}
        self.assertIn("10.0.0.0/8", gaps)  # only on c

    def test_ipv6_supported(self):
        r = analyse("advertised", [
            vif("a", "2001:db8:1::/48"),
            vif("b", "2001:db8::/32"),
        ])
        self.assertEqual(len(r["ipv6"]["partial_supernet"]), 1)
        self.assertEqual(r["ipv6"]["covered"][0]["prefix"], "2001:db8:1::/48")

    def test_invalid_prefix_reported_not_fatal(self):
        r = analyse("accepted", [vif("a", "10.0.0.0/8", "not-a-cidr"), vif("b", "10.0.0.0/8")])
        self.assertEqual(r["invalid_prefixes"], [{"vif": "a", "prefix": "not-a-cidr"}])
        self.assertEqual(r["summary"]["covered"], 1)

    def test_supernet_tiled_by_more_specifics_is_covered(self):
        # A's three more-specifics exactly tile B's /22 → residual empty → COVERED,
        # not partial_supernet (regression guard for the aggregate-tiling case).
        r = analyse("accepted", [
            vif("a", "10.10.0.0/24", "10.10.1.0/24", "10.10.2.0/23"),
            vif("b", "10.10.0.0/22"),
        ])
        self.assertEqual(r["summary"]["partial_supernet"], 0)
        self.assertEqual(r["summary"]["gaps"], 0)
        # every prefix covered, none flagged
        self.assertEqual(r["ipv4"]["partial_supernet"], [])

    def test_supernet_partially_tiled_is_partial(self):
        # Only part of the /22 is tiled → still partial with the true residual.
        r = analyse("accepted", [vif("a", "10.10.1.0/24"), vif("b", "10.10.0.0/22")])
        self.assertEqual(r["summary"]["partial_supernet"], 1)
        entry = r["ipv4"]["partial_supernet"][0]
        self.assertEqual(entry["peer_coverage"]["a"]["uncovered_residual"],
                         ["10.10.0.0/24", "10.10.2.0/23"])

    def test_requires_two_vifs(self):
        with self.assertRaises(ValueError):
            analyse("accepted", [vif("a", "10.0.0.0/8")])

    def test_host_route_and_dedupe(self):
        r = analyse("accepted", [vif("a", "10.1.1.1/32", "10.1.1.1/32"), vif("b", "10.1.0.0/16")])
        self.assertEqual(r["summary"]["covered"], 1)
        self.assertEqual(r["summary"]["partial_supernet"], 1)


if __name__ == "__main__":
    unittest.main()
