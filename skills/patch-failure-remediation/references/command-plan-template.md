# Command plan template

Every remediation plan ends with a **Command plan**: a complete script the customer can run in
**AWS CloudShell** (or any shell with AWS CLI v2 and `python3`), signed in to the instance's
account and region. Build it from this template.

## Rules for filling it in

1. **Fill in everything.** Account ID, region, instance ID, SOP ID, step numbers and titles,
   expected output, and the re-patch parameters. Leave no `<...>` placeholders in the plan.
2. **SOP commands are verbatim.** Between `cat > ... <<'SOP_STEP'` and `SOP_STEP`, paste the SOP
   step's code block exactly as written, with no edits, additions or substituted values. The quoted
   heredoc means the shell doesn't expand anything inside it.
3. **Only the selected steps.** One block per step that applies to this instance's platform,
   distribution and version (SKILL.md Step 7), in the SOP's order, keeping the SOP's step numbers.
   Leave out steps for other distributions or versions entirely. Put a `# Run only if: <condition>`
   line in the header of conditional steps. Then the SOP's Validation block for this platform.
   Include the SOP's Diagnosis block as step 0 only if it isn't empty.
   Add one comment line at the top of the plan listing skipped steps, for example
   `# Skipped: step 5 (SLES only), step 6 (last resort, not needed: step 4 succeeded)`.
4. **Platform:** Linux uses `AWS-RunShellScript` and `.sh` files; Windows uses
   `AWS-RunPowerShellScript` and `.ps1` files. Use the code block for the instance's platform.
5. **Timeouts:** 600 seconds, or the SOP's *Estimated Duration* plus 300 seconds if that's longer.
   Set the `TIMEOUT` variable accordingly.
6. **Re-patch** with the failed `AWS-RunPatchBaseline` run's own parameters only (see
   `execution-guide.md`). Put them in `patch-values.json` and nowhere else: never paste a value
   into a shell command. Use `""` for any parameter the failed run didn't have. Leave out the
   Install block if the failed run was a Scan.
   Before writing a value, check it matches its format: `RebootOption` is `RebootIfNeeded` or
   `NoReboot`; `SnapshotId` and `AssociationId` are GUIDs; `InstallOverrideList` is an `s3://` or
   `https://` URL and `BaselineOverride` an `s3://` URL, containing only letters, digits and
   `. _ ~ / : % + = @ -`; `StepTimeoutSeconds` is a whole number from 1 to 36000. If any value
   doesn't match, leave the re-patch blocks out and write `Re-patch: not included - <parameter>
   value from the failed run is not in the documented format` instead.
7. **Unverified plan.** If the instance couldn't be found, still write the plan for the instance
   ID, Region and OS the user gave, starting with the `# UNVERIFIED: ...` line from SKILL.md, with
   `RebootOption` `RebootIfNeeded` and the other re-patch values `""`.
8. **No SOP, no command plan.** If no SOP matched, or a gate blocked remediation, write
   `Command plan: none - <reason>` and nothing else.

## Template (Linux)

````markdown
### Command plan

Run in **AWS CloudShell** in account `<account_id>`, region `<region>`, during the maintenance
window. Run one block at a time and check each result against "Expected" before going on. If a
step marked **abort on failure** fails, stop and don't run the rest.

```bash
# --- Setup (run once) ---
export AWS_REGION=<region>
export INSTANCE_ID=<instance_id>
export TIMEOUT=600
run_step() {  # run_step <document> <comment> <file>
  local params cmd
  params=$(python3 -c 'import json,sys; print(json.dumps({"commands":[open(sys.argv[1]).read()],"executionTimeout":[sys.argv[2]]}))' "$3" "$TIMEOUT")
  cmd=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name "$1" \
        --comment "$2" --timeout-seconds "$TIMEOUT" --parameters "$params" \
        --query Command.CommandId --output text) || return 1
  echo "CommandId: $cmd"
  aws ssm wait command-executed --command-id "$cmd" --instance-id "$INSTANCE_ID" 2>/dev/null
  aws ssm get-command-invocation --command-id "$cmd" --instance-id "$INSTANCE_ID" \
    --query '{Status:Status,Output:StandardOutputContent,Error:StandardErrorContent}' --output json
}
```

```bash
# Applies to: <distribution and version>
# Skipped: step <n> (<reason>), step <n> (<reason>)
```

```bash
# --- <SOP-ID> step <n>: <step title> ---
# Expected: <expected output>    On failure: <abort | continue>
cat > step<n>.sh <<'SOP_STEP'
<step n code block, verbatim>
SOP_STEP
run_step AWS-RunShellScript "<SOP-ID> step <n>" step<n>.sh
```

