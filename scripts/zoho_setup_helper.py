"""
Zoho Books Setup Helper
Helps gather required information for API integration
"""

print("=" * 70)
print("ZOHO BOOKS API SETUP HELPER")
print("=" * 70)
print()

print("I need the following information to build the integration:")
print()

print("=" * 70)
print("1. ORGANIZATION ID")
print("=" * 70)
print("How to find:")
print("  1. Log into Zoho Books")
print("  2. Go to: Settings → Organization Profile")
print("  3. Look for 'Organization ID' field")
print("  4. Copy the number (usually 10-12 digits)")
print()
print("Enter your Organization ID: ", end="")
org_id = input().strip()
print()

print("=" * 70)
print("2. DATA CENTER")
print("=" * 70)
print("How to find:")
print("  1. Look at your Zoho Books URL in the browser")
print("  2. Identify your data center:")
print()
print("     books.zoho.com      → US")
print("     books.zoho.eu       → EU")
print("     books.zoho.in       → IN")
print("     books.zoho.com.au   → AU")
print("     books.zoho.com.cn   → CN")
print("     books.zoho.jp       → JP")
print()
print("Enter your data center (US/EU/IN/AU/CN/JP): ", end="")
dc = input().strip().upper()
print()

# Map data center to API endpoint
dc_map = {
    "US": "https://books.zoho.com/api/v3",
    "EU": "https://books.zoho.eu/api/v3",
    "IN": "https://books.zoho.in/api/v3",
    "AU": "https://books.zoho.com.au/api/v3",
    "CN": "https://books.zoho.com.cn/api/v3",
    "JP": "https://books.zoho.jp/api/v3"
}

api_endpoint = dc_map.get(dc, "https://books.zoho.com/api/v3")

print("=" * 70)
print("3. AUTHENTICATION METHOD")
print("=" * 70)
print("Choose your authentication method:")
print()
print("Option A: Use existing Zoho Creator/Flow connection")
print("  - Easier if you already have Zoho Creator")
print("  - Uses your existing 'amz_remit_api' connection")
print("  - Requires building a Creator webhook function")
print()
print("Option B: Direct Python API access")
print("  - Need to create OAuth credentials at api-console.zoho.com")
print("  - Direct connection from Python to Zoho Books")
print("  - Requires Client ID, Client Secret, and Refresh Token")
print()
print("Which option do you prefer? (A/B): ", end="")
auth_method = input().strip().upper()
print()

# Save configuration
config = {
    "organization_id": org_id,
    "data_center": dc,
    "api_endpoint": api_endpoint,
    "auth_method": auth_method,
    "connection_name": "amz_remit_api"
}

print("=" * 70)
print("4. CHART OF ACCOUNTS MAPPING")
print("=" * 70)
print("I need the Zoho Account IDs for your GL accounts.")
print()
print("How to find Account IDs:")
print("  1. Go to: Accountant → Chart of Accounts")
print("  2. Click on each account name")
print("  3. Look at the URL: .../chartofaccounts/{ACCOUNT_ID}")
print("  4. Copy the numeric ID")
print()
print("Or use this API call to list all accounts:")
print(f"  GET {api_endpoint}/chartofaccounts?organization_id={org_id}")
print()

gl_accounts = [
    "Amazon.ca Clearing",
    "Amazon.ca Revenue", 
    "Amazon FBA Fulfillment Fees",
    "Amazon Advertising Expense",
    "Amazon FBA Storage Fees",
    "Amazon FBA Inbound Freight",
    "Amazon Account Fees",
    "Amazon Unclassified"
]

print("Would you like to enter Account IDs now? (y/n): ", end="")
enter_accounts = input().strip().lower()
print()

account_mapping = {}
if enter_accounts == 'y':
    for account_name in gl_accounts:
        print(f"Zoho Account ID for '{account_name}': ", end="")
        account_id = input().strip()
        if account_id:
            account_mapping[account_name] = account_id
    print()

config["account_mapping"] = account_mapping

print("=" * 70)
print("CONFIGURATION SUMMARY")
print("=" * 70)
print(f"Organization ID: {org_id}")
print(f"Data Center: {dc}")
print(f"API Endpoint: {api_endpoint}")
print(f"Auth Method: {'Zoho Creator/Flow' if auth_method == 'A' else 'Direct Python API'}")
print(f"Connection: amz_remit_api")
print()
if account_mapping:
    print("GL Account Mappings:")
    for name, acc_id in account_mapping.items():
        print(f"  {name}: {acc_id}")
print()

# Save to YAML
print("=" * 70)
print("NEXT STEPS")
print("=" * 70)

if auth_method == 'A':
    print("✅ Step 1: I'll create a Zoho Creator webhook function")
    print("✅ Step 2: You'll deploy it to your Creator app")
    print("✅ Step 3: Python will POST settlement data to the webhook")
    print("✅ Step 4: Webhook uses your 'amz_remit_api' connection to post to Books")
else:
    print("✅ Step 1: Create OAuth credentials at https://api-console.zoho.com/")
    print("   - Client Name: Amazon Remittance Python")
    print("   - Scope: ZohoBooks.fullaccess.all")
    print("✅ Step 2: Generate Refresh Token (I'll provide script)")
    print("✅ Step 3: Add credentials to config/zoho_credentials.yaml")
    print("✅ Step 4: Test authentication with read-only API calls")

print()
print("Saving configuration to config/zoho_config_draft.yaml...")

import yaml
import os

config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
os.makedirs(config_dir, exist_ok=True)

config_file = os.path.join(config_dir, 'zoho_config_draft.yaml')
with open(config_file, 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

print(f"✅ Configuration saved to: {config_file}")
print()
print("Review the file and provide any missing information!")
