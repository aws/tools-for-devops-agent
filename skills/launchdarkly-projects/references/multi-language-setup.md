# Multi-Language Setup

Guidance for polyglot architectures with multiple languages/frameworks.

## Overview

In a microservices or polyglot architecture, you may have services in different languages that need to share LaunchDarkly projects or maintain separate projects per service.

## Architecture Patterns

### Pattern 1: Shared Project, Multiple Services

One project, different services consume from different environments or contexts.

**When to use:**
- All services are part of the same application
- Want centralized config management
- Services share the same configs

```
Project: "my-app"
├── Service A (Python)    → Uses "my-app" production SDK key
├── Service B (Node.js)   → Uses "my-app" production SDK key
└── Service C (Go)        → Uses "my-app" production SDK key
```

### Pattern 2: Project Per Service

Each service has its own project.

**When to use:**
- Services are independent
- Different teams own different services
- Need isolation between services

```
Project: "service-a" → Service A (Python)
Project: "service-b" → Service B (Node.js)
Project: "service-c" → Service C (Go)
```

### Pattern 3: Hybrid

Shared projects for related services, separate for others.

```
Project: "frontend-services"
├── Web App (React)
└── Mobile App (React Native)

Project: "backend-services"
├── API Gateway (Node.js)
└── Auth Service (Go)

Project: "ml-services"
├── Recommendation Engine (Python)
└── Model Serving (Python)
```

## Centralized Project Management

Create a central service for project management that other services can use:

### Project Management API

```python
# project-manager-service/app.py
from flask import Flask, jsonify, request
from launchdarkly.projects import ProjectManager

app = Flask(__name__)
pm = ProjectManager()

@app.route('/projects', methods=['POST'])
def create_project():
    """Central API to create projects for any service."""
    data = request.json
    project = pm.create_project(
        name=data['name'],
        key=data['key'],
        tags=data.get('tags', [])
    )
    return jsonify(project)

@app.route('/projects/<key>/keys/<env>')
def get_sdk_key(key, env):
    """Get SDK key for any service."""
    sdk_key = pm.get_sdk_key(key, env)
    return jsonify({'sdkKey': sdk_key})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Service Consumption

Each service calls the central API:

**Python Service:**
```python
import requests

def get_launchdarkly_sdk_key():
    resp = requests.get(
        'http://project-manager:8080/projects/my-service/keys/production'
    )
    return resp.json()['sdkKey']
```

**Node.js Service:**
```typescript
async function getLaunchDarklySdkKey(): Promise<string> {
  const resp = await fetch(
    'http://project-manager:8080/projects/my-service/keys/production'
  );
  const data = await resp.json();
  return data.sdkKey;
}
```

**Go Service:**
```go
func getLaunchDarklySdkKey() (string, error) {
    resp, err := http.Get("http://project-manager:8080/projects/my-service/keys/production")
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()
    
    var result struct {
        SdkKey string `json:"sdkKey"`
    }
    json.NewDecoder(resp.Body).Decode(&result)
    return result.SdkKey, nil
}
```

## Shared Configuration Repository

Maintain a central config repo that all services reference:

```
config-repo/
├── launchdarkly/
│   ├── projects.yaml           # Project definitions
│   ├── sdk-keys/
│   │   ├── production/
│   │   │   ├── service-a.key
│   │   │   ├── service-b.key
│   │   │   └── service-c.key
│   │   └── test/
│   │       ├── service-a.key
│   │       ├── service-b.key
│   │       └── service-c.key
│   └── scripts/
│       ├── create_projects.py
│       └── sync_keys.sh
```

**projects.yaml:**
```yaml
projects:
  - name: Service A
    key: service-a
    tags: [python, backend]
    services:
      - name: service-a
        language: python
        
  - name: Service B
    key: service-b
    tags: [nodejs, api]
    services:
      - name: service-b
        language: nodejs
        
  - name: Service C
    key: service-c
    tags: [go, gateway]
    services:
      - name: service-c
        language: go
```

**Sync script:**
```bash
#!/bin/bash
# scripts/sync_keys.sh

for env in production test; do
    for service in service-a service-b service-c; do
        sdk_key=$(python scripts/get_sdk_key.py $service $env)
        echo "$sdk_key" > "sdk-keys/$env/$service.key"
        echo "✓ Synced $service/$env"
    done
done
```

## Service Templates

Create templates for each language:

### Python Template
```python
# templates/python/launchdarkly_setup.py
import os
from launchdarkly.projects import ProjectManager

def setup_project(service_name: str):
    """Setup LaunchDarkly project for Python service."""
    pm = ProjectManager()
    
    project = pm.create_project(
        name=f"{service_name} Service",
        key=service_name,
        tags=["python", "service"]
    )
    
    sdk_key = pm.get_sdk_key(service_name, "production")
    
    # Save to .env
    with open(".env", "w") as f:
        f.write(f"LD_SDK_KEY={sdk_key}\n")
    
    print(f"✓ Setup complete for {service_name}")
```

### Node.js Template
```typescript
// templates/nodejs/launchdarkly-setup.ts
import { ProjectManager } from './launchdarkly/projects';
import * as fs from 'fs';

async function setupProject(serviceName: string): Promise<void> {
  const pm = new ProjectManager();
  
  const project = await pm.createProject({
    name: `${serviceName} Service`,
    key: serviceName,
    tags: ['nodejs', 'service'],
  });
  
  const sdkKey = await pm.getSdkKey(serviceName, 'production');
  
  // Save to .env
  fs.writeFileSync('.env', `LD_SDK_KEY=${sdkKey}\n`);
  
  console.log(`✓ Setup complete for ${serviceName}`);
}
```

### Go Template
```go
// templates/go/launchdarkly_setup.go
package main

