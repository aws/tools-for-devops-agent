# Remediation plan template

End every investigation with this section, filled in, and update it as you remediate. Leave no
`<...>` placeholder in the result. Use the [command plan template](command-plan-template.md) for
the Command plan that follows it.

```
## Remediation plan
Instance:        <instance_id> (<platform>, <distribution>)  Account: <account_id>  Region: <region>
Failed run:      AWS-RunPatchBaseline <command id>, Operation=<Scan|Install>, source <run command | maintenance window | patch policy>
Root cause:      <one or two sentences, quoting the decisive error line>
SOP:             <SOP-ID> <title>  (file: references/sops/<file>)  Risk: <level>  Reboot: <yes/no>
Match evidence:  <the Symptoms line(s) that match the error>
Ruled out:       <similar SOP-ID> - <why it doesn't fit>; ... (or none)
Gates:           maintenance window <open until HH:MM UTC / closed / none>;
                 Install attempts in 12h: <n>/3;  prerequisites: <met / which one failed>
Applies to:      <distribution and version>
Steps to run:    <SOP-ID> step <n> - <title>  (AWS-RunShellScript | AWS-RunPowerShellScript)
                 <SOP-ID> step <n> - <title>  Run only if: <condition>
                 ...
                 Validation: <SOP validation>
Skipped:         step <n> - <reason, e.g. SLES only>; step <n> - <reason>
Re-patch:        AWS-RunPatchBaseline Scan, then Install with RebootOption=<value>
                 [SnapshotId=<value>] [InstallOverrideList=<url>] [BaselineOverride=<url>] [AssociationId=<id>]
Status:          <ready to execute in chat | unverified: reason; check the gates before running | blocked: reason | no SOP - no action taken>
```

Field rules:

- **Steps to run** lists only the steps selected for this instance's platform, distribution and
  version, under the SOP's own step numbers. Mark conditional steps with `Run only if:`.
- **Ruled out** names the SOPs whose symptoms looked similar and why they don't fit, for example
  `SOP-002 - disk blocks are free; inodes are exhausted`.
- **Skipped** gives every step left out and why.
- **Re-patch** lists only the parameters the failed run had.
- **Status** is `no SOP - no action taken` when no SOP matched; the Command plan is then
  `Command plan: none - <reason>`.
