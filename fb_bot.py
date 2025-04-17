import pickle
import os
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import undetected_chromedriver as uc
import random
import time
import logging
from config import FACEBOOK_EMAIL, FACEBOOK_PASSWORD, FB_GC_ID

logger = logging.getLogger(__name__)
COOKIE_FILE = "fb_session_cookies.pkl"

class FacebookMessenger:
    def __init__(self):
        self.driver = None

    def human_type(self, element, text, speed=0.1):
        """Type like a human with random delays"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(speed / 2, speed * 1.5))

    def human_click(self, element):
        """Simulate a human-like click on a web element"""
        ActionChains(self.driver).move_to_element(element).pause(random.uniform(0.1, 0.3)).click().perform()

    def save_cookies(self):
        """Save current session cookies to file."""
        logger.info("🔄 Saving cookies...")
        try:
            if "facebook.com" not in self.driver.current_url:
                self.driver.get("https://www.facebook.com/")
                time.sleep(2)

            with open(COOKIE_FILE, "wb") as file:
                pickle.dump(self.driver.get_cookies(), file)

            logger.info("✅ Session cookies saved successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save cookies: {str(e)}")
            return False

    def load_cookies(self):
        """Load cookies from file and add to driver."""
        logger.info("🔄 Loading cookies from file...")
        if not os.path.exists(COOKIE_FILE):
            return False

        try:
            self.driver.get("https://www.facebook.com/")
            time.sleep(2)

            with open(COOKIE_FILE, "rb") as file:
                cookies = pickle.load(file)

            self.driver.delete_all_cookies()
            time.sleep(1)

            for cookie in cookies:
                if all(k in cookie for k in ['name', 'value', 'domain']) and 'facebook.com' in cookie['domain']:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"⚠️ Could not add cookie {cookie.get('name', '')}: {str(e)}")

            logger.info("🔄 Session cookies loaded")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load cookies: {str(e)}")
            return False

    def verify_login(self, timeout=15):
        """Verify if user is logged in by checking key elements."""
        logger.info("🔄 Verifying user...")
        try:
            checks = [
                EC.presence_of_element_located((By.XPATH, "//a[@href='/messages/']")),
                EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Facebook']")),
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Marketplace')]"))
            ]
            for check in checks:
                try:
                    WebDriverWait(self.driver, timeout).until(check)
                    return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"❌ Login verification failed: {str(e)}")
            return False

    def try_cookie_login(self):
        """Attempt login using saved cookies."""
        logger.info("🔄 Attempting to login using saved cookies...")
        try:
            self.driver.get("https://www.facebook.com/")
            time.sleep(2)

            if not self.load_cookies():
                return False

            self.driver.refresh()
            time.sleep(3)

            if self.verify_login(timeout=10):
                logger.info("✅ Logged in via cookies")
                self.save_cookies()
                return True

            logger.warning("⚠️ Cookies appear to be expired")
            return False

        except Exception as e:
            logger.warning(f"⚠️ Cookie login failed: {str(e)}")
            return False

    def handle_captcha(self):
        """Handle CAPTCHA manually."""
        try:
            logger.warning("🛑 CAPTCHA detected! Please solve it manually.")
            input("⏳ After solving CAPTCHA, press ENTER to continue...")
            time.sleep(3)

            if self.verify_login():
                self.save_cookies()
                return True

            logger.error("❌ CAPTCHA may not have been solved correctly")
            return False

        except Exception as e:
            logger.error(f"❌ CAPTCHA handling failed: {str(e)}")
            return False

    def is_element_present(self, by, value, timeout=5):
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except:
            return False

    def automated_login(self):
        """Automate login with username/password."""
        logger.info("🔄 Automating login...")
        try:
            self.driver.get("https://www.facebook.com/")
            time.sleep(random.uniform(2, 4))

            email_field = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            self.human_type(email_field, FACEBOOK_EMAIL)
            time.sleep(random.uniform(0.5, 1.5))

            password_field = self.driver.find_element(By.NAME, "pass")
            self.human_type(password_field, FACEBOOK_PASSWORD)
            time.sleep(random.uniform(0.5, 1.5))

            login_button = self.driver.find_element(By.NAME, "login")
            self.human_click(login_button)
            time.sleep(5)

            captcha_triggered = any([
                "checkpoint" in self.driver.current_url.lower(),
                self.is_element_present(By.ID, "captcha_form"),
                self.is_element_present(By.XPATH, "//*[contains(text(),'Enter the text you see')]"),
                self.is_element_present(By.XPATH, "//input[@name='captcha_response']"),
                self.is_element_present(By.XPATH, "//img[contains(@src,'captcha')]")
            ])

            if captcha_triggered:
                if not self.handle_captcha():
                    raise Exception("CAPTCHA solving failed")

            if not self.verify_login():
                raise Exception("Login verification failed")

            self.save_cookies()
            logger.info("✅ Login successful")
            return True

        except Exception as e:
            logger.error(f"❌ Automated login failed: {str(e)}")
            return False

    def login(self):
        """Robust login handler combining cookie and automated login."""
        try:
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--start-maximized")
            self.driver = uc.Chrome(options=options)

            if self.try_cookie_login():
                return True

            logger.info("🔁 No valid cookies, trying automated login")

             # 🚨 Close the old driver and reopen for fresh login
            self.driver.quit()

            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--start-maximized")
            self.driver = uc.Chrome(options=options)

            return self.automated_login()

        except Exception as e:
            logger.error(f"❌ Critical login failure: {str(e)}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            return False

    def get_latest_messages(self, fb_gc_id=None, limit=5):
        try:
            fb_gc_id = str(fb_gc_id) if fb_gc_id is not None else None

            # Make sure we're on the correct messenger page
            if fb_gc_id and fb_gc_id not in self.driver.current_url:
                self.driver.get(f"https://www.facebook.com/messages/t/{fb_gc_id}")
                time.sleep(3)  # Wait for page load

            # Wait for the chat container to load
            chat_container = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='main']"))
            )
            
            # Scroll to bottom of chat to load recent messages
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", 
                chat_container
            )
            time.sleep(2)

            # Try to find messages using different selectors
            messages = []
            try:
                # Find all message containers
                message_elements = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH, 
                        "//div[@role='row' and contains(@class, 'x1n2onr6')]"
                    ))
                )

                for element in message_elements[-limit:]:  # Get only the latest messages
                    try:
                        # Try to get sender name
                        try:
                            sender = element.find_element(
                                By.XPATH,
                                ".//a[@role='link']//span[contains(@class, 'x1lliihq')]"
                            ).text.strip()
                        except:
                            sender = "Unknown"

                        # Try to get message text
                        try:
                            message_text = element.find_element(
                                By.XPATH,
                                ".//div[@dir='auto']"
                            ).text.strip()
                        except:
                            continue  # Skip if no message text found

                        if message_text:
                            messages.append({
                                "sender": sender,
                                "message": message_text
                            })
                            logger.info(f"Found message - {sender}: {message_text}")

                    except Exception as msg_error:
                        logger.debug(f"Error processing message: {str(msg_error)}")
                        continue

            except Exception as e:
                logger.error(f"Error finding messages: {str(e)}")
                # Try alternative selector
                try:
                    message_elements = self.driver.find_elements(
                        By.XPATH,
                        "//div[contains(@class, 'x1y1aw1k')]//div[@dir='auto']"
                    )
                    
                    for element in message_elements[-limit:]:
                        message_text = element.text.strip()
                        if message_text:
                            messages.append({
                                "sender": "Unknown",
                                "message": message_text
                            })
                            logger.info(f"Found message (alternative): {message_text}")

                except Exception as alt_error:
                    logger.error(f"Alternative selector failed: {str(alt_error)}")

            if not messages:
                logger.warning("No messages found in chat")
                # Save debug information
                self.driver.save_screenshot("chat_debug.png")
                with open("chat_source.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)

            return messages

        except Exception as e:
            logger.exception(f"Failed to read messages: {str(e)}")
            return []


    def parse_command(self, text):
        """Parse and respond to known commands"""
        text = text.lower()

        if text.startswith("!hey") or "hey bot" in text:
            return "hello there!"
        elif text.startswith("!status"):
            return "I'm online and listening!"
        elif text.startswith("!joke"):
            return random.choice([
                # 👨‍💻 Programming Jokes
                "Why don’t programmers like nature? It has too many bugs.",
                "Why do Java developers wear glasses? Because they don’t C#.",
                "How do you comfort a JavaScript bug? You console it.",
                "I told my computer I needed a break, and now it won’t stop sending me KitKat ads.",
                "Programmer’s diet: food() && sleep() && code();",

                # 🏰 Clash of Clans Jokes
                "Why did the Barbarian go to school? To improve his *clash*ifications.",
                "Why did the Archer break up with the Giant? She needed space... 5 tiles, to be exact.",
                "Why did the Clan Castle refuse to talk? It didn’t want to *clash*.",
                "What's a Wall Breaker's favorite song? 'We Will Rock You.'",
                "Why was the Goblin always broke? He kept raiding the wrong storages.",
                "Why did the Witch get kicked from the clan? Too many *skeletons* in her closet.",
                "What do you call a Hog Rider who can't ride? Just a guy with a hammer.",
                "Why did the P.E.K.K.A bring a pencil to battle? To draw first blood.",
                "Why don’t Clashers play hide and seek? Because you can't hide from an Eagle Artillery.",
                "Why did the Town Hall blush? Because it saw the Archer Queen.",
                "How do Clashers stay cool in battle? They chill near an Ice Golem.",
                "Why was the Builder always calm? Because he knew how to constructively handle problems.",
                "What’s the Archer Queen’s favorite movie? 'Legolas: A True Story'.",
                "Why did the Lava Hound fail math? It always split during division.",
            ])
        elif text.startswith("!help"):
            return "Available commands: !hey, !status, !joke, !help"
        
        return None

    async def listen_for_commands(self, fb_gc_id=None):

        fb_gc_id = str(fb_gc_id) if fb_gc_id is not None else None
        
        self.driver.get(f"https://www.facebook.com/messages/t/{FB_GC_ID}")
        time.sleep(random.uniform(3, 6))

        logger.info(f"👂 Listening for commands in group: {fb_gc_id or 'ALL GROUPS'}...")
        last_seen_messages = set()

        while True:
            try:
                # Fetch messages ONLY from the specified FB_GC_ID
                messages = await asyncio.to_thread(self.get_latest_messages, fb_gc_id)
                
                if messages:
                    for msg in messages:
                        msg_text = msg["message"].strip()
                        msg_id = f"{msg['sender']}:{msg_text}"
                        
                        if msg_id not in last_seen_messages:
                            logger.info(f"📨 New message from {msg['sender']}: {msg_text}")
                            response = self.parse_command(msg_text)
                            if response:
                                await asyncio.to_thread(self.send_message, f"{msg['sender']}, {response}")
                            last_seen_messages.add(msg_id)
                            
                            if len(last_seen_messages) > 10:
                                last_seen_messages.pop()

                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"⚠️ Error in command listener: {str(e)}")
                await asyncio.sleep(10)

    def send_message(self, message):
        """Send message to configured group"""
        logger.info(f"🔄 Sending message to GC: {FB_GC_ID} MESSAGE: {message}")
        if not self.driver:
            logger.error("Driver not initialized")
            return False

        try:
            # Open Messenger
            self.driver.get(f"https://www.facebook.com/messages/t/{FB_GC_ID}")
            time.sleep(random.uniform(3, 6))

            # Type and send the message
            message_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='textbox' and @aria-label='Message']"))
            )
            self.human_type(message_box, message)
            time.sleep(random.uniform(1, 2))
            message_box.send_keys(Keys.RETURN)
            print(f"✅ Message sent to GC: {FB_GC_ID}")
            time.sleep(random.uniform(2, 5))

            return True

        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False

    def close(self):
        """Clean up the driver"""
        if self.driver:
            self.driver.quit()