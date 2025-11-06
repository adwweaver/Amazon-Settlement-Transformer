"""
Zoho Books OAuth Token Generator
Step-by-step guide to generate Refresh Token
"""

import webbrowser
import urllib.parse
import json

print("=" * 70)
print("ZOHO BOOKS OAUTH SETUP - STEP BY STEP")
print("=" * 70)
print()

# Configuration
CLIENT_ID = input("Enter your Client ID (or press Enter to get one first): ").strip()

if not CLIENT_ID:
    print()
    print("=" * 70)
    print("STEP 1: CREATE OAUTH CLIENT")
    print("=" * 70)
    print("1. I'll open https://api-console.zoho.com/ in your browser")
    print("2. Click 'Add Client' → 'Server-based Applications'")
    print("3. Fill in:")
    print("   - Client Name: Amazon Remittance Python")
    print("   - Homepage URL: http://localhost")
    print("   - Authorized Redirect URI: http://localhost:8080")
    print("4. Click 'CREATE'")
    print("5. Copy the Client ID and Client Secret")
    print()
    input("Press Enter to open api-console.zoho.com...")
    webbrowser.open("https://api-console.zoho.com/")
    print()
    print("After creating the client, run this script again with your Client ID.")
    exit()

CLIENT_SECRET = input("Enter your Client Secret: ").strip()

if not CLIENT_SECRET:
    print("❌ Client Secret is required!")
    exit()

print()
print("=" * 70)
print("STEP 2: GENERATE AUTHORIZATION CODE")
print("=" * 70)

# Build authorization URL
scope = "ZohoBooks.fullaccess.all"
redirect_uri = "http://localhost:8080"
access_type = "offline"

auth_params = {
    "scope": scope,
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "access_type": access_type
}

auth_url = f"https://accounts.zoho.com/oauth/v2/auth?{urllib.parse.urlencode(auth_params)}"

print("I'll open the authorization URL in your browser.")
print("1. Log into Zoho if prompted")
print("2. Click 'Accept' to grant permissions")
print("3. You'll be redirected to: http://localhost:8080/?code=XXXXX")
print("4. Copy the 'code' parameter from the URL")
print("   (The page won't load - that's OK! Just copy the code from the URL)")
print()
input("Press Enter to open authorization URL...")
webbrowser.open(auth_url)
print()

auth_code = input("Paste the authorization code here: ").strip()

if not auth_code:
    print("❌ Authorization code is required!")
    exit()

print()
print("=" * 70)
print("STEP 3: EXCHANGE CODE FOR REFRESH TOKEN")
print("=" * 70)

# Generate curl command for token exchange
token_url = "https://accounts.zoho.com/oauth/v2/token"
token_params = {
    "code": auth_code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": redirect_uri,
    "grant_type": "authorization_code"
}

# Create curl command
curl_cmd = f'curl -X POST "{token_url}" '
for key, value in token_params.items():
    curl_cmd += f'-d "{key}={value}" '

print("Run this command in PowerShell:")
print()
print(curl_cmd)
print()
print("Or I can try to run it for you...")
print()

run_now = input("Run token exchange now? (y/n): ").strip().lower()

if run_now == 'y':
    import requests
    
    print()
    print("🔄 Exchanging authorization code for refresh token...")
    
    try:
        response = requests.post(token_url, data=token_params)
        
        token_data = response.json()
        
        # Check for errors
        if 'error' in token_data:
            print()
            print("=" * 70)
            print("❌ TOKEN GENERATION FAILED")
            print("=" * 70)
            print(f"Error: {token_data.get('error')}")
            print(f"Details: {json.dumps(token_data, indent=2)}")
            print()
            exit()
        
        if 'access_token' not in token_data:
            print()
            print("=" * 70)
            print("❌ UNEXPECTED RESPONSE")
            print("=" * 70)
            print(f"Response: {json.dumps(token_data, indent=2)}")
            print()
            exit()
        
        print()
        print("=" * 70)
        print("✅ SUCCESS! TOKEN GENERATED")
        print("=" * 70)
        print()
        print(f"Access Token: {token_data.get('access_token', 'N/A')[:20]}...")
        print(f"Refresh Token: {token_data.get('refresh_token', 'N/A')}")
        print(f"Expires In: {token_data.get('expires_in', 'N/A')} seconds")
        print()
        
        # Save to config file
        print("=" * 70)
        print("SAVING CREDENTIALS")
        print("=" * 70)
        
        config = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": token_data.get('refresh_token'),
            "organization_id": "110001648299",
            "data_center": "US",
            "api_endpoint": "https://books.zoho.com/api/v3"
        }
        
        import yaml
        import os
        
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        config_file = os.path.join(config_dir, 'zoho_credentials.yaml')
        
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"✅ Credentials saved to: {config_file}")
        print()
        print("⚠️  IMPORTANT: Add this file to .gitignore!")
        print()
        
        # Update .gitignore
        gitignore_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.gitignore')
        
        gitignore_entries = [
            "config/zoho_credentials.yaml",
            "config/zoho_*.yaml",
            "*.yaml"
        ]
        
        try:
            with open(gitignore_file, 'r') as f:
                existing = f.read()
            
            with open(gitignore_file, 'a') as f:
                f.write("\n# Zoho API Credentials\n")
                for entry in gitignore_entries:
                    if entry not in existing:
                        f.write(f"{entry}\n")
            
            print("✅ Added zoho_credentials.yaml to .gitignore")
        except FileNotFoundError:
            print("⚠️  No .gitignore found - create one to protect credentials!")
        
        print()
        print("=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("✅ Step 1: Credentials saved ✓")
        print("✅ Step 2: Test authentication (run: python scripts/test_zoho_auth.py)")
        print("✅ Step 3: Map GL accounts")
        print("✅ Step 4: Test posting with dry-run mode")
        
    except requests.exceptions.RequestException as e:
        print()
        print(f"❌ Error: {e}")
        print()
        print("Response:", response.text if 'response' in locals() else "No response")
        print()
        print("Try running the curl command manually and paste the refresh_token.")

else:
    print()
    print("Run the curl command above and look for 'refresh_token' in the response.")
    print("Then manually create config/zoho_credentials.yaml with:")
    print()
    print("client_id: " + CLIENT_ID)
    print("client_secret: " + CLIENT_SECRET)
    print("refresh_token: YOUR_REFRESH_TOKEN_HERE")
    print("organization_id: 110001648299")
    print("data_center: US")
    print("api_endpoint: https://books.zoho.com/api/v3")
