# bot.py (Optimized for headless Instagram posting with session management)
import os
import time
import json
import requests
from supabase import create_client, Client
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
# from dotenv import load_dotenv

# load_dotenv()

# --- Environment Variables ---
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
INSTA_USERNAME = os.getenv('INSTA_USERNAME')
INSTA_PASSWORD = os.getenv('INSTA_PASSWORD')

# --- Constants for Session Management ---
SESSIONS_DIR = "sessions"
COOKIE_FILE = os.path.join(SESSIONS_DIR, "insta_cookies.json")

# --- Create necessary folders ---
if not os.path.exists("temp_images"):
    os.makedirs("temp_images")
if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)


def save_cookies(driver, path):
    """Saves browser cookies to a file."""
    with open(path, 'w') as f:
        json.dump(driver.get_cookies(), f)
    print("Session cookies saved.")


def load_cookies(driver, path):
    """Loads browser cookies from a file."""
    with open(path, 'r') as f:
        cookies = json.load(f)
        for cookie in cookies:
            driver.add_cookie(cookie)
    print("Session cookies loaded.")


def handle_popups(driver, wait):
    """Handle 'Save Info' and 'Notifications' popups."""
    # Using more robust selectors and a single try-except block
    try:
        # Using contains() for case-insensitivity ("Not now" vs "Not Now")
        not_now_buttons = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'Not Now')] | //*[text()='Not now']"))
        )
        for button in not_now_buttons:
            try:
                # Use JavaScript click to avoid interception issues
                driver.execute_script("arguments[0].click();", button)
                print("Clicked a 'Not Now' popup.")
                time.sleep(2) # Short pause after a click
            except StaleElementReferenceException:
                continue # Element is gone, which is fine
    except TimeoutException:
        print("No popups found to handle.")
        pass


def login_or_load_session(driver, wait):
    """Tries to load a session from cookies, otherwise logs in normally."""
    driver.get("https://www.instagram.com/")

    if os.path.exists(COOKIE_FILE):
        print("Cookie file found. Loading session...")
        load_cookies(driver, COOKIE_FILE)
        driver.refresh() # Refresh page to apply cookies
        time.sleep(5)

        # Check if login was successful by looking for the "New Post" button
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//*[@aria-label='New post']"))
            )
            print("✅ Successfully logged in using session cookies.")
            return True
        except TimeoutException:
            print("Cookie login failed. Proceeding with manual login.")

    # --- Manual Login ---
    print("Logging into Instagram manually...")
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        wait.until(EC.element_to_be_clickable((By.NAME, "username"))).send_keys(INSTA_USERNAME)
        wait.until(EC.element_to_be_clickable((By.NAME, "password"))).send_keys(INSTA_PASSWORD)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))).click()
        
        # Wait for navigation to homepage after login by looking for a known element
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//*[@aria-label='Home']"))
        )
        print("✅ Manual login successful.")
        
        # Handle popups that appear after first login
        handle_popups(driver, wait)
        
        # Save the session for next time
        save_cookies(driver, COOKIE_FILE)
        return True
    except TimeoutException:
        print("❌ Manual login failed. Check credentials or page structure.")
        driver.save_screenshot("login_error.png") # Save screenshot for debugging
        return False


def post_to_instagram(driver, image_path, caption):
    """Post an image with caption on Instagram."""
    try:
        wait = WebDriverWait(driver, 20)

        print("Navigating to home page to start post...")
        driver.get("https://www.instagram.com/")
        time.sleep(3)

        # Click "New post" - this selector is generally stable
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='New post']"))).click()
        time.sleep(2)
    
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Post']"))).click()
        time.sleep(2)

        # Upload image - Wait for the file input to appear in the modal
        file_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        file_input.send_keys(os.path.abspath(image_path))
        
        # Wait for the "Next" button to become clickable after upload
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and text()='Next']")))
        next_button.click()

        # Second "Next" button (for filters)
        next_button_2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and text()='Next']")))
        next_button_2.click()

        # Add caption
        caption_field = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='Write a caption...']")))
        caption_field.send_keys(caption)
        time.sleep(1)

        # Share post
        share_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and text()='Share']")))
        share_button.click()
        
        # Wait for confirmation that the post was shared
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[text()='Your post has been shared.']")))
        print("🎉 Post shared successfully!")
        return True

    except (TimeoutException, StaleElementReferenceException) as e:
        print(f"Error during posting: {e}")
        driver.save_screenshot("posting_error.png")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during posting: {e}")
        driver.save_screenshot("unexpected_posting_error.png")
        return False


def process_one_confession():
    """Fetch a queued confession, post, and update status."""
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    driver = None

    try:
        response = supabase.table('confessions').select('*').eq('status', 'queued').limit(1).execute()
        if not response.data:
            print("No queued confessions found.")
            return

        confession = response.data[0]
        confession_id = confession['id']
        image_url = confession['image_url']
        content = confession['content']

        print(f"Processing confession #{confession_id}...")
        image_data = requests.get(image_url).content
        local_image_path = os.path.join("temp_images", f"confession_{confession_id}.jpg")
        with open(local_image_path, 'wb') as f:
            f.write(image_data)

        # --- Setup Selenium Driver ---
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
        options.add_argument("--no-first-run") # Suppress the "What's new in Chrome" page and other first-run wizards.
        options.add_argument("--no-default-browser-check") # Disables the check to see if Chrome is the default browser.
        options.add_argument("--disable-features=TranslateUI,AutomationControlled")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 20)

        # --- Login using session or manually ---
        if not login_or_load_session(driver, wait):
            raise Exception("Failed to log into Instagram.")

        # --- Post to Instagram with retry logic ---
        post_successful = False
        for attempt in range(1, 4):
            print(f"Attempt #{attempt} to post confession #{confession_id}...")
            if post_to_instagram(driver, local_image_path, content):
                supabase.table('confessions').update({'status': 'posted'}).eq('id', confession_id).execute()
                post_successful = True
                break
            else:
                print("Retrying in 5 seconds...")
                time.sleep(5)
        
        if not post_successful:
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()
            print("❌ Failed to post after 3 attempts.")

    except Exception as e:
        print(f"Error in main process: {e}")
        # If something fails early, mark the confession as failed
        if 'confession_id' in locals():
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()

    finally:
        if 'local_image_path' in locals() and os.path.exists(local_image_path):
            os.remove(local_image_path) # Clean up image file
        if driver:
            driver.quit()


if __name__ == "__main__":
    process_one_confession()
