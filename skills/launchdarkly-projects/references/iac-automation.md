# Infrastructure as Code (IaC) Automation

Automate project management using IaC tools and CI/CD pipelines.

## Terraform

### LaunchDarkly Terraform Provider

Install and configure the LaunchDarkly Terraform provider:

```hcl
# terraform/main.tf
terraform {
  required_providers {
    launchdarkly = {
      source  = "launchdarkly/launchdarkly"
      version = "~> 2.0"
    }
  }
}

provider "launchdarkly" {
  access_token = var.launchdarkly_access_token
}
```

### Define Projects

```hcl
# terraform/projects.tf
variable "launchdarkly_access_token" {
  description = "LaunchDarkly API access token"
  type        = string
  sensitive   = true
}

resource "launchdarkly_project" "customer_ai" {
  key  = "customer-ai"
  name = "Customer Agent Service"
  tags = ["ai-configs", "production", "terraform"]
}

resource "launchdarkly_project" "platform_ai" {
  key  = "platform-ai"
  name = "Platform Agent Service"
  tags = ["ai-configs", "production", "terraform"]
}

# Output SDK keys
output "customer_ai_sdk_key_production" {
  value     = launchdarkly_project.customer_ai.environments[0].api_key
  sensitive = true
}

output "customer_ai_sdk_key_test" {
  value     = launchdarkly_project.customer_ai.environments[1].api_key
  sensitive = true
}
```

### Custom Environments

```hcl
resource "launchdarkly_project" "my_project" {
  key  = "my-project"
  name = "My Project"

  environments = [
    {
      key   = "production"
      name  = "Production"
      color = "FF0000"
    },
    {
      key   = "staging"
      name  = "Staging"
      color = "FFA500"
    },
    {
      key   = "development"
      name  = "Development"
      color = "00FF00"
    }
  ]
}
```

### Apply Terraform

```bash
# Initialize
terraform init

# Plan changes
terraform plan -var="launchdarkly_access_token=$LAUNCHDARKLY_API_TOKEN"

# Apply
terraform apply -var="launchdarkly_access_token=$LAUNCHDARKLY_API_TOKEN"

# Get SDK key
terraform output -raw customer_ai_sdk_key_production
```

### Save SDK Keys to Files

```hcl
# Save SDK keys to local files (for development only)
resource "local_file" "sdk_key_production" {
  content  = launchdarkly_project.customer_ai.environments[0].api_key
  filename = "${path.module}/.env.production"
  
  # Don't commit these files!
  provisioner "local-exec" {
    command = "echo '.env.production' >> .gitignore"
  }
}
```

## GitHub Actions

Automate project creation in CI/CD:

### Create Project on Deploy

```yaml
# .github/workflows/setup-launchdarkly.yml
name: Setup LaunchDarkly Project

on:
  workflow_dispatch:
    inputs:
      project_key:
        description: 'Project key'
        required: true
      project_name:
        description: 'Project name'
        required: true

jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install requests python-dotenv
      
      - name: Create LaunchDarkly Project
        env:
          LAUNCHDARKLY_API_TOKEN: ${{ secrets.LAUNCHDARKLY_API_TOKEN }}
        run: |
          python scripts/create_project.py \
            --name "${{ github.event.inputs.project_name }}" \
            --key "${{ github.event.inputs.project_key }}" \
            --tags "github-actions,automated"
      
      - name: Save SDK Keys to Secrets
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PROJECT_KEY: ${{ github.event.inputs.project_key }}
        run: |
          SDK_KEY=$(python scripts/get_sdk_key.py $PROJECT_KEY production)
          gh secret set LD_SDK_KEY --body "$SDK_KEY"
```

### Automated Project Creation on New Service

```yaml
# .github/workflows/new-service.yml
name: New Service Setup

on:
  create:
    branches:
      - 'service/*'

jobs:
  setup-project:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Extract service name
        id: service
        run: |
          BRANCH_NAME="${{ github.ref }}"
          SERVICE_NAME="${BRANCH_NAME#refs/heads/service/}"
          echo "name=$SERVICE_NAME" >> $GITHUB_OUTPUT
          echo "key=${SERVICE_NAME//_/-}" >> $GITHUB_OUTPUT
      
      - name: Create LaunchDarkly Project
        env:
          LAUNCHDARKLY_API_TOKEN: ${{ secrets.LAUNCHDARKLY_API_TOKEN }}
        run: |
          python scripts/create_project.py \
            --name "${{ steps.service.outputs.name }} Service" \
            --key "${{ steps.service.outputs.key }}-service" \
            --tags "service,automated"
```

## GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - setup
  - deploy

setup-launchdarkly:
  stage: setup
  image: python:3.11
  script:
    - pip install requests
    - |
      python -c "
      from launchdarkly.projects import ProjectManager
      pm = ProjectManager('$LAUNCHDARKLY_API_TOKEN')
      project = pm.create_project(
          name='$CI_PROJECT_NAME',
          key='$CI_PROJECT_NAME',
          tags=['gitlab-ci', '$CI_ENVIRONMENT_NAME']
      )
      sdk_key = pm.get_sdk_key('$CI_PROJECT_NAME', 'production')
      print(f'SDK_KEY={sdk_key}')
      " > .env.production
  artifacts:
    paths:
      - .env.production
    expire_in: 1 day
  only:
    - main
```

## CircleCI

```yaml
# .circleci/config.yml
version: 2.1

jobs:
  setup-launchdarkly:
    docker:
      - image: cimg/python:3.11
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: pip install requests
      - run:
          name: Create LaunchDarkly project
          command: |
            python scripts/create_project.py \
              --name "$CIRCLE_PROJECT_REPONAME" \
              --key "$CIRCLE_PROJECT_REPONAME" \
              --tags "circleci,automated"
      - run:
          name: Save SDK key
          command: |
            SDK_KEY=$(python scripts/get_sdk_key.py $CIRCLE_PROJECT_REPONAME production)
            echo "export LD_SDK_KEY='$SDK_KEY'" >> $BASH_ENV

workflows:
  setup:
    jobs:
      - setup-launchdarkly
```

## Ansible

Manage projects with Ansible:

```yaml
# playbooks/setup-launchdarkly.yml
---
- name: Setup LaunchDarkly Projects
  hosts: localhost
  vars:
    launchdarkly_api_token: "{{ lookup('env', 'LAUNCHDARKLY_API_TOKEN') }}"
    projects:
      - name: "Customer Agent Service"
        key: "customer-ai"
        tags: ["ai-configs", "production"]
      - name: "Platform Agent Service"
        key: "platform-ai"
        tags: ["ai-configs", "production"]
  
  tasks:
    - name: Create LaunchDarkly projects
      uri:
        url: "https://app.launchdarkly.com/api/v2/projects"
        method: POST
        headers:
          Authorization: "{{ launchdarkly_api_token }}"
          Content-Type: "application/json"
        body_format: json
        body:
          name: "{{ item.name }}"
          key: "{{ item.key }}"
          tags: "{{ item.tags }}"
        status_code: [201, 409]
      loop: "{{ projects }}"
      register: project_results
    
    - name: Get SDK keys
      uri:
        url: "https://app.launchdarkly.com/api/v2/projects/{{ item.key }}?expand=environments"
        method: GET
        headers:
          Authorization: "{{ launchdarkly_api_token }}"
      loop: "{{ projects }}"
      register: sdk_keys
    
    - name: Save SDK keys to .env
      copy:
        content: |
          LD_SDK_KEY={{ item.json.environments.items[0].apiKey }}
        dest: ".env.{{ item.item.key }}"
      loop: "{{ sdk_keys.results }}"
      no_log: true
```

**Run playbook:**
```bash
ansible-playbook playbooks/setup-launchdarkly.yml
```

## Pulumi

Infrastructure as code with Pulumi:

### Python

```python
# __main__.py
import pulumi
import pulumi_launchdarkly as launchdarkly

# Create projects
customer_ai = launchdarkly.Project(
    "customer-ai",
    key="customer-ai",
    name="Customer Agent Service",
    tags=["ai-configs", "production", "pulumi"]
)

platform_ai = launchdarkly.Project(
    "platform-ai",
    key="platform-ai",
    name="Platform Agent Service",
    tags=["ai-configs", "production", "pulumi"]
)

