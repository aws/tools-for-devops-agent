# Admin Tooling

Build CLI tools and admin utilities for project management at scale.

## Use Cases

- **Bulk operations:** Create/manage many projects at once
- **Auditing:** Report on project usage and configuration
- **Maintenance:** Clean up unused projects
- **Onboarding:** Help teams set up their projects
- **Automation:** Integrate with CI/CD and IaC

## Full-Featured CLI

Build a comprehensive CLI tool:

### Python with Click

```python
# cli/ldprojects.py
import click
import json
from tabulate import tabulate
from launchdarkly.projects import ProjectManager

pm = ProjectManager()

@click.group()
@click.option('--api-token', envvar='LAUNCHDARKLY_API_TOKEN', help='LaunchDarkly API token')
@click.pass_context
def cli(ctx, api_token):
    """LaunchDarkly project management CLI."""
    ctx.obj = ProjectManager(api_token)

@cli.command()
@click.argument('name')
@click.argument('key')
@click.option('--tags', '-t', multiple=True, help='Project tags')
@click.option('--save-env/--no-save-env', default=True, help='Save SDK keys to .env')
@click.pass_obj
def create(pm, name, key, tags, save_env):
    """Create a new project."""
    try:
        project = pm.create_project(name, key, list(tags))
        click.echo(f"✓ Created: {project['name']} ({project['key']})")
        
        if save_env:
            from launchdarkly.env_config import save_sdk_key_to_env
            save_sdk_key_to_env(key, "production")
            click.echo(f"✓ Saved SDK keys to .env")
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()

@cli.command()
@click.option('--format', '-f', type=click.Choice(['table', 'json', 'csv']), default='table')
@click.option('--filter-tag', help='Filter by tag')
@click.pass_obj
def list(pm, format, filter_tag):
    """List all projects."""
    try:
        projects = pm.list_projects()
        
        if filter_tag:
            projects = [p for p in projects if filter_tag in p.get('tags', [])]
        
        if format == 'json':
            click.echo(json.dumps(projects, indent=2))
        elif format == 'csv':
            click.echo("key,name,tags")
            for p in projects:
                tags = ','.join(p.get('tags', []))
                click.echo(f"{p['key']},{p['name']},{tags}")
        else:  # table
            rows = [[p['key'], p['name'], ', '.join(p.get('tags', []))] for p in projects]
            click.echo(tabulate(rows, headers=['Key', 'Name', 'Tags']))
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()

@cli.command()
@click.argument('project_key')
@click.option('--env', default='production', help='Environment')
@click.option('--show-key/--mask-key', default=False, help='Show full key')
@click.pass_obj
def get_key(pm, project_key, env, show_key):
    """Get SDK key for a project."""
    try:
        sdk_key = pm.get_sdk_key(project_key, env)
        if sdk_key:
            if show_key:
                click.echo(sdk_key)
            else:
                click.echo(f"{sdk_key[:10]}...{sdk_key[-4:]}")
        else:
            click.echo(f"✗ Environment '{env}' not found", err=True)
            raise click.Abort()
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()

@cli.command()
@click.argument('source_key')
@click.argument('new_key')
@click.argument('new_name')
@click.option('--tags', '-t', multiple=True, help='Additional tags')
@click.pass_obj
def clone(pm, source_key, new_key, new_name, tags):
    """Clone an existing project."""
    try:
        from launchdarkly.cloning import clone_project
        project = clone_project(source_key, new_name, new_key, list(tags))
        click.echo(f"✓ Cloned {source_key} → {new_key}")
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()

@cli.command()
@click.argument('project_key')
@click.option('--environments', '-e', multiple=True, default=['production', 'test'])
@click.option('--output', '-o', type=click.File('w'), default='-')
@click.pass_obj
def export_keys(pm, project_key, environments, output):
    """Export SDK keys for all environments."""
    try:
        keys = {}
        for env in environments:
            sdk_key = pm.get_sdk_key(project_key, env)
            if sdk_key:
                keys[env] = sdk_key
        
        output.write(json.dumps(keys, indent=2))
        output.write('\n')
        click.echo(f"✓ Exported keys for {project_key}", err=True)
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()

@cli.command()
@click.argument('csv_file', type=click.File('r'))
@click.option('--dry-run/--execute', default=True)
@click.pass_obj
def bulk_create(pm, csv_file, dry_run):
    """Create multiple projects from CSV file."""
    import csv
    
    reader = csv.DictReader(csv_file)
    for row in reader:
        key = row['key']
        name = row['name']
        tags = row.get('tags', '').split(',') if row.get('tags') else []
        
        if dry_run:
            click.echo(f"Would create: {key} ({name})")
        else:
            try:
                project = pm.create_project(name, key, tags)
                click.echo(f"✓ Created: {key}")
            except Exception as e:
                click.echo(f"✗ Failed to create {key}: {e}", err=True)

@cli.command()
@click.pass_obj
def audit(pm):
    """Audit all projects and show statistics."""
    try:
        projects = pm.list_projects()
        
        # Gather statistics
        total = len(projects)
        tags_count = {}
        for p in projects:
            for tag in p.get('tags', []):
                tags_count[tag] = tags_count.get(tag, 0) + 1
        
        click.echo(f"\n📊 Project Audit Report\n")
        click.echo(f"Total projects: {total}")
        click.echo(f"\nTag distribution:")
        for tag, count in sorted(tags_count.items(), key=lambda x: x[1], reverse=True):
            click.echo(f"  {tag}: {count}")
        
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise click.Abort()

if __name__ == '__main__':
    cli()
```

