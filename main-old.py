from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import traceback
import random
import time
import undetected_chromedriver as uc

# Credentials (replace or load securely)
FACEBOOK_EMAIL = "bastejoma8@gmail.com"
FACEBOOK_PASSWORD = "09094398645"

def human_type(element, text, speed=0.1):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(speed / 2, speed * 1.5))

def human_click(driver, element):
    actions = ActionChains(driver)
    actions.move_to_element(element).pause(random.uniform(0.2, 1.5)).click().perform()

def send_message_to_group(driver, group_name, message):
    try:
        # Open Messenger
        driver.get("https://www.facebook.com/messages/")
        time.sleep(random.uniform(3, 6))

        # Search for the group chat
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search Messenger']"))
        )
        human_type(search_box, group_name)
        time.sleep(random.uniform(2, 4))

        # Select the group from search results
        group_chat = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//span[contains(text(), '{group_name}')]/ancestor::a"))
        )
        human_click(driver, group_chat)
        time.sleep(random.uniform(3, 5))

        # Type and send the message
        message_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='textbox' and @aria-label='Message']"))
        )
        human_type(message_box, message)
        time.sleep(random.uniform(1, 2))
        message_box.send_keys(Keys.RETURN)
        print(f"✅ Message sent to '{group_name}'")
        time.sleep(random.uniform(2, 5))

    except Exception as e:
        print(f"❌ Failed to send message: {e}")
        traceback.print_exc()

def enhanced_facebook_login():
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    driver = None
    try:
        driver = uc.Chrome(options=options)
        time.sleep(random.uniform(1, 3))
        driver.get("https://www.facebook.com/")
        time.sleep(random.uniform(2, 5))

        # Login steps (same as before)
        email_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        actions = ActionChains(driver)
        actions.move_to_element(email_field).pause(1).perform()
        
        if random.random() > 0.3:
            for _ in range(random.randint(2, 5)):
                actions.move_by_offset(random.randint(-50, 50), random.randint(-50, 50)).pause(random.uniform(0.2, 1.2)).perform()

        human_type(email_field, FACEBOOK_EMAIL)
        time.sleep(random.uniform(0.5, 2.5))
        
        password_field = driver.find_element(By.NAME, "pass")
        human_type(password_field, FACEBOOK_PASSWORD)
        time.sleep(random.uniform(0.3, 1.8))
        
        login_button = driver.find_element(By.NAME, "login")
        human_click(driver, login_button)
        
        # Check login success
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@aria-label, 'Facebook') and contains(@role, 'navigation')]"))
            )
            print("✅ Login successful!")

            # Send a message to the group chat
            send_message_to_group(driver, "test coc bot", "Hello from the bot!")

        except TimeoutException:
            print("❌ Login failed. Check credentials or page structure.")
            return False

    except Exception as e:
        print(f"🚨 Critical error: {e}")
        traceback.print_exc()
        return False

    finally:
        if driver:
            try:
                driver.quit()  # Ensure clean exit
            except:
                pass  # Ignore cleanup errors

if __name__ == "__main__":
    enhanced_facebook_login()