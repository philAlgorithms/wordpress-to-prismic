import os
import httpx
from dotenv import load_dotenv
import json
import time

load_dotenv()

def check_migration_status():
    repository_name = os.getenv('PRISMIC_REPOSITORY_NAME')
    api_token = os.getenv('PRISMIC_ACCESS_TOKEN')
    api_key = os.getenv('PRISMIC_MIGRATION_API_KEY')
    
    # Migration API endpoint
    migration_url = "https://migration.prismic.io/status"
    
    headers = {
        'Authorization': f'Bearer {api_token}',
        'repository': repository_name,
        'x-api-key': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        print("\nChecking migration status...")
        response = httpx.get(
            migration_url,
            headers=headers,
            timeout=30.0
        )
        response.raise_for_status()
        
        status_data = response.json()
        
        # Save full response for inspection
        with open('migration_status.json', 'w') as f:
            json.dump(status_data, f, indent=2)
            
        print("\nMigration Status:")
        print("-" * 50)
        print(f"Total documents in migration: {len(status_data.get('documents', []))}")
        
        # Print details of each document
        for doc in status_data.get('documents', []):
            print("\nDocument:")
            print(f"ID: {doc.get('id', 'N/A')}")
            print(f"UID: {doc.get('uid', 'N/A')}")
            print(f"Type: {doc.get('type', 'N/A')}")
            print(f"Status: {'Published' if doc.get('published') else 'Draft'}")
            
        print("\nFull status details saved to 'migration_status.json'")
        
    except Exception as e:
        print(f"Error checking migration status: {str(e)}")

if __name__ == "__main__":
    check_migration_status()