# Export SDK keys
pulumi.export("customer_ai_sdk_key_prod", customer_ai.environments[0]["api_key"])
pulumi.export("customer_ai_sdk_key_test", customer_ai.environments[1]["api_key"])
```

### TypeScript

```typescript
// index.ts
import * as pulumi from "@pulumi/pulumi";
import * as launchdarkly from "@pulumi/launchdarkly";

// Create projects
const customerAi = new launchdarkly.Project("customer-ai", {
    key: "customer-ai",
    name: "Customer Agent Service",
    tags: ["ai-configs", "production", "pulumi"],
});

const platformAi = new launchdarkly.Project("platform-ai", {
    key: "platform-ai",
    name: "Platform Agent Service",
    tags: ["ai-configs", "production", "pulumi"],
});

// Export SDK keys
export const customerAiSdkKeyProd = customerAi.environments[0].apiKey;
export const customerAiSdkKeyTest = customerAi.environments[1].apiKey;
```

**Deploy:**
```bash
pulumi up
pulumi stack output customerAiSdkKeyProd
```

## Docker Compose

Initialize projects in Docker setup:

```yaml
# docker-compose.yml
version: '3.8'

services:
  setup-launchdarkly:
    image: python:3.11-slim
    environment:
      - LAUNCHDARKLY_API_TOKEN=${LAUNCHDARKLY_API_TOKEN}
    volumes:
      - ./scripts:/scripts
      - ./.env.production:/output/.env
    command: >
      sh -c "
        pip install requests &&
        python /scripts/create_project.py --name 'My Service' --key my-service &&
        python /scripts/save_sdk_key.py my-service production > /output/.env
      "
  
  app:
    build: .
    depends_on:
      - setup-launchdarkly
    env_file:
      - .env.production
```

## Kubernetes Operator

Custom operator to manage projects:

```yaml
# k8s/launchdarkly-project.yaml
apiVersion: launchdarkly.com/v1
kind: Project
metadata:
  name: customer-ai
spec:
  key: customer-ai
  name: Customer Agent Service
  tags:
    - ai-configs
    - production
    - kubernetes
  secretName: launchdarkly-sdk-keys
```

**Operator implementation (Python):**
```python
# operator/controller.py
import kopf
from launchdarkly.projects import ProjectManager
from kubernetes import client, config

@kopf.on.create('launchdarkly.com', 'v1', 'projects')
def create_project(spec, name, namespace, **kwargs):
    """Handle Project creation."""
    pm = ProjectManager()
    
    # Create project
    project = pm.create_project(
        name=spec['name'],
        key=spec['key'],
        tags=spec.get('tags', [])
    )
    
    # Get SDK keys
    sdk_key_prod = pm.get_sdk_key(spec['key'], 'production')
    sdk_key_test = pm.get_sdk_key(spec['key'], 'test')
    
    # Create Kubernetes Secret
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    
    secret = client.V1Secret(
        metadata=client.V1ObjectMeta(
            name=spec.get('secretName', f"{name}-sdk-keys"),
            namespace=namespace
        ),
        string_data={
            'sdk-key-production': sdk_key_prod,
            'sdk-key-test': sdk_key_test
        }
    )
    
    v1.create_namespaced_secret(namespace, secret)
    
    return {'message': f'Created project {spec["key"]}'}
```

## Make/Taskfile

Simple automation with Make:

```makefile
# Makefile
.PHONY: create-project list-projects get-key

create-project:
	@python scripts/create_project.py \
		--name "$(NAME)" \
		--key "$(KEY)" \
		--tags "$(TAGS)"

list-projects:
	@python scripts/list_projects.py

get-key:
	@python scripts/get_sdk_key.py $(PROJECT) $(ENV)

setup-env:
	@python scripts/save_sdk_key.py $(PROJECT) production > .env.production
	@echo "✓ Saved SDK key to .env.production"
```

**Usage:**
```bash
make create-project NAME="My Agent" KEY=my-ai TAGS=ai-configs,production
make list-projects
make get-key PROJECT=my-ai ENV=production
make setup-env PROJECT=my-ai
```

## Next Steps

- [Build admin tooling](admin-tooling.md)
- [Configure project cloning](project-cloning.md)
- [Manage environment configuration](env-config.md)
