# bot.py (Optimized for headless Instagram posting)
import os
import time
import requests
from supabase import create_client, Client
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
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

# Create temp folder for images
if not os.path.exists("temp_images"):
    os.makedirs("temp_images")


def handle_popups(driver, wait):
    """Handle 'Save Info' and 'Notifications' popups."""
    try:
        save_info = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Not now']")))
        driver.execute_script("arguments[0].click();", save_info)
        time.sleep(2)
    except TimeoutException:
        pass

    try:
        notifications = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Not Now']")))
        driver.execute_script("arguments[0].click();", notifications)
        time.sleep(2)
    except TimeoutException:
        pass


def post_to_instagram(driver, image_path, caption):
    """Post an image with caption on Instagram."""
    try:
        wait = WebDriverWait(driver, 20)

        driver.get("https://www.instagram.com/")
        time.sleep(3)

        # Click "New post"
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='New post']"))).click()
        time.sleep(2)

        # Click "Post" from menu
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Post']"))).click()
        time.sleep(2)

        # Upload image
        file_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
        file_input.send_keys(os.path.abspath(image_path))
        time.sleep(3)

        # Next buttons
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Next']"))).click()
        time.sleep(2)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='Next']"))).click()
        time.sleep(2)

        # Add caption
        caption_field = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='Write a caption...']")))
        caption_field.send_keys(caption)
        time.sleep(1)

        # Share post
        share_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and text()='Share']")))
        share_button.click()
        time.sleep(8)

        print("🎉 Post shared successfully!")
        return True

    except (TimeoutException, StaleElementReferenceException) as e:
        print(f"Error during posting: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def process_one_confession():
    """Fetch a queued confession, post, and update status."""
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    driver = None

    try:
        # Fetch one queued confession
        response = supabase.table('confessions').select('*').eq('status', 'queued').limit(1).execute()
        if not response.data:
            print("No queued confessions found.")
            return

        confession = response.data[0]
        confession_id = confession['id']
        image_url = confession['image_url']
        content = confession['content']

        print(f"Downloading image for confession #{confession_id}...")
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
  # Use new headless mode
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/91.0.4472.124 Safari/537.36")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 20)

        # Login
        print("Logging into Instagram...")
        driver.get("https://www.instagram.com/accounts/login/")
        wait.until(EC.element_to_be_clickable((By.NAME, "username"))).send_keys(INSTA_USERNAME)
        wait.until(EC.element_to_be_clickable((By.NAME, "password"))).send_keys(INSTA_PASSWORD)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))).click()
        time.sleep(5)

        handle_popups(driver, wait)

        # Try posting 3 times if fails
        for attempt in range(1, 4):
            print(f"Attempt #{attempt} to post confession #{confession_id}...")
            if post_to_instagram(driver, local_image_path, content):
                supabase.table('confessions').update({'status': 'posted'}).eq('id', confession_id).execute()
                break
            else:
                print("Retrying in 5 seconds...")
                time.sleep(5)
        else:
            supabase.table('confessions').update({'status': 'failed'}).eq('id', confession_id).execute()
            print("Failed to post after 3 attempts.")

        # Clean up
        os.remove(local_image_path)

    except Exception as e:
        print(f"Error in main process: {e}")

    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    process_one_confession()