```bash
# --- <SOP-ID> step <n>: <step title> ---
# Run only if: <condition, e.g. step 4 failed>
# Expected: <expected output>    On failure: <abort | continue>
cat > step<n>.sh <<'SOP_STEP'
<step n code block, verbatim>
SOP_STEP
run_step AWS-RunShellScript "<SOP-ID> step <n>" step<n>.sh
```

```bash
# --- <SOP-ID> validation ---
# Expected: <SOP validation expected result>
cat > validation.sh <<'SOP_STEP'
<validation code block, verbatim>
SOP_STEP
run_step AWS-RunShellScript "<SOP-ID> validation" validation.sh
```

```bash
# --- Re-patch values copied from the failed run ---
# Each value is checked against its documented format before anything is sent; leave a value
# empty ("") if the failed run didn't have that parameter.
cat > patch-values.json <<'PATCH_VALUES'
{"RebootOption": "<RebootIfNeeded|NoReboot>", "SnapshotId": "<guid or empty>", "InstallOverrideList": "<s3:// or https:// URL or empty>", "BaselineOverride": "<s3:// URL or empty>", "AssociationId": "<guid or empty>", "StepTimeoutSeconds": "<1-36000 or empty>"}
PATCH_VALUES
patch_params() {  # patch_params Scan|Install -> validated AWS-RunPatchBaseline parameters (JSON)
  python3 - "$1" patch-values.json <<'PY'
import json, re, sys
op, values = sys.argv[1], json.load(open(sys.argv[2]))
GUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
URL = r"(s3://|https://)[A-Za-z0-9._~/:%+=@-]{1,1024}"
RULES = {"RebootOption": r"RebootIfNeeded|NoReboot", "SnapshotId": GUID, "AssociationId": GUID,
         "InstallOverrideList": URL, "BaselineOverride": r"s3://[A-Za-z0-9._~/:%+=@-]{1,1024}",
         "StepTimeoutSeconds": r"[1-9][0-9]{0,4}"}
keys = ["SnapshotId", "BaselineOverride", "AssociationId"]
if op == "Install":
    keys += ["RebootOption", "InstallOverrideList", "StepTimeoutSeconds"]
elif op != "Scan":
    sys.exit("refusing: operation must be Scan or Install")
params = {"Operation": [op]}
for k in keys:
    v = values.get(k)
    if v in (None, ""):
        continue
    if not isinstance(v, str) or not re.fullmatch(RULES[k], v):
        sys.exit(f"refusing: {k} value {v!r} is not in the documented format")
    if k == "StepTimeoutSeconds" and int(v) > 36000:
        sys.exit("refusing: StepTimeoutSeconds must be 1-36000")
    params[k] = [v]
print(json.dumps(params))
PY
}
```

```bash
# --- Re-patch 1: dry run (Scan) ---
# Expected: Status "Success"
P=$(patch_params Scan) && \
SCAN=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunPatchBaseline \
  --comment "post-remediation scan" --parameters "$P" \
  --query Command.CommandId --output text) && echo "CommandId: $SCAN" && \
aws ssm wait command-executed --command-id "$SCAN" --instance-id "$INSTANCE_ID"; \
aws ssm get-command-invocation --command-id "$SCAN" --instance-id "$INSTANCE_ID" --query Status --output text
```

```bash
# --- Re-patch 2: Install (only after the Scan succeeded) ---
# RebootOption=<value>: <the instance may reboot | the instance will not reboot>
P=$(patch_params Install) && \
aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunPatchBaseline \
  --comment "post-remediation install" --parameters "$P" \
  --query Command.CommandId --output text
```

To run a step directly on the instance instead (Session Manager shell), paste the contents of the
step's `SOP_STEP` block and run it as root.
````

## Windows differences

- Use `AWS-RunPowerShellScript` in `run_step` and name the files `step1.ps1`, `step2.ps1`,
  `validation.ps1`.
- The script is still run from CloudShell (bash); only the document and the file contents change.
- For running directly on the instance, paste the block into an elevated PowerShell session.

## Example (filled in, Linux, SOP-002 step 2)

```bash
# --- SOP-002 step 2: Clean package manager cache ---
# Expected: "Cache cleaned"    On failure: continue
cat > step2.sh <<'SOP_STEP'
yum clean all 2>/dev/null; apt-get clean 2>/dev/null; dnf clean all 2>/dev/null; du -sh /var/cache/yum /var/cache/apt /var/cache/dnf 2>/dev/null; echo "Cache cleaned"
SOP_STEP
run_step AWS-RunShellScript "SOP-002 step 2" step2.sh
```
