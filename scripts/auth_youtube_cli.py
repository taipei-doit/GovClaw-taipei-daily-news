import os
# Force OAuth to allow http for localhost
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import google_auth_oauthlib.flow
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]
SCRIPTS_DIR = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = SCRIPTS_DIR / "client_secrets.json"
CREDENTIALS_FILE = SCRIPTS_DIR / "youtube_credentials.json"

flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
    str(CLIENT_SECRETS_FILE), SCOPES, redirect_uri='http://localhost:8080/')

auth_url, _ = flow.authorization_url(prompt='consent')

print("\n=== PLEASE VISIT THIS URL TO AUTHORIZE ===")
print(auth_url)
print("==========================================\n")

auth_response = input("Enter the entire localhost URL you were redirected to: ")
flow.fetch_token(authorization_response=auth_response)
creds = flow.credentials

with open(str(CREDENTIALS_FILE), 'w') as token:
    token.write(creds.to_json())
print("Successfully authenticated and saved new credentials!")