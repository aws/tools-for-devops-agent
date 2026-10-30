# Python Project Setup

Implementation patterns for Python applications using the LaunchDarkly API.

## Prerequisites

```bash
pip install requests python-dotenv
```

## Basic Project Management Module

Create a reusable module for project operations:

```python
# launchdarkly/projects.py
import os
import requests
from typing import Optional, Dict, List

API_TOKEN = os.environ.get("LAUNCHDARKLY_API_TOKEN")
BASE_URL = "https://app.launchdarkly.com/api/v2"


class ProjectManager:
    """Manage LaunchDarkly projects via API."""
    
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or API_TOKEN
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json"
        }
    
    def create_project(self, name: str, key: str, tags: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Create a new LaunchDarkly project.
        
        Args:
            name: Human-readable project name
            key: Unique identifier (lowercase, hyphens only)
            tags: Optional list of tags
            
        Returns:
            Project dict if successful, None otherwise
        """
        payload = {"name": name, "key": key}
        if tags:
            payload["tags"] = tags
        
        response = requests.post(
            f"{BASE_URL}/projects",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code == 201:
            return response.json()
        elif response.status_code == 409:
            print(f"Project '{key}' already exists")
            return self.get_project(key)
        else:
            print(f"Error: {response.text}")
            return None
    
    def get_project(self, project_key: str) -> Optional[Dict]:
        """Get project with environments expanded."""
        response = requests.get(
            f"{BASE_URL}/projects/{project_key}",
            headers=self.headers,
            params={"expand": "environments"}
        )
        return response.json() if response.status_code == 200 else None
    
    def get_sdk_key(self, project_key: str, environment: str = "production") -> Optional[str]:
        """Get SDK key for a specific environment."""
        project = self.get_project(project_key)
        if not project:
            return None
        
        envs = project.get("environments", {})
        env_items = envs.get("items", []) if isinstance(envs, dict) else envs
        
        for env in env_items:
            if env["key"] == environment:
                return env["apiKey"]
        
        return None
    
    def list_projects(self) -> List[Dict]:
        """List all projects in organization."""
        response = requests.get(
            f"{BASE_URL}/projects",
            headers=self.headers
        )
        return response.json().get("items", []) if response.status_code == 200 else []
```

## Usage Examples

### Create a Project
```python
from launchdarkly.projects import ProjectManager

pm = ProjectManager()

# Create new project
project = pm.create_project(
    name="Customer Support Agent",
    key="support-ai",
    tags=["ai-configs", "production"]
)

if project:
    print(f"Created project: {project['key']}")
```

### Get SDK Key
```python
pm = ProjectManager()

# Get production SDK key
sdk_key = pm.get_sdk_key("support-ai", "production")
print(f"Production SDK Key: {sdk_key}")

# Get test SDK key
test_sdk_key = pm.get_sdk_key("support-ai", "test")
print(f"Test SDK Key: {test_sdk_key}")
```

### List Projects
```python
pm = ProjectManager()

projects = pm.list_projects()
for project in projects:
    print(f"- {project['name']} ({project['key']})")
```

## FastAPI Integration

If you're using FastAPI, integrate project management into your app:

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    launchdarkly_api_token: str
    launchdarkly_sdk_key: str
    
    class Config:
        env_file = ".env"

settings = Settings()


# app/main.py
from fastapi import FastAPI
from launchdarkly.projects import ProjectManager
from .config import settings

app = FastAPI()
pm = ProjectManager(api_token=settings.launchdarkly_api_token)

@app.on_event("startup")
async def startup():
    # Ensure project exists
    project = pm.create_project(
        name="My API Service",
        key="api-service"
    )
    if project:
        print(f"LaunchDarkly project ready: {project['key']}")
```

## Django Integration

For Django applications:

```python
# settings.py
import os
from launchdarkly.projects import ProjectManager

LAUNCHDARKLY_API_TOKEN = os.environ.get("LAUNCHDARKLY_API_TOKEN")
LAUNCHDARKLY_PROJECT_KEY = os.environ.get("LAUNCHDARKLY_PROJECT_KEY", "django-app")

# Ensure project exists on startup
pm = ProjectManager(api_token=LAUNCHDARKLY_API_TOKEN)
project = pm.create_project(
    name="Django Application",
    key=LAUNCHDARKLY_PROJECT_KEY
)

LD_SDK_KEY = pm.get_sdk_key(LAUNCHDARKLY_PROJECT_KEY, "production")
```

## CLI Tool

Create a management CLI for project operations:

```python
# cli/ld_projects.py
import click
from launchdarkly.projects import ProjectManager

@click.group()
def cli():
    """LaunchDarkly project management CLI."""
    pass

@cli.command()
@click.argument("name")
@click.argument("key")
@click.option("--tags", multiple=True, help="Project tags")
def create(name: str, key: str, tags: tuple):
    """Create a new project."""
    pm = ProjectManager()
    project = pm.create_project(name, key, list(tags))
    if project:
        click.echo(f"✓ Created: {project['name']} ({project['key']})")

@cli.command()
def list():
    """List all projects."""
    pm = ProjectManager()
    projects = pm.list_projects()
    for project in projects:
        click.echo(f"- {project['name']} ({project['key']})")

@cli.command()
@click.argument("project_key")
@click.option("--env", default="production", help="Environment")
def get_key(project_key: str, env: str):
    """Get SDK key for a project environment."""
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, env)
    if sdk_key:
        click.echo(sdk_key)

if __name__ == "__main__":
    cli()
```

**Usage:**
```bash
python cli/ld_projects.py create "My Agent" my-ai --tags ai-configs
python cli/ld_projects.py list
python cli/ld_projects.py get-key my-ai --env production
```

## Error Handling

Add robust error handling for production use:

```python
class LaunchDarklyError(Exception):
    """Base exception for LaunchDarkly operations."""
    pass

class ProjectManager:
    def create_project(self, name: str, key: str, tags: Optional[List[str]] = None) -> Dict:
        """Create project with error handling."""
        try:
            response = requests.post(
                f"{BASE_URL}/projects",
                headers=self.headers,
                json={"name": name, "key": key, "tags": tags or []},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                # Project exists, return existing
                return self.get_project(key)
            elif e.response.status_code == 401:
                raise LaunchDarklyError("Invalid API token")
            elif e.response.status_code == 403:
                raise LaunchDarklyError("Insufficient permissions (need projects:write)")
            else:
                raise LaunchDarklyError(f"API error: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise LaunchDarklyError(f"Request failed: {str(e)}")
```

## Testing

Mock the API for unit tests:

```python
# tests/test_projects.py
import pytest
from unittest.mock import Mock, patch
from launchdarkly.projects import ProjectManager

@pytest.fixture
def mock_response():
    mock = Mock()
    mock.status_code = 201
    mock.json.return_value = {
        "name": "Test Project",
        "key": "test-project"
    }
    return mock

@patch("requests.post")
def test_create_project(mock_post, mock_response):
    mock_post.return_value = mock_response
    
    pm = ProjectManager(api_token="test-token")
    project = pm.create_project("Test Project", "test-project")
    
    assert project["key"] == "test-project"
    mock_post.assert_called_once()
```

## Next Steps

- [Save SDK keys to .env](env-config.md)
- [Clone projects for different environments](project-cloning.md)
- [Build admin tooling](admin-tooling.md)
