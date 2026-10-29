# Quick Start: Create Your First Project

Basic project creation patterns for getting started quickly.

## Prerequisites

- LaunchDarkly API access token with `projects:write` permission
- Set `LAUNCHDARKLY_API_TOKEN` environment variable

## Basic Project Creation

### Using the LaunchDarkly API

**Endpoint:** `POST https://app.launchdarkly.com/api/v2/projects`

**Required Headers:**
```
Authorization: {YOUR_API_TOKEN}
Content-Type: application/json
```

**Minimal Payload:**
```json
{
  "name": "My Agent Project",
  "key": "my-ai-project"
}
```

**Recommended Payload:**
```json
{
  "name": "Customer Support Agent",
  "key": "support-ai",
  "tags": ["ai-configs", "production"]
}
```

## Response Handling

### Success (201 Created)
```json
{
  "name": "Customer Support Agent",
  "key": "support-ai",
  "environments": {
    "items": [
      {
        "name": "Production",
        "key": "production",
        "apiKey": "sdk-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      },
      {
        "name": "Test",
        "key": "test",
        "apiKey": "sdk-yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
      }
    ]
  }
}
```

**Action:** Extract and save SDK keys for use in your application.

### Conflict (409)
Project with that key already exists.

**Action:** Either use the existing project or choose a different key.

### Error (400, 401, 403)
```json
{
  "code": "invalid_request",
  "message": "project key must be lowercase with hyphens"
}
```

**Action:** Fix the payload based on error message.

## Project Key Rules

Must follow these constraints:
- **Pattern:** `^[a-z][a-z0-9-]*$`
- **Start with:** Lowercase letter
- **Contains only:** Lowercase letters, numbers, hyphens
- **Unique:** Across your entire organization

### Valid Examples
```
support-ai
chat-bot-v2
recommendation-engine
customer-ai-prod
```

### Invalid Examples
```
Support_AI          # uppercase and underscore
123-project         # starts with number
my.project          # contains dot
ai_chatbot          # underscore not allowed
```

## Extracting SDK Keys

After creating a project, you'll need the SDK keys to connect your application.

### Environments Created by Default
- **Production** (key: `production`)
- **Test** (key: `test`)

### Get SDK Key for an Environment

**Endpoint:** `GET https://app.launchdarkly.com/api/v2/projects/{projectKey}?expand=environments`

**Parse Response:**
```json
{
  "environments": {
    "items": [
      {
        "key": "production",
        "apiKey": "sdk-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
      }
    ]
  }
}
```

Filter by `environment.key` to find the desired environment's `apiKey`.

## List Existing Projects

Before creating a new project, you may want to check what exists.

**Endpoint:** `GET https://app.launchdarkly.com/api/v2/projects`

**Response:**
```json
{
  "items": [
    {
      "name": "Customer Support Agent",
      "key": "support-ai",
      "tags": ["ai-configs"]
    }
  ]
}
```

## Common Mistakes

| Mistake | Problem | Fix |
|---------|---------|-----|
| Uppercase in key | Rejected by API | Use lowercase only |
| Spaces in key | Invalid format | Use hyphens instead |
| Key collision | 409 conflict | Choose unique key or use existing |
| Missing API token | 401 unauthorized | Set LAUNCHDARKLY_API_TOKEN |
| Wrong permission | 403 forbidden | Request `projects:write` permission |

## Next Steps

After creating your project:

1. **Save SDK keys** to your environment configuration
2. **Initialize LaunchDarkly SDK** in your application  
3. **Create configs** within the project
4. **Test the integration** in test environment first

See [Environment Configuration](env-config.md) for saving SDK keys to your codebase.
