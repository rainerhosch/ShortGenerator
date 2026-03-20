"""
PaperBrief — One-Time YouTube Authentication
Run this script once to authorize your YouTube Channel.
It will create output/.youtube_token.json with the refresh token.
"""

import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Constants based on config.py paths
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT_DIR = Path(__file__).parent
OUTPUT_DIR = ROOT_DIR / "output"

def find_client_secrets():
    exact_match = ROOT_DIR / "client_secrets.json"
    if exact_match.exists():
        return exact_match
    try:
        secrets = list(ROOT_DIR.glob("client_secret*.json"))
        if secrets:
            return secrets[0]
    except Exception:
        pass
    return None

def main():
    print("=== PaperBrief: YouTube Auto-Upload Setup ===")
    
    # Ensure fully reproducible environment for local OAuth server
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "0"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    token_path = OUTPUT_DIR / ".youtube_token.json"
    client_secrets = find_client_secrets()
    
    if not client_secrets:
        print("❌ Error: Could not find client_secrets.json in the project root.")
        print("Please download it from Google Cloud Console (OAuth 2.0 Client IDs for Desktop App).")
        return
        
    print(f"✅ Found client secrets at: {client_secrets.name}")
    print("⏳ Opening browser for authentication...")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets), SCOPES
        )
        # Menggunakan port tetap 8080 agar mudah didaftarkan di Google Cloud
        creds = flow.run_local_server(port=8080)
        
        # Save credentials to token file
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
            
        print(f"🎉 Success! Refresh token saved to {token_path}")
        print("You don't need to run this script again. The scheduler will use this token automatically.")
        
    except Exception as e:
        print(f"❌ Error during authentication: {e}")

if __name__ == "__main__":
    main()
