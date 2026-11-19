# Skip Scheduled Maintenance Skill (Sample)

This is a **sample skill** demonstrating how to write an incident filtering skill for the AWS DevOps Agent **Incident triage** agent type. It shows how to define skip criteria so the agent automatically filters low-priority incidents during a scheduled maintenance window, avoiding unnecessary investigations for expected disruptions.

This skill appears as the ["Example: Incident filtering skill"](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#example-incident-filtering-skill) in the AWS DevOps Agent User Guide.

> **Note:** This skill uses hardcoded dates and severity thresholds specific to a fictional maintenance scenario and cannot be reused as-is. Use it as a template for writing similar incident filtering skills for your own maintenance windows.

## Purpose

Skills targeted to the Incident triage agent type can define criteria for automatically skipping incidents that don't require investigation. When a new incident matches the skip criteria, AWS DevOps Agent marks it as **Skipped** and provides a reason explaining why it was filtered.

During scheduled maintenance windows, monitoring systems often fire alarms for expected disruptions — service restarts, brief connectivity blips, or elevated error rates from rolling deployments. Without filtering guidance, the Incident triage agent would investigate each of these as a genuine incident. This sample skill demonstrates how to encode maintenance-window awareness so the agent can skip low-priority alarms while still escalating critical ones.

## Key Capabilities (Demonstrated)

- Defining skip criteria that the Incident triage agent evaluates for each incoming incident
- Combining multiple filtering conditions (time window AND severity) for skip decisions
- Preserving escalation paths for high-severity incidents regardless of maintenance status

## Prerequisites

- AWS DevOps Agent space

## Limitations

- This skill uses hardcoded dates (2025-03-15 02:00–06:00 UTC) — you must update the window for your actual maintenance schedule
- Only filters by severity and time; does not account for specific services or alarm sources
- Cannot be reused as-is — adapt the time window and criteria to your environment

## Agent Types

This skill is designed for:

- **Incident triage** — initial incident assessment. When the skill's skip criteria match an incoming incident, the agent marks it as Skipped instead of launching an investigation.

## Uploading to AWS DevOps Agent

This skill has no prerequisites beyond an Agent Space. It's a sample with a hardcoded maintenance window, so the catalog copy only demonstrates the behavior; to filter incidents in your own window, adapt `SKILL.md` and use Option B. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **Incident Triage** (`INCIDENT_TRIAGE`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **Incident Triage** recommended | Yes: files and agent types | Re-upload a new zip |

Skip criteria only take effect in incident triage, which decides whether to investigate an incoming incident, so target **Incident Triage** only. **Generic** would load the skip rules into every agent type, RCA and on-demand chat included, where they don't apply.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `skip-scheduled-maintenance`.
4. Choose **Details** and check that the agent type is **Incident Triage**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to set your own maintenance window and severity threshold in `SKILL.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/skip-scheduled-maintenance/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f skip-scheduled-maintenance.zip
   zip -r skip-scheduled-maintenance.zip skip-scheduled-maintenance/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l skip-scheduled-maintenance.zip | tail -1   # expect 1 file
   ```

2. Check that the zip has this structure:

   ```text
   skip-scheduled-maintenance.zip
   └── skip-scheduled-maintenance/
       └── SKILL.md                    # required: frontmatter with name and description
   ```

   The zip leaves out `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `skip-scheduled-maintenance.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **Incident Triage**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

### As a Template

1. Copy the `SKILL.md` file as a starting point for your own incident filtering skill
2. Replace the hardcoded maintenance window with your actual planned maintenance dates/times
3. Adjust the severity threshold if your organization uses different severity levels
4. Add additional filtering criteria (e.g., specific services, alarm names, or AWS accounts)
5. Consider creating separate skills for different maintenance windows or filtering scenarios

### Sample Incident triage Behavior (with this skill active)

When the skill is active, the Incident triage agent evaluates each incoming incident against the skip criteria. Incidents that match are marked as **Skipped** with a reason:

- **Skipped:** A MEDIUM-severity alarm arriving at 2025-03-15 03:30 UTC
- **Skipped:** A LOW-severity alarm arriving at 2025-03-15 04:15 UTC
- **Investigated:** A CRITICAL-severity alarm arriving at 2025-03-15 03:00 UTC (high severity is never skipped)
- **Investigated:** A HIGH-severity alarm arriving at 2025-03-15 05:00 UTC (high severity is never skipped)
- **Investigated:** A MEDIUM-severity alarm arriving at 2025-03-15 07:00 UTC (outside maintenance window)
