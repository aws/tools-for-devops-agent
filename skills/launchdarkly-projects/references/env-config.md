# Environment Configuration

Patterns for saving SDK keys to your codebase's configuration system.

## Overview

After creating a project, you need to save the SDK keys so your application can use them. The approach depends on your existing configuration pattern.

## Common Patterns

### 1. .env Files

Most common pattern for local development and simple deployments.

#### Python
```python
def save_sdk_key_to_env(
    project_key: str,
    environment: str = "production",
    env_file: str = ".env",
    var_name: str = "LD_SDK_KEY"
):
    """Save SDK key to .env file."""
    # Get the SDK key
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, environment)
    
    if not sdk_key:
        raise ValueError(f"Could not get SDK key for {project_key}/{environment}")
    
    # Read existing .env content
    env_content = {}
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_content[key] = value
    
    # Update or add the SDK key
    env_content[var_name] = sdk_key
    
    # Write back to .env
    with open(env_file, "w") as f:
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")
    
    print(f"✓ Saved {var_name} to {env_file}")
```

#### Node.js/TypeScript
```typescript
import * as fs from 'fs';
import * as path from 'path';

async function saveSdkKeyToEnv(
  projectKey: string,
  environment: string = 'production',
  envFile: string = '.env',
  varName: string = 'LD_SDK_KEY'
): Promise<void> {
  const pm = new ProjectManager();
  const sdkKey = await pm.getSdkKey(projectKey, environment);
  
  if (!sdkKey) {
    throw new Error(`Could not get SDK key for ${projectKey}/${environment}`);
  }
  
  // Read existing .env content
  const envContent: Record<string, string> = {};
  if (fs.existsSync(envFile)) {
    const content = fs.readFileSync(envFile, 'utf-8');
    content.split('\n').forEach((line) => {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
        const [key, ...valueParts] = trimmed.split('=');
        envContent[key] = valueParts.join('=');
      }
    });
  }
  
  // Update or add the SDK key
  envContent[varName] = sdkKey;
  
  // Write back to .env
  const lines = Object.entries(envContent).map(([key, value]) => `${key}=${value}`);
  fs.writeFileSync(envFile, lines.join('\n') + '\n');
  
  console.log(`✓ Saved ${varName} to ${envFile}`);
}
```

#### Usage
```bash
# Python
python -c "from launchdarkly.projects import save_sdk_key_to_env; save_sdk_key_to_env('my-project')"

# Node.js
node -e "require('./src/launchdarkly/env-config').saveSdkKeyToEnv('my-project')"
```

### 2. Multiple Environments

Save keys for multiple environments:

```python
# Save both production and test keys
save_sdk_key_to_env("my-project", "production", var_name="LD_SDK_KEY_PROD")
save_sdk_key_to_env("my-project", "test", var_name="LD_SDK_KEY_TEST")
```

**.env result:**
```bash
LD_SDK_KEY_PROD=sdk-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
LD_SDK_KEY_TEST=sdk-yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

### 3. Secrets Manager Integration

For cloud deployments, integrate with secrets managers.

#### AWS Secrets Manager
```python
import boto3
import json

def save_to_aws_secrets(project_key: str, environment: str, secret_name: str):
    """Save SDK key to AWS Secrets Manager."""
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, environment)
    
    client = boto3.client('secretsmanager')
    
    try:
        # Get existing secret
        response = client.get_secret_value(SecretId=secret_name)
        secrets = json.loads(response['SecretString'])
    except client.exceptions.ResourceNotFoundException:
        secrets = {}
    
    # Update with new key
    secrets['LD_SDK_KEY'] = sdk_key
    
    # Save back
    client.put_secret_value(
        SecretId=secret_name,
        SecretString=json.dumps(secrets)
    )
    
    print(f"✓ Saved SDK key to AWS Secrets Manager: {secret_name}")

# Usage
save_to_aws_secrets("my-project", "production", "myapp/production")
```

#### GCP Secret Manager
```python
from google.cloud import secretmanager

def save_to_gcp_secrets(project_key: str, environment: str, secret_id: str, gcp_project: str):
    """Save SDK key to GCP Secret Manager."""
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, environment)
    
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{gcp_project}/secrets/{secret_id}"
    
    # Add new version
    response = client.add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": sdk_key.encode("UTF-8")},
        }
    )
    
    print(f"✓ Saved SDK key to GCP Secret Manager: {response.name}")
