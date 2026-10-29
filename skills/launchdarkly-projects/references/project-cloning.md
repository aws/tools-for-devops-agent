# Project Cloning

Patterns for cloning projects across regions, teams, or environments.

## Use Cases

- **Multi-region deployments:** Clone project structure for US, EU, APAC regions
- **Multi-tenant applications:** Separate project per customer/tenant
- **Team isolation:** Clone template for different teams
- **Environment parity:** Ensure dev/staging/prod have identical structure

## Basic Cloning Pattern

### Python
```python
def clone_project(source_key: str, new_name: str, new_key: str, tags: List[str] = None) -> Dict:
    """
    Clone a project's structure (metadata only, not flags/configs).
    
    Args:
        source_key: The project to copy settings from
        new_name: Name for the new project
        new_key: Unique key for the new project
        tags: Optional tags (defaults to source tags + 'cloned')
        
    Returns:
        The newly created project
    """
    pm = ProjectManager()
    
    # Get source project settings
    source = pm.get_project(source_key)
    if not source:
        raise ValueError(f"Source project '{source_key}' not found")
    
    # Prepare new project with same settings
    source_tags = source.get("tags", [])
    new_tags = tags or (source_tags + ["cloned"])
    
    # Create new project
    return pm.create_project(
        name=new_name,
        key=new_key,
        tags=new_tags
    )
```

### TypeScript
```typescript
async function cloneProject(
  sourceKey: string,
  newName: string,
  newKey: string,
  tags?: string[]
): Promise<Project> {
  const pm = new ProjectManager();
  
  // Get source project settings
  const source = await pm.getProject(sourceKey);
  if (!source) {
    throw new Error(`Source project '${sourceKey}' not found`);
  }
  
  // Prepare new project with same settings
  const sourceTags = source.tags || [];
  const newTags = tags || [...sourceTags, 'cloned'];
  
  // Create new project
  return pm.createProject({
    name: newName,
    key: newKey,
    tags: newTags,
  });
}
```

## Multi-Region Cloning

Clone a project for multiple regions:

```python
def clone_for_regions(base_project: str, regions: List[str]):
    """
    Clone a project for multiple regions.
    
    Example:
        clone_for_regions("ai-service", ["us", "eu", "apac"])
        Creates: ai-service-us, ai-service-eu, ai-service-apac
    """
    pm = ProjectManager()
    base = pm.get_project(base_project)
    
    if not base:
        raise ValueError(f"Base project '{base_project}' not found")
    
    created_projects = []
    
    for region in regions:
        new_key = f"{base_project}-{region}"
        new_name = f"{base['name']} - {region.upper()}"
        
        print(f"Creating {new_key}...")
        project = clone_project(
            source_key=base_project,
            new_name=new_name,
            new_key=new_key,
            tags=base.get("tags", []) + [f"region:{region}"]
        )
        
        created_projects.append(project)
        print(f"✓ Created {new_key}")
    
    return created_projects

# Usage
clone_for_regions("customer-ai", ["us", "eu", "apac"])
```

**Result:**
- `customer-ai-us` - Customer Agent - US
- `customer-ai-eu` - Customer Agent - EU
- `customer-ai-apac` - Customer Agent - APAC

## Multi-Tenant Cloning

Clone for different tenants/customers:

```typescript
interface Tenant {
  id: string;
  name: string;
}

async function cloneForTenants(
  baseProject: string,
  tenants: Tenant[]
): Promise<Project[]> {
  const pm = new ProjectManager();
  const base = await pm.getProject(baseProject);
  
  if (!base) {
    throw new Error(`Base project '${baseProject}' not found`);
  }
  
  const createdProjects: Project[] = [];
  
  for (const tenant of tenants) {
    const newKey = `${baseProject}-${tenant.id}`;
    const newName = `${base.name} - ${tenant.name}`;
    
    console.log(`Creating ${newKey}...`);
    const project = await cloneProject(
      baseProject,
      newName,
      newKey,
      [...(base.tags || []), `tenant:${tenant.id}`]
    );
    
    createdProjects.push(project);
    console.log(`✓ Created ${newKey}`);
  }
  
  return createdProjects;
}

// Usage
const tenants = [
  { id: 'acme', name: 'Acme Corp' },
  { id: 'globex', name: 'Globex Inc' },
  { id: 'initech', name: 'Initech' },
];

cloneForTenants('saas-ai', tenants);
```

**Result:**
- `saas-ai-acme` - SaaS Agent - Acme Corp
- `saas-ai-globex` - SaaS Agent - Globex Inc
- `saas-ai-initech` - SaaS Agent - Initech

## Team-Based Cloning

Clone template project for multiple teams:

```python
def clone_for_teams(template_project: str, teams: List[str]):
    """
    Clone a template project for multiple teams.
    
    Example:
        clone_for_teams("ai-template", ["platform", "customer", "product"])
    """
    pm = ProjectManager()
    template = pm.get_project(template_project)
    
    if not template:
        raise ValueError(f"Template project '{template_project}' not found")
    
    created_projects = []
    
    for team in teams:
        new_key = f"{team}-ai"
        new_name = f"{team.title()} Team Agent"
        
        print(f"Creating {new_key} for {team} team...")
        project = clone_project(
            source_key=template_project,
            new_name=new_name,
            new_key=new_key,
            tags=["ai-configs", f"team:{team}"]
        )
        
        # Save SDK keys for team
        save_sdk_key_to_env(
            new_key,
            "production",
            env_file=f".env.{team}",
            var_name="LD_SDK_KEY"
        )
        
        created_projects.append(project)
        print(f"✓ Created {new_key}")
    
    return created_projects

# Usage
clone_for_teams("ai-template", ["platform", "customer", "product"])
```

