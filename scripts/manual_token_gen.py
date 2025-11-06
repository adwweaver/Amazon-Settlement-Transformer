"""
Manual Zoho OAuth Token Generation
Simpler step-by-step process
"""

CLIENT_ID = "1000.1AUQGRI6QABZXVWRF36S30OW9C9WVC"
CLIENT_SECRET = "70ef0020bd9afc9715e980f85b630a9d4d56e2df37"

print("=" * 70)
print("MANUAL OAUTH TOKEN GENERATION")
print("=" * 70)
print()

# Step 1: Generate authorization URL
auth_url = (
    f"https://accounts.zoho.com/oauth/v2/auth?"
    f"scope=ZohoBooks.fullaccess.all&"
    f"client_id={CLIENT_ID}&"
    f"response_type=code&"
    f"redirect_uri=http://localhost:8080&"
    f"access_type=offline"
)

print("STEP 1: Get Authorization Code")
print("-" * 70)
print("1. Open this URL in your browser:")
print()
print(auth_url)
print()
print("2. Log into Zoho and click 'Accept'")
print("3. You'll be redirected to: http://localhost:8080/?code=XXXXXX")
print("4. Copy the 'code' parameter from the URL (the page won't load - that's OK!)")
print()

# Also create a clickable file
import webbrowser
import time

print("Opening URL in browser...")
webbrowser.open(auth_url)
time.sleep(2)

print()
auth_code = input("Paste the authorization code here: ").strip()

if not auth_code:
    print("❌ No code provided")
    exit()

print()
print("STEP 2: Exchange Code for Refresh Token")
print("-" * 70)

# Build curl command
curl_cmd = (
    f'curl -X POST "https://accounts.zoho.com/oauth/v2/token" '
    f'-d "code={auth_code}" '
    f'-d "client_id={CLIENT_ID}" '
    f'-d "client_secret={CLIENT_SECRET}" '
    f'-d "redirect_uri=http://localhost:8080" '
    f'-d "grant_type=authorization_code"'
)

print("Run this PowerShell command:")
print()
print(curl_cmd)
print()

# Try with Python requests
try:
    import requests
    
    print("Or let me try with Python...")
    print()
    
    token_url = "https://accounts.zoho.com/oauth/v2/token"
    token_data = {
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": "http://localhost:8080",
        "grant_type": "authorization_code"
    }
    
    response = requests.post(token_url, data=token_data)
    result = response.json()
    
    print("Response:")
    print("-" * 70)
    import json
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
            "data_center": "US",
            "api_endpoint": "https://books.zoho.com/api/v3"
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
        print()
        if 'error' in result:
            print(f"Error: {result['error']}")
            
            if result['error'] == 'invalid_code':
                print()
                print("The authorization code expired or was already used.")
                print("Run this script again to get a new code.")
        
except Exception as e:
    print(f"Error: {e}")
    print()
    print("Try running the curl command manually in PowerShell.")
