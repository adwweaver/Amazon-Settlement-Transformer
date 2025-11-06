#!/usr/bin/env python3
"""
Deploy Amazon Settlement Processor to SharePoint

This script helps set up the web app for SharePoint deployment.
It checks requirements and provides deployment instructions.

Usage:
    python scripts/deploy_to_sharepoint.py
"""

import sys
from pathlib import Path
import subprocess
import os

def check_requirements():
    """Check if all requirements are met"""
    print("="*80)
    print("DEPLOYMENT REQUIREMENTS CHECK")
    print("="*80)
    print()
    
    requirements_met = True
    
    # Check Python
    print("1. Checking Python...")
    try:
        result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
        print(f"   ✅ Python: {result.stdout.strip()}")
    except Exception as e:
        print(f"   ❌ Python not found: {e}")
        requirements_met = False
    
    # Check Streamlit
    print("\n2. Checking Streamlit...")
    try:
        import streamlit
        print(f"   ✅ Streamlit: {streamlit.__version__}")
    except ImportError:
        print("   ❌ Streamlit not installed")
        print("   Installing Streamlit...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "streamlit"], check=True)
            print("   ✅ Streamlit installed successfully")
        except Exception as e:
            print(f"   ❌ Failed to install Streamlit: {e}")
            requirements_met = False
    
    # Check project structure
    print("\n3. Checking project structure...")
    project_root = Path(__file__).parent.parent
    
    required_files = [
        "scripts/web_app.py",
        "scripts/main.py",
        "config/config.yaml",
        "requirements.txt"
    ]
    
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} not found")
            requirements_met = False
    
    # Check SharePoint access
    print("\n4. Checking SharePoint access...")
    sharepoint_path = Path(os.path.expanduser(
        r"~\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL"
    ))
    
    if sharepoint_path.exists():
        print(f"   ✅ SharePoint path accessible: {sharepoint_path}")
    else:
        print(f"   ⚠️  SharePoint path not found: {sharepoint_path}")
        print("   Note: This is okay if you're deploying to Streamlit Cloud")
    
    print("\n" + "="*80)
    
    return requirements_met


def check_github_access():
    """Check if GitHub is configured"""
    print("\n5. Checking GitHub access...")
    try:
        result = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            print("   ✅ GitHub remote configured")
            print(f"   {result.stdout.strip()}")
            return True
        else:
            print("   ⚠️  No GitHub remote configured")
            print("   Note: Required for Streamlit Cloud deployment")
            return False
    except Exception:
        print("   ⚠️  Git not available")
        return False


def create_deployment_files():
    """Create deployment helper files"""
    project_root = Path(__file__).parent.parent
    
    # Create .streamlit/config.toml
    streamlit_config_dir = project_root / '.streamlit'
    streamlit_config_dir.mkdir(exist_ok=True)
    
    config_file = streamlit_config_dir / 'config.toml'
    config_content = """[server]
port = 8501
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
"""
    
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"   ✅ Created Streamlit config: {config_file}")
    
    # Create .streamlit/credentials.toml (empty for now)
    creds_file = streamlit_config_dir / 'credentials.toml'
    if not creds_file.exists():
        with open(creds_file, 'w') as f:
            f.write("# Streamlit Cloud credentials\n")
        print(f"   ✅ Created Streamlit credentials file: {creds_file}")


def create_sharepoint_embed_code():
    """Create SharePoint embed code"""
    embed_code = """<!-- Amazon Settlement Processor - SharePoint Embed Code -->
<!-- Copy this code to your SharePoint page -->

<!-- Option 1: Iframe Embed (Recommended) -->
<div style="width: 100%; height: 800px; border: 1px solid #ccc;">
    <iframe 
        src="YOUR_STREAMLIT_CLOUD_URL_HERE" 
        width="100%" 
        height="100%" 
        frameborder="0"
        style="border: none;">
    </iframe>
</div>

<!-- Option 2: Direct Link Button -->
<a href="YOUR_STREAMLIT_CLOUD_URL_HERE" target="_blank" 
   style="display: inline-block; padding: 10px 20px; background: #0066cc; color: white; text-decoration: none; border-radius: 4px;">
   Open Amazon Settlement Processor
</a>
"""
    
    embed_file = Path(__file__).parent.parent / 'sharepoint_embed_code.html'
    with open(embed_file, 'w') as f:
        f.write(embed_code)
    
    print(f"   ✅ Created SharePoint embed code: {embed_file}")
    
    return embed_file


