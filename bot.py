# bot.py (API Version - No Selenium Needed)
import os
import requests
from supabase import create_client, Client
# from dotenv import load_dotenv

# load_dotenv()

# --- Environment Variables ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# --- NEW: Instagram Graph API Credentials ---
# These will come from your GitHub Secrets
INSTA_BUSINESS_ACCOUNT_ID = os.getenv('INSTA_BUSINESS_ACCOUNT_ID')
INSTA_GRAPH_API_ACCESS_TOKEN = os.getenv('INSTA_GRAPH_API_ACCESS_TOKEN')
GRAPH_API_VERSION = "v19.0" # Use a recent, non-deprecated version

def post_to_instagram_api(image_url, caption):
    """
    Posts a photo to Instagram using the Instagram Graph API.
    This is a two-step process: create a media container, then publish it.
    """
    if not all([INSTA_BUSINESS_ACCOUNT_ID, INSTA_GRAPH_API_ACCESS_TOKEN]):
        print("❌ Error: Instagram API credentials are not set in environment variables.")
        return False

    # --- Step 1: Create a Media Container ---
    container_creation_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{INSTA_BUSINESS_ACCOUNT_ID}/media"
    
    container_payload = {
        'image_url': image_url,
        'caption': caption,
        'access_token': INSTA_GRAPH_API_ACCESS_TOKEN
    }
    
    try:
        print("Step 1: Creating media container...")
        creation_response = requests.post(container_creation_url, data=container_payload)
        creation_data = creation_response.json()

        if 'id' not in creation_data:
            print("❌ Error creating media container:")
            print(creation_data.get('error', 'Unknown error'))
            return False

        container_id = creation_data['id']
        print(f"✅ Media container created successfully with ID: {container_id}")

        # --- Step 2: Publish the Media Container ---
        publish_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{INSTA_BUSINESS_ACCOUNT_ID}/media_publish"
        
        publish_payload = {
            'creation_id': container_id,
            'access_token': INSTA_GRAPH_API_ACCESS_TOKEN
        }
        
        print("Step 2: Publishing media...")
        publish_response = requests.post(publish_url, data=publish_payload)
        publish_data = publish_response.json()

        if 'id' in publish_data:
            print(f"🎉 Post shared successfully! Post ID: {publish_data['id']}")
            return True
        else:
            print("❌ Error publishing media container:")
            print(publish_data.get('error', 'Unknown error'))
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False


def process_one_confession():
    """Fetch a queued confession, post via API, and update status."""
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    confession_id = None # Initialize to handle early errors

    try:
        response = supabase.table('confessions').select('*').eq('status', 'queued').limit(1).execute()
        
        if not response.data:
            print("No queued confessions found. Exiting.")
            return

        confession = response.data[0]
        confession_id = confession['id']
        image_url = confession['image_url']
        content = confession['content']

        print(f"Processing confession #{confession_id}...")

        # Post to Instagram using the new API function
        post_successful = post_to_instagram_api(image_url, content)

        if post_successful:
            supabase.table('confessions').update({'status': 'posted'}).eq('id', confession_id).execute()
            print(f"Updated confession #{confession_id} status to 'posted'.")
        else:
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()
            print(f"Updated confession #{confession_id} status to 'failed'.")

    except Exception as e:
        print(f"An error occurred in the main process: {e}")
        if confession_id:
            # If we know which confession failed, mark it as failed
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()
            print(f"Updated confession #{confession_id} status to 'failed' due to an unexpected error.")


if __name__ == "__main__":
    process_one_confession()
