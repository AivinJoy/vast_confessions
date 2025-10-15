import os
import time
import requests
from supabase import create_client, Client

# --- CONSTANTS & CONFIGURATION ---
# All configuration is now handled by environment variables for security and flexibility.

# Instagram Graph API version and settings
GRAPH_API_VERSION = "v19.0"
POST_MAX_RETRIES = 15  # How many times to check for media processing status
POST_RETRY_DELAY_SECONDS = 4 # How many seconds to wait between checks

# --- ENVIRONMENT VARIABLES ---
# These must be set in your execution environment (e.g., GitHub Secrets, .env file)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_BUCKET_NAME = os.getenv('SUPABASE_BUCKET_NAME')
INSTA_BUSINESS_ACCOUNT_ID = os.getenv('INSTA_BUSINESS_ACCOUNT_ID')
INSTA_GRAPH_API_ACCESS_TOKEN = os.getenv('INSTA_GRAPH_API_ACCESS_TOKEN')


def post_to_instagram_api(image_url, caption):
    """
    Posts a photo to Instagram using the Graph API.
    Waits for the media container to be processed before publishing.
    """
    if not all([INSTA_BUSINESS_ACCOUNT_ID, INSTA_GRAPH_API_ACCESS_TOKEN]):
        print("❌ Error: Instagram API credentials are not set in environment variables.")
        return False

    # --- Step 1: Create Media Container ---
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

        # --- Step 1.5: Poll for Media Processing Status ---
        print(f"⏳ Waiting for Instagram to process media (up to ~{POST_MAX_RETRIES * POST_RETRY_DELAY_SECONDS} seconds)...")
        time.sleep(3)  # small initial delay before polling

        for attempt in range(POST_MAX_RETRIES):
            status_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{container_id}"
            status_params = {
                'fields': 'status_code',
                'access_token': INSTA_GRAPH_API_ACCESS_TOKEN
            }
            status_response = requests.get(status_url, params=status_params)
            status_data = status_response.json()
            status_code = status_data.get('status_code')

            print(f"→ Attempt {attempt + 1}/{POST_MAX_RETRIES}: Media status is '{status_code}'")

            if status_code == "FINISHED":
                print("✅ Media is ready for publishing.")
                break
            elif status_code in ["ERROR", "EXPIRED"]:
                print(f"❌ Media processing failed with status: {status_code}.")
                return False
            
            time.sleep(POST_RETRY_DELAY_SECONDS)
        else:
            # This 'else' block runs only if the 'for' loop completes without a 'break'
            print("❌ Timeout: Media was not ready after multiple checks.")
            return False

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
            print("❌ Error publishing media:")
            print(publish_data.get('error', 'Unknown error'))
            return False

    except requests.exceptions.RequestException as e:
        print(f"An HTTP request error occurred: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during posting: {e}")
        return False


def process_one_confession():
    """
    Fetches one queued confession from Supabase, posts it, updates the status,
    and cleans up the corresponding image from storage.
    """
    if not all([SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET_NAME]):
        print("❌ Error: Supabase credentials or bucket name are missing.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    confession_id = None

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

        post_successful = post_to_instagram_api(image_url, content)

        if post_successful:
            supabase.table('confessions').update({'status': 'posted'}).eq('id', confession_id).execute()
            print(f"✅ Updated confession #{confession_id} status to 'posted'.")

            print("🧹 Cleaning up image from Supabase Storage...")
            try:
                # Extracts the file path from the full URL for deletion
                path_to_delete = image_url.split(f"{SUPABASE_BUCKET_NAME}/")[-1]
                supabase.storage.from_(SUPABASE_BUCKET_NAME).remove([path_to_delete])
                print(f"✅ Successfully deleted '{path_to_delete}' from storage.")
            except Exception as e:
                print(f"⚠️ Could not delete image from storage. Manual cleanup needed. Error: {e}")
        else:
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()
            print(f"❌ Updated confession #{confession_id} status to 'failed'.")

    except Exception as e:
        print(f"💥 A critical error occurred in the main process: {e}")
        if confession_id and supabase:
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()
            print(f"❌ Updated confession #{confession_id} status to 'failed' due to the error.")


if __name__ == "__main__":
    process_one_confession()
