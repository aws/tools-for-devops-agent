# Authentication Methods - Complete Guide

## Overview

This document explains three common authentication methods used in API integrations, their call flows, security characteristics, and use cases.

## Table of Contents

1. [OAuth Client Credentials (M2M)](#1-oauth-client-credentials-m2m)
2. [OAuth 3LO (Three-Legged OAuth)](#2-oauth-3lo-three-legged-oauth)
3. [API Key Authentication](#3-api-key-authentication)
4. [Comparison Matrix](#comparison-matrix)
5. [Decision Guide](#decision-guide)

---

## 1. OAuth Client Credentials (M2M)

### Description

**Machine-to-Machine (M2M)** authentication where no user is involved. The application authenticates as itself using client credentials.

### Architecture

```
┌─────────────────┐                    ┌─────────────────────┐
│   Service A     │                    │  Authorization      │
│   (Client)      │                    │     Server          │
│                 │                    │   (Cognito/Auth0)   │
└────────┬────────┘                    └──────────┬──────────┘
         │                                        │
         │  1. Token Request                      │
         │     POST /oauth2/token                 │
         │     client_id=abc123                   │
         │     client_secret=xyz789               │
         │     grant_type=client_credentials      │
         │     scope=read write                   │
         ├───────────────────────────────────────>│
         │                                        │
         │                            2. Validate credentials
         │                               - Check client_id exists
         │                               - Verify client_secret
         │                               - Validate scopes
         │                               - Generate JWT token
         │                                        │
         │  3. Access Token Response              │
         │     {                                  │
         │       "access_token": "eyJhbGc...",    │
         │       "token_type": "Bearer",          │
         │       "expires_in": 3600,              │
         │       "scope": "read write"            │
         │     }                                  │
         │<───────────────────────────────────────┤
         │                                        │
┌────────┴────────┐                    ┌──────────┴──────────┐
│   Service A     │                    │    Service B        │
│   (Client)      │                    │   (API Server)      │
└────────┬────────┘                    └──────────┬──────────┘
         │                                        │
         │  4. API Request                        │
         │     GET /api/resource                  │
         │     Authorization: Bearer eyJhbGc...   │
         ├───────────────────────────────────────>│
         │                                        │
         │                            5. Validate token
         │                               - Verify signature
         │                               - Check expiration
         │                               - Validate scopes
         │                                        │
         │  6. API Response                       │
         │     { "data": [...] }                  │
         │<───────────────────────────────────────┤
         │                                        │
```

### Request/Response Examples

#### Step 1: Token Request

**HTTP Request:**
```http
POST /oauth2/token HTTP/1.1
Host: auth.example.com
Content-Type: application/x-www-form-urlencoded
Authorization: Basic YWJjMTIzOnh5ejc4OQ==

grant_type=client_credentials&scope=read write
```

**curl Example:**
```bash
curl -X POST https://auth.example.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "client_id:client_secret" \
  -d "grant_type=client_credentials&scope=read write"
```

#### Step 3: Token Response

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhYmMxMjMiLCJzY29wZSI6InJlYWQgd3JpdGUiLCJleHAiOjE3MDAwMDAwMDB9.signature",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

**JWT Token Structure:**
```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "abc123",
    "client_id": "abc123",
    "scope": "read write",
    "iss": "https://auth.example.com",
    "exp": 1700000000,
    "iat": 1699996400
  },
  "signature": "..."
}
```

#### Step 4: API Request with Token

**HTTP Request:**
```http
GET /api/resource HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

**curl Example:**
```bash
curl https://api.example.com/api/resource \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Characteristics

| Aspect | Details |
|--------|---------|
| **User Involvement** | ❌ None - fully automated |
| **Login Screen** | ❌ No user interface |
| **Consent Screen** | ❌ No user consent |
| **Token Represents** | Application identity |
| **Credentials Required** | Client ID + Client Secret |
| **Token Lifetime** | Short (typically 1 hour) |
| **Refresh Tokens** | ❌ Not used (request new token) |
| **Security Level** | 🟢 High (if secret protected) |
| **Complexity** | 🟡 Medium |

### Use Cases

✅ **Ideal For:**
- Microservice-to-microservice communication
- Backend services accessing APIs
- Scheduled jobs and cron tasks
- CI/CD pipelines
- Server-side integrations
- Your Lambda MCP implementation

❌ **Not Suitable For:**
- User-facing applications
- Mobile apps (can't secure secret)
- Browser-based applications
- Scenarios requiring user consent
- MCP specification compliance (requires user delegation)

### Security Considerations

**Strengths:**
- ✅ Short-lived tokens limit exposure
- ✅ Scope-based access control
- ✅ Centralized token management
- ✅ Revocation support

**Risks:**
- ⚠️ Client secret must be protected
- ⚠️ Secret exposure = full access
- ⚠️ No user context in tokens
- ⚠️ Requires secure secret storage

**Best Practices:**
```bash
# Store secrets securely
export CLIENT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id oauth-client-secret \
  --query SecretString --output text)

# Rotate secrets regularly
aws secretsmanager rotate-secret --secret-id oauth-client-secret

# Use environment-specific credentials
# dev-client-id / staging-client-id / prod-client-id

# Monitor token usage
aws cloudwatch put-metric-data \
  --namespace OAuth \
  --metric-name TokenRequests \
  --value 1
```

### Implementation Example (Python)

```python
import requests
import time
from datetime import datetime, timedelta

class OAuth2Client:
    def __init__(self, client_id, client_secret, token_url):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.token = None
        self.token_expiry = None
    
    def get_token(self):
        """Get or refresh access token"""
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token
        
        response = requests.post(
            self.token_url,
            data={
                'grant_type': 'client_credentials',
                'scope': 'read write'
            },
            auth=(self.client_id, self.client_secret)
        )
        response.raise_for_status()
        
        data = response.json()
        self.token = data['access_token']
        # Refresh 5 minutes before expiry
        self.token_expiry = datetime.now() + timedelta(seconds=data['expires_in'] - 300)
        
        return self.token
    
    def call_api(self, url):
        """Make authenticated API call"""
        token = self.get_token()
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {token}'}
        )
        return response.json()

# Usage
client = OAuth2Client(
    client_id='abc123',
    client_secret='xyz789',
    token_url='https://auth.example.com/oauth2/token'
)

data = client.call_api('https://api.example.com/resource')
```

### CDK Implementation

```typescript
// Cognito User Pool with Client Credentials
const userPool = new cognito.UserPool(this, 'UserPool', {
  userPoolName: 'api-oauth-pool',
});

// Resource Server with scopes
const resourceServer = userPool.addResourceServer('ResourceServer', {
  identifier: 'api-server',
  scopes: [
    { scopeName: 'read', scopeDescription: 'Read access' },
    { scopeName: 'write', scopeDescription: 'Write access' },
  ],
});

// M2M Client
const m2mClient = new cognito.UserPoolClient(this, 'M2MClient', {
  userPool,
  generateSecret: true,
  authFlows: {
    userPassword: false,
    userSrp: false,
    custom: false,
  },
  oAuth: {
    flows: {
      clientCredentials: true,  // ← Enable M2M
    },
    scopes: [
      cognito.OAuthScope.resourceServer(resourceServer, { scopeName: 'read' }),
      cognito.OAuthScope.resourceServer(resourceServer, { scopeName: 'write' }),
    ],
  },
  accessTokenValidity: cdk.Duration.hours(1),
  enableTokenRevocation: true,
});
```

---

## 2. OAuth 3LO (Three-Legged OAuth)

### Description

**Three-Legged OAuth** (Authorization Code Flow) enables user-delegated access where the user explicitly grants permission to an application to access their resources.

Called "3-legged" because it involves three parties:
1. **User** (Resource Owner)
2. **Client Application**
3. **Resource Server** (API)

### Architecture

```
┌──────────────┐
│     User     │
│   (Browser)  │
└──────┬───────┘
       │
       │ 1. Click "Login with Provider"
       │
┌──────┴───────┐
│    Client    │
│     App      │
└──────┬───────┘
       │
       │ 2. Redirect to Authorization Server
       │    /authorize?
       │      response_type=code
       │      client_id=abc123
       │      redirect_uri=https://app.com/callback
       │      scope=read write
       │      state=random123
       │      code_challenge=xyz...
       │      code_challenge_method=S256
       │
┌──────┴───────────────┐
│  Authorization       │
│     Server           │
└──────┬───────────────┘
       │
       │ 3. Show Login Screen
       │
┌──────┴───────┐
│     User     │
│   (Browser)  │
└──────┬───────┘
       │
       │ 4. Enter credentials
       │    username: user@example.com
       │    password: ********
       │
┌──────┴───────────────┐
│  Authorization       │
│     Server           │
└──────┬───────────────┘
       │
       │ 5. Show Consent Screen
       │    "App X wants to:"
       │    ☑ Read your data
       │    ☑ Write to your account
       │    [Approve] [Deny]
       │
┌──────┴───────┐
│     User     │
│   (Browser)  │
└──────┬───────┘
       │
       │ 6. User clicks "Approve"
       │
┌──────┴───────────────┐
│  Authorization       │
│     Server           │
└──────┬───────────────┘
       │
       │ 7. Redirect with authorization code
       │    https://app.com/callback?
       │      code=auth_code_abc123
       │      state=random123
       │
┌──────┴───────┐
│    Client    │
│     App      │
│  (Backend)   │
└──────┬───────┘
       │
       │ 8. Exchange code for token
       │    POST /token
       │      grant_type=authorization_code
       │      code=auth_code_abc123
       │      redirect_uri=https://app.com/callback
       │      client_id=abc123
       │      client_secret=xyz789
       │      code_verifier=original_random
       │
┌──────┴───────────────┐
│  Authorization       │
│     Server           │
└──────┬───────────────┘
       │
       │ 9. Return tokens
       │    {
       │      "access_token": "eyJhbGc...",
       │      "refresh_token": "def456...",
       │      "expires_in": 3600
       │    }
       │
┌──────┴───────┐
│    Client    │
│     App      │
└──────┬───────┘
       │
       │ 10. Access user's resources
       │     GET /api/user/data
       │     Authorization: Bearer eyJhbGc...
       │
┌──────┴───────────────┐
│   Resource Server    │
│      (API)           │
└──────────────────────┘
```

### Request/Response Examples

#### Step 2: Authorization Request

**Browser Redirect:**
```
https://auth.example.com/authorize?
  response_type=code&
  client_id=abc123&
  redirect_uri=https://app.example.com/callback&
  scope=read write&
  state=random_state_string_123&
  code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&
  code_challenge_method=S256
```

**PKCE Generation (Python):**
```python
import secrets
import hashlib
import base64

# Generate code verifier
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

# Generate code challenge
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode('utf-8')).digest()
).decode('utf-8').rstrip('=')
```

#### Step 7: Authorization Code Response

**Browser Redirect:**
```
https://app.example.com/callback?
  code=auth_code_abc123xyz789&
  state=random_state_string_123
```

#### Step 8: Token Exchange Request

**HTTP Request:**
```http
POST /oauth2/token HTTP/1.1
Host: auth.example.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=auth_code_abc123xyz789&
redirect_uri=https://app.example.com/callback&
client_id=abc123&
client_secret=xyz789&
code_verifier=original_code_verifier_string
```

**curl Example:**
```bash
curl -X POST https://auth.example.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=auth_code_abc123xyz789" \
  -d "redirect_uri=https://app.example.com/callback" \
  -d "client_id=abc123" \
  -d "client_secret=xyz789" \
  -d "code_verifier=original_code_verifier_string"
```

#### Step 9: Token Response

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyMTIzIiwic2NvcGUiOiJyZWFkIHdyaXRlIiwiZXhwIjoxNzAwMDAwMDAwfQ.signature",
  "refresh_token": "def456ghi789jkl012mno345pqr678stu901vwx234yz",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write"
}
```

**Access Token Structure:**
```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user123",
    "email": "user@example.com",
    "scope": "read write",
    "iss": "https://auth.example.com",
    "aud": "abc123",
    "exp": 1700000000,
    "iat": 1699996400
  },
  "signature": "..."
}
```

### Characteristics

| Aspect | Details |
|--------|---------|
| **User Involvement** | ✅ Required - user must login |
| **Login Screen** | ✅ Yes - hosted by auth server |
| **Consent Screen** | ✅ Yes - user approves scopes |
| **Token Represents** | User's delegated permission |
| **Credentials Required** | User login + app credentials |
| **Token Lifetime** | Access: 1 hour, Refresh: days/months |
| **Refresh Tokens** | ✅ Yes - long-lived |
| **Security Level** | 🟢 Highest (with PKCE) |
| **Complexity** | 🔴 High |

### Use Cases

✅ **Ideal For:**
- Web applications
- Mobile applications
- Desktop applications
- Browser extensions
- Any app acting on behalf of users
- MCP specification compliance
- Third-party integrations requiring user consent

❌ **Not Suitable For:**
- Server-to-server communication
- Background jobs without user
- Automated systems
- Scenarios where user interaction is impossible

### Security Features

**PKCE (Proof Key for Code Exchange):**
- Prevents authorization code interception
- Required for public clients (mobile/SPA)
- Recommended for all clients in OAuth 2.1

**State Parameter:**
- Prevents CSRF attacks
- Client generates random string
- Validates on callback

**Redirect URI Validation:**
- Authorization server validates exact match
- Prevents token theft via open redirects

**Refresh Token Rotation:**
- New refresh token issued on each use
- Old refresh token invalidated
- Limits impact of token theft

### Implementation Example (Python/Flask)

```python
from flask import Flask, redirect, request, session
import requests
import secrets
import hashlib
import base64

app = Flask(__name__)
app.secret_key = 'your-secret-key'

CLIENT_ID = 'abc123'
CLIENT_SECRET = 'xyz789'
AUTH_URL = 'https://auth.example.com/authorize'
TOKEN_URL = 'https://auth.example.com/token'
REDIRECT_URI = 'https://app.example.com/callback'

@app.route('/login')
def login():
    # Generate PKCE
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    
    # Generate state
    state = secrets.token_urlsafe(32)
    
    # Store in session
    session['code_verifier'] = code_verifier
    session['state'] = state
    
    # Build authorization URL
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'read write',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }
    
    auth_url = f"{AUTH_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    # Validate state
    if request.args.get('state') != session.get('state'):
        return 'Invalid state', 400
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        return 'No code provided', 400
    
    # Exchange code for token
    response = requests.post(TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code_verifier': session.get('code_verifier')
    })
    
    tokens = response.json()
    session['access_token'] = tokens['access_token']
    session['refresh_token'] = tokens['refresh_token']
    
    return redirect('/dashboard')

@app.route('/api/data')
def get_data():
    token = session.get('access_token')
    if not token:
        return redirect('/login')
    
    response = requests.get(
        'https://api.example.com/user/data',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    return response.json()
```

### CDK Implementation

```typescript
// Cognito User Pool with Authorization Code Flow
const userPool = new cognito.UserPool(this, 'UserPool', {
  userPoolName: 'user-oauth-pool',
  selfSignUpEnabled: true,
  signInAliases: { email: true },
  autoVerify: { email: true },
});

// Resource Server
const resourceServer = userPool.addResourceServer('ResourceServer', {
  identifier: 'api-server',
  scopes: [
    { scopeName: 'read', scopeDescription: 'Read access' },
    { scopeName: 'write', scopeDescription: 'Write access' },
  ],
});

// Web App Client with Authorization Code Flow
const webClient = userPool.addClient('WebClient', {
  generateSecret: true,
  authFlows: {
    userPassword: true,
    userSrp: true,
  },
  oAuth: {
    flows: {
      authorizationCodeGrant: true,  // ← Enable 3LO
    },
    scopes: [
      cognito.OAuthScope.OPENID,
      cognito.OAuthScope.EMAIL,
      cognito.OAuthScope.PROFILE,
      cognito.OAuthScope.resourceServer(resourceServer, { scopeName: 'read' }),
      cognito.OAuthScope.resourceServer(resourceServer, { scopeName: 'write' }),
    ],
    callbackUrls: ['https://app.example.com/callback'],
    logoutUrls: ['https://app.example.com/logout'],
  },
  accessTokenValidity: cdk.Duration.hours(1),
  refreshTokenValidity: cdk.Duration.days(30),
  enableTokenRevocation: true,
});

// Cognito Domain for hosted UI
const domain = userPool.addDomain('Domain', {
  cognitoDomain: {
    domainPrefix: 'my-app-oauth',
  },
});
```

---

*Continued in next part...*
# Authentication Methods - Part 2

## 3. API Key Authentication

### Description

**API Key** is the simplest form of authentication using a static, long-lived credential that identifies the calling application. No OAuth flow, no tokens, just a single key.

### Architecture

```
┌─────────────────┐                          ┌─────────────────────┐
│   Client App    │                          │    API Server       │
│                 │                          │                     │
└────────┬────────┘                          └──────────┬──────────┘
         │                                              │
         │  1. API Request with Key                    │
         │     GET /api/resource                       │
         │     X-API-Key: sk_live_abc123xyz789         │
         ├────────────────────────────────────────────>│
         │                                              │
         │                                  2. Validate API Key
         │                                     - Lookup key in database
         │                                     - Check if active
         │                                     - Check rate limits
         │                                     - Check IP whitelist (optional)
         │                                              │
         │  3. API Response                             │
         │     { "data": [...] }                        │
         │<────────────────────────────────────────────┤
         │                                              │
```

### Request/Response Examples

#### Header-Based (Recommended)

**HTTP Request:**
```http
GET /api/resource HTTP/1.1
Host: api.example.com
X-API-Key: sk_live_abc123xyz789
Content-Type: application/json
```

**curl Example:**
```bash
curl https://api.example.com/api/resource \
  -H "X-API-Key: sk_live_abc123xyz789"
```

#### Bearer Token Format

**HTTP Request:**
```http
GET /api/resource HTTP/1.1
Host: api.example.com
Authorization: Bearer sk_live_abc123xyz789
Content-Type: application/json
```

**curl Example:**
```bash
curl https://api.example.com/api/resource \
  -H "Authorization: Bearer sk_live_abc123xyz789"
```

#### Query Parameter (Not Recommended)

**HTTP Request:**
```http
GET /api/resource?api_key=sk_live_abc123xyz789 HTTP/1.1
Host: api.example.com
```

**curl Example:**
```bash
curl "https://api.example.com/api/resource?api_key=sk_live_abc123xyz789"
```

⚠️ **Warning**: Query parameters are logged in server logs, proxy logs, and browser history. Use headers instead.

### Characteristics

| Aspect | Details |
|--------|---------|
| **User Involvement** | ❌ None |
| **Login Screen** | ❌ No |
| **Consent Screen** | ❌ No |
| **Token Represents** | Application identity |
| **Credentials Required** | Single static key |
| **Token Lifetime** | ❌ No expiration (manual rotation) |
| **Refresh Mechanism** | ❌ None (generate new key) |
| **Security Level** | 🔴 Low |
| **Complexity** | 🟢 Very Low |

### Use Cases

✅ **Ideal For:**
- Simple internal APIs
- Development and testing
- Public read-only APIs
- Low-security requirements
- Quick prototypes
- Internal monitoring dashboards

❌ **Not Suitable For:**
- Production systems with sensitive data
- User-specific access control
- Compliance requirements (SOC2, HIPAA, PCI-DSS)
- Mobile or browser applications (key exposure)
- Multi-tenant systems
- MCP specification compliance

### Security Risks

⚠️ **Critical Vulnerabilities:**

1. **No Expiration**
   - Keys valid forever unless manually revoked
   - Stolen key = permanent access until discovered

2. **No Scopes**
   - All-or-nothing access
   - Can't limit permissions per key

3. **Easy to Leak**
   - Committed to git repositories
   - Logged in application logs
   - Exposed in error messages
   - Visible in network traffic (if not HTTPS)

4. **No User Context**
   - Can't distinguish between users
   - No audit trail of who did what

5. **Replay Attacks**
   - Stolen key can be reused indefinitely
   - No protection against interception

### Best Practices

```bash
# ✅ DO: Store in environment variables
export API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id api-key \
  --query SecretString --output text)

# ✅ DO: Use different keys per environment
export DEV_API_KEY="sk_dev_..."
export STAGING_API_KEY="sk_staging_..."
export PROD_API_KEY="sk_prod_..."

# ✅ DO: Rotate keys regularly
# Create new key
NEW_KEY=$(openssl rand -hex 32)
# Update application
# Revoke old key after grace period

# ❌ DON'T: Hardcode in source code
API_KEY = "sk_live_abc123xyz789"  # BAD!

# ❌ DON'T: Commit to version control
echo "API_KEY=sk_live_abc123xyz789" >> .env  # BAD!
git add .env  # VERY BAD!

# ❌ DON'T: Use in query parameters
curl "https://api.com/data?api_key=sk_live_abc123xyz789"  # BAD!

# ❌ DON'T: Log API keys
logger.info(f"Using API key: {api_key}")  # BAD!
```

### Implementation Example (Python/Flask)

**Server Side:**
```python
from flask import Flask, request, jsonify
from functools import wraps
import hashlib
import hmac

app = Flask(__name__)

# Store hashed API keys (never store plaintext!)
API_KEYS = {
    'client1': hashlib.sha256('sk_live_abc123xyz789'.encode()).hexdigest(),
    'client2': hashlib.sha256('sk_live_def456uvw012'.encode()).hexdigest(),
}

RATE_LIMITS = {
    'client1': {'requests': 0, 'limit': 1000},
    'client2': {'requests': 0, 'limit': 100},
}

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Hash provided key
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Find matching client
        client_id = None
        for cid, stored_hash in API_KEYS.items():
            if hmac.compare_digest(key_hash, stored_hash):
                client_id = cid
                break
        
        if not client_id:
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Check rate limit
        if RATE_LIMITS[client_id]['requests'] >= RATE_LIMITS[client_id]['limit']:
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        RATE_LIMITS[client_id]['requests'] += 1
        
        # Add client_id to request context
        request.client_id = client_id
        
        return f(*args, **kwargs)
    
    return decorated_function

@app.route('/api/resource')
@require_api_key
def get_resource():
    return jsonify({
        'data': 'sensitive information',
        'client_id': request.client_id
    })

@app.route('/api/public')
def public_endpoint():
    return jsonify({'data': 'public information'})
```

**Client Side:**
```python
import requests
import os

class APIClient:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
    
    def get(self, endpoint):
        response = requests.get(
            f"{self.base_url}{endpoint}",
            headers={'X-API-Key': self.api_key}
        )
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint, data):
        response = requests.post(
            f"{self.base_url}{endpoint}",
            json=data,
            headers={'X-API-Key': self.api_key}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = APIClient(
    api_key=os.environ['API_KEY'],  # From environment
    base_url='https://api.example.com'
)

data = client.get('/api/resource')
```

### CDK Implementation (API Gateway)

```typescript
import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';

// Lambda function to handle requests
const apiFunction = new lambda.Function(this, 'APIFunction', {
  runtime: lambda.Runtime.PYTHON_3_11,
  handler: 'index.handler',
  code: lambda.Code.fromInline(`
def handler(event, context):
    return {
        'statusCode': 200,
        'body': '{"data": "response"}'
    }
  `),
});

// API Gateway with API Key
const api = new apigateway.RestApi(this, 'API', {
  restApiName: 'API Key Protected API',
  apiKeySourceType: apigateway.ApiKeySourceType.HEADER,
});

// Create API Key
const apiKey = api.addApiKey('APIKey', {
  apiKeyName: 'client-api-key',
  description: 'API key for client access',
});

// Create Usage Plan
const usagePlan = api.addUsagePlan('UsagePlan', {
  name: 'Standard',
  throttle: {
    rateLimit: 100,
    burstLimit: 200,
  },
  quota: {
    limit: 10000,
    period: apigateway.Period.MONTH,
  },
});

// Associate API Key with Usage Plan
usagePlan.addApiKey(apiKey);

// Add resource and method
const resource = api.root.addResource('resource');
resource.addMethod('GET', new apigateway.LambdaIntegration(apiFunction), {
  apiKeyRequired: true,  // ← Require API key
});

// Associate stage with usage plan
usagePlan.addApiStage({
  stage: api.deploymentStage,
});

// Output API key value
new cdk.CfnOutput(this, 'APIKeyValue', {
  value: apiKey.keyId,
  description: 'API Key ID (retrieve value from console)',
});
```

---

## Comparison Matrix

### Feature Comparison

| Feature | Client Credentials | OAuth 3LO | API Key |
|---------|-------------------|-----------|---------|
| **User Login** | ❌ | ✅ | ❌ |
| **User Consent** | ❌ | ✅ | ❌ |
| **Token Expiration** | ✅ (1 hour) | ✅ (1 hour + refresh) | ❌ (manual) |
| **Scope Control** | ✅ | ✅ | ❌ |
| **User Context** | ❌ | ✅ | ❌ |
| **Revocation** | ✅ (expires) | ✅ (instant) | ⚠️ (manual) |
| **Refresh Tokens** | ❌ | ✅ | ❌ |
| **PKCE Support** | ❌ | ✅ | ❌ |
| **Rate Limiting** | ✅ | ✅ | ✅ |
| **Audit Trail** | ✅ | ✅ | ⚠️ Limited |

### Security Comparison

| Aspect | Client Credentials | OAuth 3LO | API Key |
|--------|-------------------|-----------|---------|
| **Security Level** | 🟢 High | 🟢 Highest | 🔴 Low |
| **Secret Protection** | Required | Required | Required |
| **Token Theft Impact** | 🟡 Limited (1 hour) | 🟢 Minimal (revocable) | 🔴 Severe (permanent) |
| **Replay Attack** | 🟢 Protected | 🟢 Protected | 🔴 Vulnerable |
| **MITM Attack** | 🟢 Protected (HTTPS) | 🟢 Protected (HTTPS) | 🔴 Vulnerable |
| **Credential Leakage** | 🟡 Moderate risk | 🟢 Low risk | 🔴 High risk |

### Complexity Comparison

| Aspect | Client Credentials | OAuth 3LO | API Key |
|--------|-------------------|-----------|---------|
| **Implementation** | 🟡 Medium | 🔴 High | 🟢 Low |
| **Setup Time** | 🟡 Minutes | 🔴 Hours | 🟢 Seconds |
| **Maintenance** | 🟡 Medium | 🔴 High | 🟢 Low |
| **User Experience** | 🟢 Seamless | 🟡 Requires login | 🟢 Seamless |
| **Debugging** | 🟡 Medium | 🔴 Complex | 🟢 Easy |

### Use Case Comparison

| Scenario | Client Credentials | OAuth 3LO | API Key |
|----------|-------------------|-----------|---------|
| **Microservices** | ✅ Ideal | ❌ | ⚠️ Simple only |
| **Web Apps** | ❌ | ✅ Ideal | ❌ |
| **Mobile Apps** | ❌ | ✅ Ideal | ❌ |
| **Background Jobs** | ✅ Ideal | ❌ | ✅ Simple only |
| **Public APIs** | ⚠️ | ⚠️ | ✅ Read-only |
| **Internal APIs** | ✅ | ❌ | ✅ |
| **MCP Compliance** | ⚠️ M2M only | ✅ Full | ❌ |

---

## Decision Guide

### Choose **Client Credentials** When:

✅ **Requirements:**
- Service-to-service communication
- No user interaction possible
- Backend systems only
- You control both client and server
- Need scope-based access control
- Require token expiration

✅ **Examples:**
- Lambda function accessing API
- Microservice calling another microservice
- CI/CD pipeline deploying to API
- Scheduled job fetching data
- Your current Lambda MCP implementation

### Choose **OAuth 3LO** When:

✅ **Requirements:**
- User-facing application
- Acting on behalf of users
- Need user consent
- Require user context in tokens
- MCP specification compliance
- Third-party integrations

✅ **Examples:**
- Web application with user login
- Mobile app accessing user data
- Browser extension
- Desktop application
- MCP client in user's browser

### Choose **API Key** When:

✅ **Requirements:**
- Simple internal APIs
- Development/testing only
- Low security requirements
- Quick prototypes
- Public read-only APIs
- No user context needed

✅ **Examples:**
- Internal monitoring dashboard
- Development environment
- Public weather API
- Simple webhook receiver
- Quick proof of concept

---

## Migration Paths

### From API Key → Client Credentials

**Why Migrate:**
- Need token expiration
- Require scope-based access
- Improve security posture
- Prepare for compliance audit

**Steps:**
1. Set up Cognito User Pool
2. Create M2M client with scopes
3. Update client code to fetch tokens
4. Run both systems in parallel
5. Migrate clients gradually
6. Deprecate API keys

**Timeline:** 1-2 weeks

### From Client Credentials → OAuth 3LO

**Why Migrate:**
- Need user-delegated access
- Require user consent
- MCP specification compliance
- Multi-tenant requirements

**Steps:**
1. Enable Authorization Code flow in Cognito
2. Implement PKCE in client
3. Add login/consent UI
4. Update token handling
5. Test user flows
6. Deploy gradually

**Timeline:** 2-4 weeks

### From API Key → OAuth 3LO

**Why Migrate:**
- Moving from internal to public API
- Need user authentication
- Compliance requirements
- Security audit findings

**Steps:**
1. Set up complete OAuth infrastructure
2. Implement full authorization flow
3. Add user management
4. Build consent screens
5. Extensive testing
6. Gradual rollout

**Timeline:** 4-8 weeks

---

## Your Current Implementation

### What You Have

```typescript
// OAuth Client Credentials (M2M)
oAuth: {
  flows: {
    clientCredentials: true
  }
}
```

**This is:**
- ✅ OAuth 2.0 Client Credentials
- ✅ Suitable for M2M communication
- ✅ Secure for server-to-server
- ⚠️ Not MCP-spec compliant (requires OAuth 3LO)

### To Become MCP-Compliant

You would need to add:

```typescript
oAuth: {
  flows: {
    authorizationCodeGrant: true,  // ← Add this
    clientCredentials: true         // Keep this
  }
}
```

Plus:
- PKCE support
- User consent UI
- Protected Resource Metadata endpoint
- WWW-Authenticate headers
- Resource parameter validation

---

## References

- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [OAuth 2.1 Draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- [JWT RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
- [MCP Authorization Spec](https://modelcontextprotocol.io/specification/draft/basic/authorization)
- [AWS Cognito Documentation](https://docs.aws.amazon.com/cognito/)
- [API Gateway API Keys](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-key-source.html)
