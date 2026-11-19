"""Deterministic CIDR coverage analysis for Direct Connect VIF resilience.

Pure stdlib (ipaddress) — no external dependencies. All arithmetic is exact
subnet-containment math; nothing here is heuristic.

Coverage semantics for a prefix P from VIF-X against peer VIF-Y:
  - COVERED:  Y has P exactly, or Y has a supernet fully containing P.
  - PARTIAL SUPERNET (residual): P is a supernet from X and Y covers only
    part of it via more-specifics. The uncovered residual set is computed
    exactly (P minus the union of Y's prefixes contained in P).
  - GAP: Y has no exact match, no supernet, and no more-specific inside P.

Default routes (0.0.0.0/0, ::/0) are reported separately and excluded from
coverage classification. IPv4 and IPv6 are analysed independently.
"""

from __future__ import annotations

import ipaddress
from typing import Dict, List, Optional

DEFAULT_ROUTES = ("0.0.0.0/0", "::/0")


def _parse(cidr: str):
    """Parse a CIDR string into an ip_network, or None if invalid."""
    try:
        return ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return None


def _parse_vifs(vifs: List[dict]):
    """Normalise input VIFs into parsed, de-duplicated network lists.

    Returns (parsed_vifs, invalid_prefixes, default_route_present).
    """
    parsed = []
    invalid: List[dict] = []
    default_present = {"ipv4": [], "ipv6": []}

    for vif in vifs:
        nets = []
        seen = set()
        for raw in vif.get("prefixes") or []:
            if raw.strip() in DEFAULT_ROUTES or _is_default(raw):
                fam = "ipv6" if ":" in raw else "ipv4"
                if vif["id"] not in default_present[fam]:
                    default_present[fam].append(vif["id"])
                continue
            net = _parse(raw)
            if net is None:
                invalid.append({"vif": vif["id"], "prefix": raw})
                continue
            if net in seen:
                continue
            seen.add(net)
            nets.append(net)
        parsed.append({"id": vif["id"], "name": vif.get("name") or vif["id"], "nets": nets})

    return parsed, invalid, default_present


def _is_default(cidr: str) -> bool:
    net = _parse(cidr)
    return net is not None and net.prefixlen == 0


def _covering_net(prefix, nets) -> Optional[object]:
    """Return the first network in nets that covers prefix (exact or supernet)."""
    for net in nets:
        if net.version == prefix.version and prefix.subnet_of(net):
            return net
    return None


def _contained_subnets(supernet, nets):
    """Networks in nets strictly inside supernet (not equal, same family)."""
    return [
        n for n in nets
        if n.version == supernet.version and n != supernet and n.subnet_of(supernet)
    ]


def _residual(supernet, subnets):
    """Exact set difference: supernet minus the union of subnets.

    CIDR blocks never partially overlap — any two either nest or are
    disjoint — so iterative address_exclude is exact.
    """
    remaining = [supernet]
    for sub in ipaddress.collapse_addresses(subnets):
        next_remaining = []
        for chunk in remaining:
            if sub.subnet_of(chunk):
                next_remaining.extend(chunk.address_exclude(sub))
            elif chunk.subnet_of(sub):
                continue  # chunk fully consumed
            else:
                next_remaining.append(chunk)
        remaining = next_remaining
    return sorted(ipaddress.collapse_addresses(remaining))


def _classify_against_peer(prefix, peer_nets) -> dict:
    """Classify one prefix against one peer VIF's prefix list."""
    if _covering_net(prefix, peer_nets) is not None:
        return {"status": "covered"}
    inside = _contained_subnets(prefix, peer_nets)
    if inside:
        residual = _residual(prefix, inside)
        if not residual:
            # The peer's more-specifics exactly tile this supernet — every
            # address is reachable, so it is fully covered (not partial).
            return {"status": "covered"}
        return {
            "status": "partial_supernet",
            "covered_subnets": [str(n) for n in sorted(ipaddress.collapse_addresses(inside))],
            "uncovered_residual": [str(n) for n in residual],
        }
    return {"status": "gap"}