import (
    "fmt"
    "os"
    "yourmodule/pkg/launchdarkly"
)

func setupProject(serviceName string) error {
    pm := launchdarkly.NewProjectManager("")
    
    project, err := pm.CreateProject(
        fmt.Sprintf("%s Service", serviceName),
        serviceName,
        []string{"go", "service"},
    )
    if err != nil {
        return err
    }
    
    sdkKey, err := pm.GetSDKKey(serviceName, "production")
    if err != nil {
        return err
    }
    
    // Save to .env
    f, err := os.Create(".env")
    if err != nil {
        return err
    }
    defer f.Close()
    
    fmt.Fprintf(f, "LD_SDK_KEY=%s\n", sdkKey)
    
    fmt.Printf("✓ Setup complete for %s\n", serviceName)
    return nil
}
```

## Monorepo Setup

For monorepos with multiple services:

```
monorepo/
├── services/
│   ├── api/                 (Node.js)
│   ├── worker/              (Python)
│   └── gateway/             (Go)
├── packages/
│   └── launchdarkly-setup/
│       ├── python/
│       │   └── setup.py
│       ├── nodejs/
│       │   └── setup.ts
│       └── go/
│           └── setup.go
└── scripts/
    └── setup-all-projects.sh
```

**setup-all-projects.sh:**
```bash
#!/bin/bash

echo "Setting up LaunchDarkly projects for all services..."

cd services/api
npm run setup-launchdarkly

cd ../worker
python scripts/setup_launchdarkly.py

cd ../gateway
go run scripts/setup_launchdarkly.go

echo "✓ All services configured"
```

## Environment Variable Convention

Standardize environment variable names across languages:

```bash
# Common convention
LD_SDK_KEY=<production-key>
LD_SDK_KEY_TEST=<test-key>
LAUNCHDARKLY_PROJECT_KEY=<project-key>
LAUNCHDARKLY_ENVIRONMENT=<production|test>
```

**Loading in each language:**

**Python:**
```python
import os
sdk_key = os.environ['LD_SDK_KEY']
```

**Node.js:**
```typescript
const sdkKey = process.env.LD_SDK_KEY;
```

**Go:**
```go
sdkKey := os.Getenv("LD_SDK_KEY")
```

**Ruby:**
```ruby
sdk_key = ENV['LD_SDK_KEY']
```

**Java:**
```java
String sdkKey = System.getenv("LD_SDK_KEY");
```

## Container/K8s ConfigMap

Share SDK keys via Kubernetes ConfigMap:

```yaml
# k8s/launchdarkly-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: launchdarkly-config
data:
  project-key: "my-app"
  environment: "production"

---
apiVersion: v1
kind: Secret
metadata:
  name: launchdarkly-secrets
type: Opaque
stringData:
  sdk-key: "sdk-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**Mount in all services:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: service-a
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: LD_SDK_KEY
          valueFrom:
            secretKeyRef:
              name: launchdarkly-secrets
              key: sdk-key
        - name: LAUNCHDARKLY_PROJECT_KEY
          valueFrom:
            configMapKeyRef:
              name: launchdarkly-config
              key: project-key
```

## Service Mesh Integration

For service mesh (Istio, Linkerd), use a sidecar pattern:

```yaml
# Sidecar that manages LaunchDarkly SDK keys
apiVersion: v1
kind: Pod
metadata:
  name: my-service
spec:
  containers:
  # Main application
  - name: app
    image: my-service:latest
    env:
    - name: LD_SDK_KEY
      value: /var/run/secrets/launchdarkly/sdk-key
    volumeMounts:
    - name: ld-keys
      mountPath: /var/run/secrets/launchdarkly
  
  # Sidecar that fetches/refreshes keys
  - name: ld-key-sync
    image: ld-key-sync:latest
    env:
    - name: LAUNCHDARKLY_API_TOKEN
      valueFrom:
        secretKeyRef:
          name: ld-api-token
          key: token
    - name: PROJECT_KEY
      value: my-service
    volumeMounts:
    - name: ld-keys
      mountPath: /var/run/secrets/launchdarkly
  
  volumes:
  - name: ld-keys
    emptyDir: {}
```

## Best Practices

### 1. Naming Conventions
```
Project Key Format: {service-name}-{optional-suffix}

Examples:
  - api-gateway
  - user-service
  - recommendation-engine
```

### 2. Tagging Strategy
```python
tags = [
    "language:python",      # or nodejs, go, etc.
    "team:platform",        # owning team
    "environment:prod",     # deployment env
    "type:service"          # or frontend, worker, etc.
]
```

### 3. Documentation
Maintain a service registry:

```markdown
# Service Registry

| Service | Language | Project Key | Team | Status |
|---------|----------|-------------|------|--------|
| API Gateway | Node.js | api-gateway | Platform | Active |
| User Service | Go | user-service | Identity | Active |
| ML Engine | Python | ml-engine | Data Science | Active |
```

### 4. Automation
Automate project creation for new services:

```bash
# scripts/new-service.sh
#!/bin/bash
SERVICE_NAME=$1
LANGUAGE=$2

# Create project
python scripts/create_project.py \
    --name "$SERVICE_NAME Service" \
    --key "$SERVICE_NAME" \
    --tags "language:$LANGUAGE,type:service"

# Generate template
cp -r "templates/$LANGUAGE" "services/$SERVICE_NAME"

# Setup SDK key
cd "services/$SERVICE_NAME"
bash setup.sh

echo "✓ New service $SERVICE_NAME created"
```

## Next Steps

- [Setup environment configuration](env-config.md)
- [Configure project cloning](project-cloning.md)
- [Build admin tooling](admin-tooling.md)
