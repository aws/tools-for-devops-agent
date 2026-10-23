#!/usr/bin/env python3
"""
Test Lambda MCP endpoint with proper authentication
"""

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import requests
import json
import os

def load_config():
    """Load configuration from mcp-server-config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'mcp-server-config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def get_token(config):
    auth_config = config['authorization_configuration']
    scope = ' '.join([param['value'] for param in auth_config['exchange_parameters'] if param['key'] == 'scope'])
    
    response = requests.post(
        auth_config['exchange_url'],
        data={'grant_type': 'client_credentials', 'scope': scope},
        auth=(auth_config['client_id'], auth_config['client_secret']),
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    return response.json()['access_token']

def create_transport(mcp_url, token):
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {token}"})

def test_direct_http(config):
    """Test direct HTTP call to Lambda MCP endpoint"""
    token = get_token(config)
    url = config['endpoint']
    
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }
    
    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.status_code == 200

def run_agent():
    config = load_config()
    token = get_token(config)
    print("✅ Authenticated")
    
    # Test direct HTTP first
    if not test_direct_http(config):
        print("❌ Direct HTTP test failed")
        return
    
    print("✅ Direct HTTP test passed")
    
    # Use the MCP endpoint from config
    mcp_url = config['endpoint']
    
    model = BedrockModel(inference_profile_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0", streaming=True)
    mcp_client = MCPClient(lambda: create_transport(mcp_url, token))
    
    try:
        with mcp_client:
            tools = mcp_client.list_tools_sync()
            agent = Agent(model=model, tools=tools)
            print(f"✅ Agent ready with {len(tools)} MCP tools")
            
            while True:
                query = input("\n🔍 Query: ").strip()
                if query.lower() in ['quit', 'q']: break
                if not query: continue
                
                try:
                    response = agent(query)
                    content = response.message.get('content', '') if hasattr(response, 'message') and response.message else response
                    
                    if isinstance(content, list):
                        for item in content:
                            if item.get('type') == 'text':
                                print(f"🤖 {item.get('text', '')}")
                    else:
                        print(f"🤖 {content}")
                except Exception as e:
                    print(f"❌ {e}")
    except Exception as e:
        print(f"❌ MCP Client failed: {e}")

if __name__ == "__main__":
    run_agent()