def analyse(direction: str, vifs: List[dict]) -> dict:
    """Full coverage analysis across a redundant VIF set.

    Input: direction ("accepted"|"advertised"), vifs: [{id, name, prefixes[]}].
    """
    if not vifs or len(vifs) < 2:
        raise ValueError("At least 2 VIFs are required for a coverage comparison.")

    parsed, invalid, default_present = _parse_vifs(vifs)
    empty_vifs = [v["id"] for v in parsed if not v["nets"]]

    # Per-family prefix universe: every unique prefix any VIF carries.
    findings = {"ipv4": {"gaps": [], "partial_supernet": [], "partial": [], "covered": []},
                "ipv6": {"gaps": [], "partial_supernet": [], "partial": [], "covered": []}}

    universe = {}
    for vif in parsed:
        for net in vif["nets"]:
            universe.setdefault(net, []).append(vif["id"])

    for net in sorted(universe, key=lambda n: (n.version, int(n.network_address), n.prefixlen)):
        fam = "ipv4" if net.version == 4 else "ipv6"
        present_on = universe[net]
        peer_results = {}
        for vif in parsed:
            if vif["id"] in present_on:
                continue
            peer_results[vif["id"]] = _classify_against_peer(net, vif["nets"])

        entry = {"prefix": str(net), "present_on": present_on}
        statuses = {r["status"] for r in peer_results.values()}

        if not peer_results or statuses == {"covered"}:
            findings[fam]["covered"].append(entry)
        elif "partial_supernet" in statuses:
            entry["peer_coverage"] = peer_results
            findings[fam]["partial_supernet"].append(entry)
        elif len(present_on) == 1 and statuses == {"gap"}:
            entry["missing_from"] = [v for v, r in peer_results.items() if r["status"] == "gap"]
            findings[fam]["gaps"].append(entry)
        else:
            entry["missing_from"] = [v for v, r in peer_results.items() if r["status"] == "gap"]
            entry["covered_on"] = present_on + [v for v, r in peer_results.items() if r["status"] == "covered"]
            findings[fam]["partial"].append(entry)

    # Pairwise directional view: what A carries that B does not cover.
    pairwise = []
    for a in parsed:
        for b in parsed:
            if a["id"] == b["id"]:
                continue
            gaps, partials, covered = [], [], []
            for net in a["nets"]:
                result = _classify_against_peer(net, b["nets"])
                if result["status"] == "covered":
                    covered.append(str(net))
                elif result["status"] == "partial_supernet":
                    partials.append({"prefix": str(net),
                                     "uncovered_residual": result["uncovered_residual"]})
                else:
                    gaps.append(str(net))
            pairwise.append({
                "if_this_vif_fails": a["id"], "vif_name": a["name"],
                "surviving_peer": b["id"], "peer_name": b["name"],
                "blackholed_prefixes": gaps,
                "partially_blackholed": partials,
                "covered_count": len(covered),
            })

    summary = {
        "total_unique_prefixes": len(universe),
        "gaps": sum(len(findings[f]["gaps"]) for f in ("ipv4", "ipv6")),
        "partial_supernet": sum(len(findings[f]["partial_supernet"]) for f in ("ipv4", "ipv6")),
        "partial": sum(len(findings[f]["partial"]) for f in ("ipv4", "ipv6")),
        "covered": sum(len(findings[f]["covered"]) for f in ("ipv4", "ipv6")),
    }

    return {
        "direction": direction,
        "summary": summary,
        "ipv4": findings["ipv4"],
        "ipv6": findings["ipv6"],
        "default_route_present": default_present,
        "empty_vifs": empty_vifs,
        "invalid_prefixes": invalid,
        "pairwise": pairwise,
    }
