import json
import os
import urllib.request
import jwt
from jwt.algorithms import RSAAlgorithm
from functools import lru_cache

@lru_cache(maxsize=1)
def get_jwks(region, user_pool_id):
    """Fetch and cache Cognito public keys"""
    url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def lambda_handler(event, context):
    print(f"Authorizer event: {json.dumps(event)}")
    
    try:
        token = event['authorizationToken'].replace('Bearer ', '')
        user_pool_id = os.environ['USER_POOL_ID']
        region = os.environ.get('AWS_REGION', 'us-west-2')  # AWS_REGION is set by Lambda runtime
        expected_issuer = os.environ['COGNITO_ISSUER']
        required_scopes = set(os.environ['REQUIRED_SCOPES'].split())
        
        # Get token header to find correct public key
        header = jwt.get_unverified_header(token)
        
        # Fetch JWKS and find matching key
        jwks = get_jwks(region, user_pool_id)
        key = next((k for k in jwks['keys'] if k['kid'] == header['kid']), None)
        if not key:
            raise Exception('Public key not found in JWKS')
        
        # Convert JWK to public key
        public_key = RSAAlgorithm.from_jwk(key)
        
        # Verify signature and decode claims
        claims = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            issuer=expected_issuer,
            options={"verify_exp": True, "verify_iss": True, "verify_signature": True}
        )
        
        print(f"✅ Token signature verified. Issuer: {claims['iss']}")
        print(f"✅ Token expiration validated. Expires: {claims['exp']}")
        
        # Validate token_use
        if claims.get('token_use') != 'access':
            raise Exception(f"Invalid token_use: {claims.get('token_use')}")
        
        # Validate required scopes
        token_scopes = set(claims.get('scope', '').split())
        if not required_scopes.issubset(token_scopes):
            raise Exception(f'Insufficient scopes. Required: {required_scopes}, Got: {token_scopes}')
        
        print(f"✅ Scopes validated: {token_scopes}")
        
        # Generate Allow policy
        policy = {
            'principalId': claims['client_id'],
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [{
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Allow',
                    'Resource': event['methodArn']
                }]
            },
            'context': {
                'clientId': claims['client_id'],
                'scope': claims.get('scope', ''),
                'issuer': claims['iss'],
                'expiresAt': str(claims['exp'])
            }
        }
        
        print(f"✅ Authorization successful for client: {claims['client_id']}")
        return policy
        
    except jwt.ExpiredSignatureError:
        print("❌ Authorization failed: Token expired")
        raise Exception('Unauthorized')
    except jwt.InvalidIssuerError as e:
        print(f"❌ Authorization failed: Invalid issuer - {str(e)}")
        raise Exception('Unauthorized')
    except jwt.InvalidSignatureError:
        print("❌ Authorization failed: Invalid signature - Token may be forged")
        raise Exception('Unauthorized')
    except jwt.InvalidTokenError as e:
        print(f"❌ Authorization failed: Invalid token - {str(e)}")
        raise Exception('Unauthorized')
    except Exception as e:
        print(f"❌ Authorization failed: {str(e)}")
        raise Exception('Unauthorized')
