"""
Zoho Canada OAuth Token Generator
"""

import webbrowser

CLIENT_ID = "1000.1AUQGRI6QABZXVWRF36S30OW9C9WVC"
CLIENT_SECRET = "70ef0020bd9afc9715e980f85b630a9d4d56e2df37"

print("=" * 70)
print("ZOHO CANADA OAUTH SETUP")
print("=" * 70)
print()

# Canada-specific auth URL
auth_url = (
    f"https://accounts.zohocloud.ca/oauth/v2/auth?"
    f"scope=ZohoBooks.fullaccess.all&"
    f"client_id={CLIENT_ID}&"
    f"response_type=code&"
    f"redirect_uri=http://localhost:8080&"
    f"access_type=offline"
)

print("STEP 1: Get Authorization Code")
print("-" * 70)
print("Opening authorization URL in browser...")
print()

webbrowser.open(auth_url)

print("After approving:")
print("1. You'll be redirected to: http://localhost:8080/?code=XXXXXX")
print("2. Copy ONLY the code value (after 'code=')")
print("3. Paste it below quickly (codes expire in 2 minutes!)")
print()

auth_code = input("Paste authorization code: ").strip()

if not auth_code:
    print("❌ No code provided")
    exit()

print()
print("🔄 Exchanging code for refresh token...")

import requests
import json

token_url = "https://accounts.zohocloud.ca/oauth/v2/token"
token_data = {
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": "http://localhost:8080",
    "grant_type": "authorization_code"
}

response = requests.post(token_url, data=token_data)
result = response.json()

print()
print("Response:")
print("-" * 70)
print(json.dumps(result, indent=2))
print()

if 'access_token' in result:
    print("=" * 70)
    print("✅ SUCCESS!")
    print("=" * 70)
    print()
    print(f"Refresh Token: {result['refresh_token']}")
    print()
    
    # Save to config
    import yaml
    from pathlib import Path
    
    config = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": result['refresh_token'],
        "organization_id": "110001648299",
        "data_center": "CA",
        "accounts_server": "https://accounts.zohocloud.ca",
        "api_endpoint": "https://books.zohocloud.ca/api/v3"
    }
    
    config_file = Path(__file__).parent.parent / 'config' / 'zoho_credentials.yaml'
    with open(config_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"✅ Saved to: {config_file}")
    print()
    print("Now run: python scripts/test_zoho_auth.py")
    
else:
    print("=" * 70)
    print("❌ FAILED")
    print("=" * 70)
    if 'error' in result:
        print(f"Error: {result['error']}")
