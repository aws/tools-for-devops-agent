#!/usr/bin/env bash
set -euo pipefail

bucket=""
prefix=""
region=""
profile="standard"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) bucket="$2"; shift 2 ;;
    --prefix) prefix="$2"; shift 2 ;;
    --region) region="$2"; shift 2 ;;
    --profile) profile="$2"; shift 2 ;;
    *) echo "Unsupported argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$bucket" && -n "$prefix" && -n "$region" ]] || { echo "bucket, prefix, and region are required" >&2; exit 2; }
[[ "$profile" == "standard" || "$profile" == "extended" ]] || { echo "profile must be standard or extended" >&2; exit 2; }

outdir="$(mktemp -d /tmp/gpu-diag.XXXXXX)"
trap 'rm -rf "$outdir"' EXIT
summary="$outdir/summary.txt"
capture_failures=()

run_capture() {
  local name="$1"
  local output="$2"
  shift 2
  printf '[%s] ' "$name" | tee -a "$summary"
  if timeout --kill-after=30 300 "$@" >"$output" 2>&1; then
    echo "SUCCESS" | tee -a "$summary"
  else
    status=$?
    echo "FAILED (exit=$status)" | tee -a "$summary"
    capture_failures+=("$name")
  fi
}

run_shell_capture() {
  local name="$1"
  local output="$2"
  local command="$3"
  printf '[%s] ' "$name" | tee -a "$summary"
  if timeout --kill-after=30 300 bash -o pipefail -c "$command" >"$output" 2>&1; then
    echo "SUCCESS" | tee -a "$summary"
  else
    status=$?
    echo "FAILED (exit=$status)" | tee -a "$summary"
    capture_failures+=("$name")
  fi
}

echo "GPU diagnostics collection" | tee "$summary"
echo "profile=$profile" | tee -a "$summary"
date -u --iso-8601=seconds | tee -a "$summary"

if [[ -x /usr/bin/nvidia-bug-report.sh ]]; then
  (
    cd "$outdir"
    timeout --kill-after=30 300 /usr/bin/nvidia-bug-report.sh
  ) >>"$summary" 2>&1 || true
fi
run_capture "nvidia-smi" "$outdir/nvidia-smi.txt" nvidia-smi
run_capture "nvidia-smi-query" "$outdir/nvidia-smi-query.txt" nvidia-smi -q
run_capture "nvlink-status" "$outdir/nvlink-status.txt" nvidia-smi nvlink -s
run_capture "nvlink-errors" "$outdir/nvlink-errors.txt" nvidia-smi nvlink -e
run_capture "gpu-topology" "$outdir/nvidia-topo.txt" nvidia-smi topo -m
run_capture "ecc-errors" "$outdir/nvidia-ecc.txt" nvidia-smi -q -d ECC
run_capture "row-remap-state" "$outdir/row-remap-state.txt" nvidia-smi -q -d ROW_REMAPPER
run_shell_capture "kernel-xid" "$outdir/kernel-xid.txt" "journalctl -k -b 2>/dev/null | grep -Ei 'Xid|GPU has fallen' || true"
run_shell_capture "kernel-nvidia" "$outdir/kernel-nvidia.txt" "journalctl -k -b 2>/dev/null | grep -i nvidia || true"
run_shell_capture "fabric-manager" "$outdir/fabricmanager-status.txt" "systemctl status nvidia-fabricmanager 2>&1 || true"
run_shell_capture "fabric-manager-log" "$outdir/fabricmanager-log.txt" "journalctl -u nvidia-fabricmanager -b 2>/dev/null | tail -1000 || true"
run_capture "firmware" "$outdir/firmware-inventory.txt" nvidia-smi --query-gpu=index,name,uuid,vbios_version,driver_version,gsp.mode.current,gsp.mode.default --format=csv
run_shell_capture "os-info" "$outdir/os-info.txt" "uname -a; cat /etc/os-release; uptime"

if [[ "$profile" == "extended" ]]; then
  run_capture "efa-devices" "$outdir/efa-devices.txt" ibv_devinfo
  run_capture "efa-status" "$outdir/efa-status.txt" ibstat
  run_shell_capture "efa-counters" "$outdir/efa-counters.txt" "find /sys/class/infiniband -path '*/counters/*' -type f -exec sh -c 'echo \"\$1: \$(cat \"\$1\")\"' _ {} \\;"
  run_capture "pcie-link" "$outdir/pcie-link.txt" nvidia-smi --query-gpu=index,pci.bus_id,pcie.link.gen.current,pcie.link.width.current,pcie.link.gen.max,pcie.link.width.max --format=csv
fi

CAPTURE_FAILURES="$(IFS=,; printf '%s' "${capture_failures[*]}")" \
OUTDIR="$outdir" PROFILE="$profile" PREFIX="$prefix" python3 - <<'PY'
import json
import os
import re
import unicodedata
from pathlib import Path

outdir = Path(os.environ["OUTDIR"])
findings = []
failed_captures = [name for name in os.environ["CAPTURE_FAILURES"].split(",") if name]
nvlink_error_counters = (
    "malformed packet errors",
    "buffer overrun errors",
    "rx errors",
    "rx remote errors",
    "rx general errors",
    "local link integrity errors",
    "effective errors",
    "symbol errors",
)


def has_nonzero_counter(line):
    match = re.search(r":\s*(\d+)\s*$", line)
    return bool(match and int(match.group(1)) > 0)


def add_finding(severity, filename, line_number, line):
    evidence = "".join(
        character for character in line
        if not unicodedata.category(character).startswith("C")
    )
    findings.append({
        "severity": severity,
        "artifactKey": f"{os.environ['PREFIX']}/{filename}",
        "line": line_number,
        "evidence": evidence[:500],
    })


for filename in ("kernel-xid.txt", "nvidia-ecc.txt", "nvlink-errors.txt", "fabricmanager-status.txt"):
    path = outdir / filename
    if not path.exists():
        continue
    for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        lowered = line.lower()
        if filename == "kernel-xid.txt" and ("xid 79" in lowered or "fallen off bus" in lowered):
            add_finding("critical", filename, number, line)
        elif filename == "kernel-xid.txt" and "xid" in lowered:
            add_finding("high", filename, number, line)
        elif filename == "nvidia-ecc.txt" and "uncorrectable" in lowered and has_nonzero_counter(line):
            add_finding("critical", filename, number, line)
        elif filename == "nvlink-errors.txt" and any(
            counter in lowered for counter in nvlink_error_counters
        ) and has_nonzero_counter(line):
            add_finding("high", filename, number, line)
        elif filename == "fabricmanager-status.txt" and ("failed" in lowered or "inactive" in lowered):
            add_finding("high", filename, number, line)
manifest = {
    "collectionComplete": not failed_captures,
    "failedCaptures": failed_captures,
    "profile": os.environ["PROFILE"],
    "expectedFiles": ["summary.txt", "nvidia-smi.txt", "nvidia-smi-query.txt", "kernel-xid.txt", "nvidia-ecc.txt", "nvlink-errors.txt"],
    "artifacts": [
        {"key": f"{os.environ['PREFIX']}/{path.name}", "bytes": path.stat().st_size}
        for path in sorted(outdir.iterdir()) if path.is_file()
    ],
}
(outdir / "findings.json").write_text(json.dumps({"findings": findings}, indent=2))
manifest["artifacts"].append({"key": f"{os.environ['PREFIX']}/findings.json", "bytes": (outdir / "findings.json").stat().st_size})
(outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
PY

aws s3 cp "$outdir/" "s3://$bucket/$prefix/" --recursive --region "$region" --only-show-errors