def print_deployment_instructions():
    """Print deployment instructions"""
    print("\n" + "="*80)
    print("DEPLOYMENT INSTRUCTIONS")
    print("="*80)
    print()
    
    print("OPTION 1: Streamlit Cloud (Recommended - Free)")
    print("-" * 80)
    print("1. Push code to GitHub:")
    print("   git add scripts/web_app.py requirements.txt .streamlit/")
    print("   git commit -m 'Add Streamlit web app'")
    print("   git push")
    print()
    print("2. Deploy to Streamlit Cloud:")
    print("   a. Go to: https://share.streamlit.io")
    print("   b. Sign in with GitHub")
    print("   c. Click 'New app'")
    print("   d. Select your repository: Amazon-Settlement-Transformer")
    print("   e. Main file path: scripts/web_app.py")
    print("   f. Click 'Deploy'")
    print()
    print("3. Get your app URL:")
    print("   https://amazon-settlement-transformer.streamlit.app")
    print()
    print("4. Embed in SharePoint:")
    print("   a. Go to your SharePoint page:")
    print("      https://touchstonebrandscanada.sharepoint.com/sites/BrackishCo/SitePages/CollabHome.aspx")
    print("   b. Edit the page")
    print("   c. Add 'Embed' web part")
    print("   d. Use the code from: sharepoint_embed_code.html")
    print("   e. Replace YOUR_STREAMLIT_CLOUD_URL_HERE with your app URL")
    print()
    
    print("OPTION 2: Local Server (For Testing)")
    print("-" * 80)
    print("1. Run locally:")
    print("   streamlit run scripts/web_app.py")
    print()
    print("2. Access at: http://localhost:8501")
    print()
    print("3. For SharePoint access:")
    print("   - Run on a server accessible from your network")
    print("   - Use: streamlit run scripts/web_app.py --server.address 0.0.0.0")
    print("   - Embed using server IP in SharePoint")
    print()
    
    print("="*80)


def main():
    """Main deployment function"""
    print("="*80)
    print("AMAZON SETTLEMENT PROCESSOR - SHAREPOINT DEPLOYMENT")
    print("="*80)
    print()
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Some requirements are not met. Please fix the issues above.")
        return
    
    # Check GitHub
    github_ok = check_github_access()
    
    # Create deployment files
    print("\n6. Creating deployment files...")
    create_deployment_files()
    
    # Create SharePoint embed code
    print("\n7. Creating SharePoint embed code...")
    embed_file = create_sharepoint_embed_code()
    
    # Print instructions
    print_deployment_instructions()
    
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print()
    
    if github_ok:
        print("✅ GitHub is configured. You can deploy to Streamlit Cloud now!")
        print("\n1. Run: git add scripts/web_app.py requirements.txt .streamlit/")
        print("2. Run: git commit -m 'Add Streamlit web app'")
        print("3. Run: git push")
        print("4. Go to: https://share.streamlit.io and deploy")
    else:
        print("⚠️  GitHub remote not configured.")
        print("   To deploy to Streamlit Cloud:")
        print("   1. Create a GitHub repository")
        print("   2. Run: git remote add origin YOUR_REPO_URL")
        print("   3. Run: git push -u origin main")
        print("   4. Then deploy on Streamlit Cloud")
    
    print("\nSharePoint embed code saved to: sharepoint_embed_code.html")
    print("="*80)


if __name__ == "__main__":
    main()



