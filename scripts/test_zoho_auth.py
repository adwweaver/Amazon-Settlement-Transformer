"""
Test Zoho Books API Authentication
Verifies credentials and lists chart of accounts
"""

import yaml
import requests
import json
from pathlib import Path

print("=" * 70)
print("ZOHO BOOKS API AUTHENTICATION TEST")
print("=" * 70)
print()

# Load credentials
config_file = Path(__file__).parent.parent / 'config' / 'zoho_credentials.yaml'

if not config_file.exists():
    print(f"❌ Credentials file not found: {config_file}")
    print()
    print("Run: python scripts/generate_zoho_token.py")
    exit()

with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

print("✅ Credentials loaded")
print(f"   Organization ID: {config['organization_id']}")
print(f"   Data Center: {config['data_center']}")
print(f"   API Endpoint: {config['api_endpoint']}")
print()

# Get fresh access token
print("🔄 Refreshing access token...")
print(f"   Using Client ID: {config['client_id'][:20]}...")
print(f"   Using Refresh Token: {config['refresh_token'][:30]}...")
print()

# Use Canada-specific accounts server if configured
accounts_server = config.get('accounts_server', 'https://accounts.zoho.com')
token_url = f"{accounts_server}/oauth/v2/token"

print(f"   Token URL: {token_url}")
print()

token_params = {
    "refresh_token": config['refresh_token'],
    "client_id": config['client_id'],
    "client_secret": config['client_secret'],
    "grant_type": "refresh_token"
}

try:
    response = requests.post(token_url, data=token_params)
    
    token_data = response.json()
    
    # Debug: Print response
    if 'access_token' not in token_data:
        print(f"❌ Token response missing access_token")
        print(f"Response: {json.dumps(token_data, indent=2)}")
        exit()
    
    access_token = token_data['access_token']
    
    print(f"✅ Access token obtained (expires in {token_data['expires_in']}s)")
    print()
    
except requests.exceptions.RequestException as e:
    print(f"❌ Token refresh failed: {e}")
    if 'response' in locals():
        print(f"Response: {response.text}")
    exit()

# Test API: Get Chart of Accounts
print("=" * 70)
print("TESTING API: GET CHART OF ACCOUNTS")
print("=" * 70)
print()

headers = {
    "Authorization": f"Zoho-oauthtoken {access_token}"
}

params = {
    "organization_id": config['organization_id']
}

try:
    api_url = f"{config['api_endpoint']}/chartofaccounts"
    response = requests.get(api_url, headers=headers, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    if data.get('code') == 0:
        print("✅ API call successful!")
        print()
        
        accounts = data.get('chartofaccounts', [])
        print(f"Found {len(accounts)} accounts in your chart of accounts")
        print()
        
        # Filter for Amazon-related accounts
        print("=" * 70)
        print("AMAZON-RELATED ACCOUNTS")
        print("=" * 70)
        print()
        
        amazon_accounts = [acc for acc in accounts if 'amazon' in acc['account_name'].lower()]
        
        if amazon_accounts:
            print("Account ID | Account Name                          | Account Type")
            print("-" * 70)
            for acc in amazon_accounts:
                print(f"{acc['account_id']:<10} | {acc['account_name']:<40} | {acc['account_type']}")
        else:
            print("⚠️  No accounts with 'Amazon' in the name found.")
            print("    You may need to create them first.")
        
        print()
        print("=" * 70)
        print("ALL ACCOUNTS (First 20)")
        print("=" * 70)
        print()
        print("Account ID | Account Name                          | Account Type")
        print("-" * 70)
        
        for acc in accounts[:20]:
            print(f"{acc['account_id']:<10} | {acc['account_name']:<40} | {acc['account_type']}")
        
        if len(accounts) > 20:
            print(f"... and {len(accounts) - 20} more accounts")
        
        print()
        print("=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("1. Identify the Account IDs for your 8 Amazon GL accounts")
        print("2. Update ZOHO_SETUP_CHECKLIST.md with the Account IDs")
        print("3. Run: python scripts/map_gl_accounts.py")
        
    else:
        print(f"❌ API returned error code: {data.get('code')}")
        print(f"   Message: {data.get('message')}")
    
except requests.exceptions.RequestException as e:
    print(f"❌ API call failed: {e}")
    if hasattr(response, 'text'):
        print(f"Response: {response.text}")

print()