**Install dependencies:**
```bash
pip install click tabulate
```

**Usage:**
```bash
# Create project
python cli/ldprojects.py create "My Agent" my-ai -t ai-configs -t production

# List projects
python cli/ldprojects.py list
python cli/ldprojects.py list --format json
python cli/ldprojects.py list --filter-tag ai-configs

# Get SDK key
python cli/ldprojects.py get-key my-ai
python cli/ldprojects.py get-key my-ai --env test --show-key

# Clone project
python cli/ldprojects.py clone template-ai new-ai "New Agent Project"

# Export keys
python cli/ldprojects.py export-keys my-ai -o keys.json

# Bulk create
python cli/ldprojects.py bulk-create projects.csv --execute

# Audit
python cli/ldprojects.py audit
```

## Web Admin Dashboard

Build a simple web dashboard:

### Flask Dashboard

```python
# admin/app.py
from flask import Flask, render_template, request, redirect, jsonify
from launchdarkly.projects import ProjectManager

app = Flask(__name__)
pm = ProjectManager()

@app.route('/')
def index():
    projects = pm.list_projects()
    return render_template('index.html', projects=projects)

@app.route('/projects', methods=['POST'])
def create_project():
    data = request.json
    project = pm.create_project(
        name=data['name'],
        key=data['key'],
        tags=data.get('tags', [])
    )
    return jsonify(project)

@app.route('/projects/<key>')
def project_detail(key):
    project = pm.get_project(key)
    return render_template('project.html', project=project)

@app.route('/projects/<key>/keys/<env>')
def get_sdk_key(key, env):
    sdk_key = pm.get_sdk_key(key, env)
    return jsonify({'sdkKey': sdk_key})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

**templates/index.html:**
```html
<!DOCTYPE html>
<html>
<head>
    <title>LaunchDarkly Projects Admin</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .project { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
        .tags { color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <h1>LaunchDarkly Projects</h1>
    
    <h2>Create New Project</h2>
    <form id="createForm">
        <input type="text" name="name" placeholder="Project Name" required>
        <input type="text" name="key" placeholder="project-key" required>
        <input type="text" name="tags" placeholder="tag1,tag2">
        <button type="submit">Create</button>
    </form>
    
    <h2>Existing Projects</h2>
    {% for project in projects %}
    <div class="project">
        <h3><a href="/projects/{{ project.key }}">{{ project.name }}</a></h3>
        <p><strong>Key:</strong> {{ project.key }}</p>
        <p class="tags"><strong>Tags:</strong> {{ project.tags|join(', ') }}</p>
    </div>
    {% endfor %}
    
    <script>
        document.getElementById('createForm').onsubmit = async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const data = {
                name: formData.get('name'),
                key: formData.get('key'),
                tags: formData.get('tags').split(',').filter(t => t.trim())
            };
            
            const resp = await fetch('/projects', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            
            if (resp.ok) {
                location.reload();
            } else {
                alert('Failed to create project');
            }
        };
    </script>
</body>
</html>
```

**Run the dashboard:**
```bash
pip install flask
python admin/app.py
# Visit http://localhost:5000
```

## Monitoring & Alerting

Monitor project creation and usage:

```python
# monitoring/project_monitor.py
import time
from datetime import datetime
from launchdarkly.projects import ProjectManager

class ProjectMonitor:
    """Monitor LaunchDarkly projects for changes."""
    
    def __init__(self):
        self.pm = ProjectManager()
        self.known_projects = set()
    
    def check_for_new_projects(self):
        """Check for newly created projects."""
        projects = self.pm.list_projects()
        current_keys = {p['key'] for p in projects}
        
        new_projects = current_keys - self.known_projects
        if new_projects:
            self.on_new_projects(new_projects, projects)
        
        self.known_projects = current_keys
    
    def on_new_projects(self, new_keys, all_projects):
        """Handle new projects."""
        for key in new_keys:
            project = next(p for p in all_projects if p['key'] == key)
            print(f"[{datetime.now()}] New project detected: {project['name']} ({key})")
            # Send alert, log to DB, etc.
    
    def run(self, interval=60):
        """Run monitor continuously."""
        print(f"Starting project monitor (interval: {interval}s)")
        while True:
            try:
                self.check_for_new_projects()
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(interval)

if __name__ == '__main__':
    monitor = ProjectMonitor()
    monitor.run()
```

## Backup & Recovery

Backup project configurations:

```python
# backup/project_backup.py
import json
from datetime import datetime
from launchdarkly.projects import ProjectManager

def backup_all_projects(output_file=None):
    """Backup all projects to JSON file."""
    pm = ProjectManager()
    projects = pm.list_projects()
    
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"projects_backup_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(projects, f, indent=2)
    
    print(f"✓ Backed up {len(projects)} projects to {output_file}")
    return output_file

def restore_projects(backup_file):
    """Restore projects from backup (creates if missing)."""
    pm = ProjectManager()
    
    with open(backup_file, 'r') as f:
        projects = json.load(f)
    
    for project in projects:
        try:
            pm.create_project(
                name=project['name'],
                key=project['key'],
                tags=project.get('tags', [])
            )
            print(f"✓ Restored: {project['key']}")
        except Exception as e:
            print(f"✗ Failed to restore {project['key']}: {e}")

# Usage
backup_all_projects()
# restore_projects('projects_backup_20260205_120000.json')
```

## Integration with Terraform

Export projects to Terraform format:

```python
# terraform/export_terraform.py
def export_to_terraform(project_keys=None):
    """Export projects as Terraform configuration."""
    pm = ProjectManager()
    projects = pm.list_projects()
    
    if project_keys:
        projects = [p for p in projects if p['key'] in project_keys]
    
    tf_config = []
    for project in projects:
        resource_name = project['key'].replace('-', '_')
        tags = ', '.join(f'"{tag}"' for tag in project.get('tags', []))
        
        tf_config.append(f'''
resource "launchdarkly_project" "{resource_name}" {{
  key  = "{project['key']}"
  name = "{project['name']}"
  tags = [{tags}]
}}
''')
    
    output = '\n'.join(tf_config)
    with open('projects.tf', 'w') as f:
        f.write(output)
    
    print(f"✓ Exported {len(projects)} projects to projects.tf")

# Usage
export_to_terraform()
```

## Slack Integration

Send notifications to Slack:

```python
# integrations/slack_notifier.py
import requests

def notify_slack(webhook_url, message):
    """Send notification to Slack."""
    requests.post(webhook_url, json={'text': message})

def notify_project_created(project, webhook_url):
    """Notify Slack when project is created."""
    message = f"🎉 New LaunchDarkly project created: *{project['name']}* (`{project['key']}`)"
    notify_slack(webhook_url, message)

# Usage in CLI
@cli.command()
@click.argument('name')
@click.argument('key')
@click.option('--slack-webhook', envvar='SLACK_WEBHOOK_URL')
@click.pass_obj
def create_with_notification(pm, name, key, slack_webhook):
    """Create project and notify Slack."""
    project = pm.create_project(name, key, [])
    click.echo(f"✓ Created: {project['name']}")
    
    if slack_webhook:
        notify_project_created(project, slack_webhook)
        click.echo("✓ Notified Slack")
```

## Next Steps

- [Set up IaC automation](iac-automation.md)
- [Configure project cloning](project-cloning.md)
- [Manage SDK keys](env-config.md)