```

#### Azure Key Vault
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

def save_to_azure_keyvault(project_key: str, environment: str, vault_url: str, secret_name: str):
    """Save SDK key to Azure Key Vault."""
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, environment)
    
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)
    
    client.set_secret(secret_name, sdk_key)
    
    print(f"✓ Saved SDK key to Azure Key Vault: {secret_name}")
```

### 4. Kubernetes Secrets

For Kubernetes deployments:

```python
import base64
import yaml

def create_k8s_secret(project_key: str, environment: str, namespace: str = "default"):
    """Generate Kubernetes secret manifest."""
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, environment)
    
    # Encode SDK key
    encoded_key = base64.b64encode(sdk_key.encode()).decode()
    
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "launchdarkly-sdk-key",
            "namespace": namespace
        },
        "type": "Opaque",
        "data": {
            "sdk-key": encoded_key
        }
    }
    
    # Write to file
    with open("k8s-secret.yaml", "w") as f:
        yaml.dump(secret, f)
    
    print("✓ Created k8s-secret.yaml")
    print("Apply with: kubectl apply -f k8s-secret.yaml")
```

### 5. Configuration Files

For applications using config files (YAML, JSON, TOML):

#### YAML Config
```python
import yaml

def save_to_yaml_config(project_key: str, environment: str, config_file: str = "config.yaml"):
    """Save SDK key to YAML config file."""
    pm = ProjectManager()
    sdk_key = pm.get_sdk_key(project_key, environment)
    
    # Read existing config
    config = {}
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = yaml.safe_load(f) or {}
    
    # Update LaunchDarkly section
    if "launchdarkly" not in config:
        config["launchdarkly"] = {}
    
    config["launchdarkly"]["sdk_key"] = sdk_key
    config["launchdarkly"]["project_key"] = project_key
    config["launchdarkly"]["environment"] = environment
    
    # Write back
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"✓ Saved SDK key to {config_file}")
```

#### JSON Config
```typescript
import * as fs from 'fs';

async function saveToJsonConfig(
  projectKey: string,
  environment: string,
  configFile: string = 'config.json'
): Promise<void> {
  const pm = new ProjectManager();
  const sdkKey = await pm.getSdkKey(projectKey, environment);
  
  // Read existing config
  let config: any = {};
  if (fs.existsSync(configFile)) {
    config = JSON.parse(fs.readFileSync(configFile, 'utf-8'));
  }
  
  // Update LaunchDarkly section
  config.launchdarkly = {
    sdkKey,
    projectKey,
    environment,
  };
  
  // Write back
  fs.writeFileSync(configFile, JSON.stringify(config, null, 2));
  
  console.log(`✓ Saved SDK key to ${configFile}`);
}
```

## Security Best Practices

### 1. Never Commit SDK Keys
Add to `.gitignore`:
```gitignore
# Environment files
.env
.env.local
.env.production
.env.test

# Config files with secrets
config/secrets.yaml
config/production.json
```

### 2. Use Different Keys Per Environment
```python
# Development
save_sdk_key_to_env("my-project", "test", ".env.development")

# Production (deploy separately)
save_sdk_key_to_env("my-project", "production", ".env.production")
```

### 3. Rotate Keys Regularly
```python
def rotate_sdk_key(project_key: str, environment: str):
    """
    Note: This requires creating a new SDK key via API.
    The LaunchDarkly API doesn't support key rotation directly.
    You would need to create a new environment or reset the key in the UI.
    """
    print("⚠️  SDK key rotation must be done via LaunchDarkly UI")
    print(f"   Go to: Project Settings → Environments → {environment} → Reset SDK Key")
```

### 4. Least Privilege Access
- API tokens for project creation: `projects:write`
- Application SDK keys: read-only by default
- Separate keys for test vs production

## Verification

After saving SDK keys, verify they work:

```python
async def verify_sdk_key(sdk_key: str) -> bool:
    """Verify an SDK key by initializing the AI SDK with it.

    Run in a standalone script. Inside an app that already called init_client,
    sdk_key is ignored and shutdown() closes the app's client.
    """
    from launchdarkly_ai_server import init_client, get_client, shutdown

    await init_client({"sdkKey": sdk_key})
    ok = get_client().is_initialized()
    print("✓ SDK key is valid and working" if ok else "✗ SDK key failed to initialize")
    await shutdown()
    return ok
```

Run it with `asyncio.run(verify_sdk_key(key))`. It needs `launchdarkly-server-sdk` and `launchdarkly-ai-server`.

## Next Steps

- [Integrate SDK in your application](../../../onboarding/sdk-install/SKILL.md)
- [Set up project cloning](project-cloning.md)
- [Build automation scripts](iac-automation.md)