## Bulk Cloning with CSV

Clone from a CSV file with project specifications:

```python
import csv

def clone_from_csv(source_key: str, csv_file: str):
    """
    Clone projects from CSV file.
    
    CSV format:
        project_key,project_name,tags
        mobile-ai-us,Mobile Agent US,"mobile,us,production"
        mobile-ai-eu,Mobile Agent EU,"mobile,eu,production"
    """
    pm = ProjectManager()
    created_projects = []
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row['project_key']
            name = row['project_name']
            tags = row.get('tags', '').split(',') if row.get('tags') else []
            
            print(f"Creating {key}...")
            project = clone_project(source_key, name, key, tags)
            created_projects.append(project)
            print(f"✓ Created {key}")
    
    return created_projects

# Usage
clone_from_csv("ai-template", "projects.csv")
```

**projects.csv:**
```csv
project_key,project_name,tags
mobile-ai-us,Mobile Agent US,"mobile,us,production"
mobile-ai-eu,Mobile Agent EU,"mobile,eu,production"
web-ai-us,Web Agent US,"web,us,production"
web-ai-eu,Web Agent EU,"web,eu,production"
```

## Automated SDK Key Management

After cloning, automatically save SDK keys:

```python
def clone_and_configure(
    source_key: str,
    new_key: str,
    new_name: str,
    env_file: str = None
):
    """Clone project and automatically save SDK keys."""
    # Clone the project
    project = clone_project(source_key, new_name, new_key)
    print(f"✓ Cloned {source_key} → {new_key}")
    
    # Save SDK keys for both environments
    env_file = env_file or f".env.{new_key}"
    
    for environment in ["production", "test"]:
        var_name = f"LD_SDK_KEY_{environment.upper()}"
        save_sdk_key_to_env(new_key, environment, env_file, var_name)
    
    print(f"✓ Saved SDK keys to {env_file}")
    
    return project
```

## Parallel Cloning

Clone multiple projects in parallel for speed:

```python
import concurrent.futures

def clone_projects_parallel(clones: List[Dict[str, str]], max_workers: int = 5):
    """
    Clone multiple projects in parallel.
    
    Args:
        clones: List of dicts with keys: source_key, new_key, new_name
        max_workers: Max parallel requests
    """
    def clone_single(clone_spec):
        return clone_project(
            source_key=clone_spec['source_key'],
            new_name=clone_spec['new_name'],
            new_key=clone_spec['new_key']
        )
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(clone_single, spec): spec for spec in clones}
        
        results = []
        for future in concurrent.futures.as_completed(futures):
            spec = futures[future]
            try:
                project = future.result()
                print(f"✓ Cloned {spec['new_key']}")
                results.append(project)
            except Exception as e:
                print(f"✗ Failed to clone {spec['new_key']}: {e}")
        
        return results

# Usage
clones = [
    {"source_key": "template", "new_key": "team-a-ai", "new_name": "Team A Agent"},
    {"source_key": "template", "new_key": "team-b-ai", "new_name": "Team B Agent"},
    {"source_key": "template", "new_key": "team-c-ai", "new_name": "Team C Agent"},
]

clone_projects_parallel(clones)
```

## Cloning with MCP Server

If using the LaunchDarkly MCP server:

```typescript
// Note: MCP server may not have clone functionality
// You would create projects individually

async function cloneWithMCP(sourceKey: string, newKey: string, newName: string) {
  // Get source project via MCP
  const source = await mcp.getProject(sourceKey);
  
  // Create new project with same settings
  const project = await mcp.createProject({
    name: newName,
    key: newKey,
    tags: [...(source.tags || []), 'cloned'],
  });
  
  return project;
}
```

## Best Practices

### 1. Naming Conventions
Use consistent naming across clones:
```
{base}-{region}        →  ai-service-us, ai-service-eu
{team}-{service}       →  platform-ai, customer-ai
{service}-{tenant}     →  saas-acme, saas-globex
```

### 2. Tagging Strategy
Tag clones for easy filtering:
```python
tags = [
    "ai-configs",
    f"region:{region}",
    f"cloned-from:{source_key}",
    f"created:{datetime.now().isoformat()}"
]
```

### 3. Documentation
Document cloning relationships:
```python
def clone_with_metadata(source_key: str, new_key: str, new_name: str):
    """Clone and document the relationship."""
    project = clone_project(source_key, new_name, new_key)
    
    # Create a mapping file
    with open("project-clones.json", "a") as f:
        f.write(json.dumps({
            "source": source_key,
            "clone": new_key,
            "created_at": datetime.now().isoformat()
        }) + "\n")
    
    return project
```

### 4. Verification
Verify clones after creation:
```python
def verify_clones(clones: List[str]):
    """Verify all cloned projects exist and have SDK keys."""
    pm = ProjectManager()
    
    for project_key in clones:
        project = pm.get_project(project_key)
        if not project:
            print(f"✗ {project_key} not found")
            continue
        
        sdk_key = pm.get_sdk_key(project_key, "production")
        if sdk_key:
            print(f"✓ {project_key} verified")
        else:
            print(f"⚠️  {project_key} missing SDK key")
```

## Next Steps

- [Save SDK keys for cloned projects](env-config.md)
- [Automate with IaC](iac-automation.md)
- [Build admin tooling](admin-tooling.md)
