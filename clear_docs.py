
# Script to clean up Google Drive documents
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import os

# Load Google service account credentials from environment
creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
credentials = service_account.Credentials.from_service_account_info(
    creds, scopes=['https://www.googleapis.com/auth/drive.file']
)

# Initialize Google Drive API service
drive_service = build('drive', 'v3', credentials=credentials)

# Query to find all Google Docs owned by service account
results = drive_service.files().list(q="mimeType='application/vnd.google-apps.document'").execute()
files = results.get('files', [])

# Delete all found documents
for file in files:
    print(f'Deleting {file["name"]}')
    drive_service.files().delete(fileId=file['id']).execute()

print('All docs deleted')
