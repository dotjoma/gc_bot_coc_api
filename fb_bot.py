import pickle
import os
import hashlib
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
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
COOKIE_FILE = "fb_session_cookies.pkl"

class FacebookMessenger:
    def __init__(self):
        self.driver = None
        self.init_database()

    def human_type(self, element, text, speed=0.1):
        """Type like a human with random delays"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(speed / 2, speed * 1.5))

    def human_click(self, element):
        """Simulate a human-like click on a web element"""
        ActionChains(self.driver).move_to_element(element).pause(random.uniform(0.1, 0.3)).click().perform()

    def init_database(self):
        """Initialize SQLite database for message history"""
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS message_history (
                        message_id TEXT PRIMARY KEY,
                        sender TEXT,
                        message TEXT,
                        processed_at TEXT
                    )
                ''')

                # Kudos tracking table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS kudos (
                        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        coc_name TEXT NOT NULL UNIQUE,
                        total_kudos INTEGER DEFAULT 0,
                        weekly_kudos INTEGER DEFAULT 0,
                        last_kudos_date TEXT  
                    )
                ''')

                conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def give_kudos(self, coc_name: str):
        """Award kudos to a player by their CoC name"""
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                
                # Insert or update player record
                cursor.execute('''
                    INSERT INTO kudos (coc_name, total_kudos, weekly_kudos, last_kudos_date)
                    VALUES (?, 1, 1, DATE('now'))
                    ON CONFLICT(coc_name) DO UPDATE SET
                        total_kudos = total_kudos + 1,
                        weekly_kudos = weekly_kudos + 1,
                        last_kudos_date = DATE('now')
                ''', (coc_name,))
                
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to give kudos: {e}")
            return False
    
    def show_kudos(self, period: str = "total", limit: int = 10) -> str:
        """
        Generate formatted kudos leaderboard
        Args:
            period: 'total' or 'weekly'
            limit: Number of entries to show
        Returns:
            Formatted leaderboard string
        """
        try:
            results = self.get_kudos_leaderboard(period, limit)
            
            if not results:
                return "No kudos records found"
                
            # Create header
            period_title = "Lifetime" if period == "total" else "Weekly"
            leaderboard = [
                f"----- {period_title} Kudos Leaderboard -----",
                "Rank    Player            Kudos",
                "--------------------------------"
            ]
            
            # Add entries with aligned columns
            for rank, (coc_name, score) in enumerate(results, 1):
                leaderboard.append(f"{rank:<8}{coc_name:<18}{score}")
                
            # Add footer
            leaderboard.append("--------------------------------")
            leaderboard.append("Type '!seekudos weekly' for weekly rankings")
            
            return "\n".join(leaderboard)
            
        except Exception as e:
            logger.error(f"Failed to generate kudos display: {e}")
            return "Error retrieving leaderboard"

    def get_kudos_leaderboard(self, period: str = "total", limit: int = 10) -> list:
        """Retrieve raw kudos data from database"""
        try:
            column = "total_kudos" if period == "total" else "weekly_kudos"
            
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                
                cursor.execute(f'''
                    SELECT coc_name, {column} as score
                    FROM kudos
                    ORDER BY score DESC
                    LIMIT ?
                ''', (limit,))
                
                return cursor.fetchall()
                
        except Exception as e:
            logger.error(f"Database error in get_kudos_leaderboard: {e}")
            return []

    def is_message_processed(self, message_id):
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM message_history WHERE message_id = ?", (message_id,))
                result = cursor.fetchone()
                if result:
                    logger.info(f"Message already processed: {message_id}")
                    return True
                else:
                    logger.info(f"Message not processed yet: {message_id}")
                    return False
        except Exception as e:
            logger.error(f"Error checking message history: {e}")
            return False


    def mark_message_as_processed(self, message_id, sender, message):
        processed_at = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO message_history (message_id, sender, message, processed_at)
                    VALUES (?, ?, ?, ?)
                ''', (message_id, sender, message, processed_at))
                conn.commit()
                logger.info(f"Marked message as processed: {message_id}")
        except Exception as e:
            logger.error(f"Failed to mark message as processed: {e}")


    def save_processed_message(self, message_id, sender, message):
        """Save processed message to database"""
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT OR REPLACE INTO message_history (message_id, sender, message, processed_at)
                    VALUES (?, ?, ?, ?)
                ''', (message_id, sender, message, current_time))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save message to database: {e}")
            return False

    def cleanup_old_messages(self, minutes=1440):
        """Clean up messages older than specified minutes"""
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                cutoff_time = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('DELETE FROM message_history WHERE processed_at < ?', (cutoff_time,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup old messages: {e}")

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
            
            try:
                self.driver = uc.Chrome(options=options)
            except Exception as e:
                if "This version of ChromeDriver only supports Chrome version" in str(e):
                    import re
                    # Extract the required and current Chrome versions from the error message
                    match = re.search(r'only supports Chrome version (\d+).*Current browser version is (\d+)', str(e))
                    if match:
                        required_ver = match.group(1)
                        current_ver = match.group(2)
                        error_msg = (
                            f"❌ Chrome version mismatch detected!\n"
                            f"  • Your Chrome version: {current_ver}\n"
                            f"  • Required Chrome version: {required_ver}\n\n"
                            "Please update your Chrome browser to the latest version:\n"
                            "1. Open Chrome\n"
                            "2. Click the three dots (⋮) in the top-right corner\n"
                            "3. Go to Help > About Google Chrome\n"
                            "4. Let it update if an update is available\n\n"
                            "If the issue persists, you can manually download the matching ChromeDriver from:\n"
                            "https://chromedriver.chromium.org/downloads"
                        )
                        logger.error(error_msg)
                        raise Exception(error_msg) from e
                # Re-raise the original exception if it's not a version mismatch
                raise

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
                time.sleep(3)

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

            messages = []
            try:
                message_elements = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH, 
                        "//div[@role='row' and contains(@class, 'x1n2onr6')]"
                    ))
                )

                logger.info(f"Found {len(message_elements)} message elements")

                for element in message_elements[-limit:]:
                    try:
                        # Get message text first
                        try:
                            message_text = element.find_element(
                                By.XPATH,
                                ".//div[@dir='auto']"
                            ).text.strip()
                            logger.info(f"Found message text: {message_text}")
                        except:
                            continue

                        # Only respond to specific commands
                        valid_commands = [
                            "!hey", "!status", "!joke", "!help", 
                            "!info", "!kudos", "!seekudos"
                        ]
                        
                        # Skip if message does not start with a valid command
                        if not any(message_text.lower().startswith(command) for command in valid_commands):
                            logger.info(f"Skipping non-command message: {message_text}")
                            continue

                        # Get sender name
                        sender = None
                        sender_selectors = [
                            (".//h4[contains(@class, 'x1heor9g')]", "h4"),
                            (".//span[contains(@class, 'x1lliihq')]", "span"),
                            (".//a[@role='link']", "link")
                        ]

                        for selector, selector_type in sender_selectors:
                            try:
                                sender_element = element.find_element(By.XPATH, selector)
                                potential_sender = sender_element.text.strip().rstrip(':')

                                if (potential_sender and 
                                    len(potential_sender) >= 2 and 
                                    not potential_sender.startswith('!') and
                                    not any(skip in potential_sender.lower() for skip in [
                                        'facebook', 'messenger', 'notification', 'message', 
                                        'sent', 'you and', 'liked', 'reacted', 'shared', 
                                        'group', 'bot'
                                    ])):
                                    sender = potential_sender
                                    logger.info(f"Found sender '{sender}' using {selector_type}")
                                    break
                            except:
                                continue

                        if not sender:
                            continue

                        # Create unique message ID
                        current_time = datetime.now().strftime('%Y%m%d%H%M%S')
                        message_id = f"{fb_gc_id}_{sender}_{message_text}_{current_time}"

                        # Check if message was already processed
                        if not self.is_message_processed(message_id):
                            self.mark_message_as_processed(message_id, sender, message_text)
                            messages.append({
                                "message_id": message_id,
                                "sender": sender,
                                "message": message_text
                            })
                            logger.info(f"Added new command from {sender}: {message_text}")

                    except Exception as msg_error:
                        logger.info(f"Error processing message: {str(msg_error)}")
                        continue

                logger.info(f"Returning {len(messages)} messages to process")
                return messages

            except Exception as e:
                logger.exception(f"Error: {str(e)}")
                return []

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
        elif text.startswith("!info"):
            return """Bot Information:
                Version: 1.0.0  
                Last Updated: 2025-04-17

                Features:  
                - Facebook Messenger automation  
                - Command processing (!help for list)  
                - Message tracking  
                - Automated responses  

                Technical:  
                - Python 3.10+  
                - Selenium WebDriver  
                - SQLite database  
                - 24/7 operation  

                Maintained and Developed By:  
                Joma  

                Type !help for commands"""

        elif text.startswith("!kudos"):
            try:
                # Extract CoC name after command
                coc_name = text.split(maxsplit=1)[1].strip()
                if self.give_kudos(coc_name):
                    return f"Kudos awarded to {coc_name}!"
                return "Failed to record kudos"
            except IndexError:
                return "Usage: !kudos [InGameName]"

        elif text.startswith("!seekudos"):
            try:
                # Default to total leaderboard
                period = "total"
                
                # Check for weekly request
                if "weekly" in text.lower():
                    period = "weekly"
                    
                return self.show_kudos(period=period, limit=15)  # Show top 15
                
            except Exception as e:
                logger.error(f"Kudos command error: {e}")
                return "Usage: !seekudos [weekly]"

        elif text.startswith("!help"):
            return "Available commands: !hey, !status, !joke, !info, !kudos, !seekudos, !help"
        
        return None

    def generate_message_id(sender, message, timestamp):
        combined = f"{sender}|{message.strip().lower()}|{timestamp}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    async def listen_for_commands(self, fb_gc_id=None):
        fb_gc_id = str(fb_gc_id) if fb_gc_id is not None else None

        self.driver.get(f"https://www.facebook.com/messages/t/{FB_GC_ID}")
        time.sleep(random.uniform(3, 6))

        logger.info(f"👂 Listening for commands in group: {fb_gc_id or 'ALL GROUPS'}...")

        count = 0
        while True:
            try:
                # Cleanup old messages periodically
                self.cleanup_old_messages(minutes=1440)

                # Fetch messages ONLY from the specified FB_GC_ID
                messages = await asyncio.to_thread(self.get_latest_messages, fb_gc_id)
                
                if messages:
                    for msg in messages:
                        # 🛑 Skip if message already processed
                        if self.is_message_processed(msg["message_id"]):
                            continue

                        response = self.parse_command(msg["message"])
                        if response:
                            success = await asyncio.to_thread(
                                self.send_message,
                                f"{msg['sender']}, {response}"
                            )

                            if success:
                                self.save_processed_message(
                                    msg["message_id"],
                                    msg["sender"],
                                    msg["message"]
                                )
                                logger.info(f"✅ Processed command from {msg['sender']}")

                await asyncio.sleep(10)
                self.driver.get(f"https://www.facebook.com/messages/t/{FB_GC_ID}")
                time.sleep(3)

            except Exception as e:
                logger.error(f"⚠️ Error in command listener: {str(e)}")
                await asyncio.sleep(10)
            # print(count)
            # count = count + 1
            # if count >= 10:
            #     self.send_message("[RELOGIN_DEBUG] Login again if cookie expired.")
            #     count = 0

            # await asyncio.sleep(1)


    def escape_xpath_text(self, text):
        """Safely escape text for use inside an XPath expression."""
        if "'" in text and '"' in text:
            parts = text.split("'")
            return "concat('" + "', \"'\", '".join(parts) + "')"
        elif "'" in text:
            return f'"{text}"'
        else:
            return f"'{text}'"

    def send_message(self, message):
        """Send message to configured Facebook group chat"""
        logger.info(f"🔄 Attempting to send message to GC: {FB_GC_ID}")

        if not self.driver:
            logger.error("❌ WebDriver not initialized")
            return False

        # Verify if the bot is logged in before proceeding
        if not self.verify_login():
            logger.error("❌ Not logged in to Facebook. Attempting to log in...")

            # Attempt login if not logged in
            if not self.login():
                logger.error("❌ Failed to log in.")
                return False

            # Once logged in, save the session cookies
            if not self.save_cookies():
                logger.warning("⚠️ Failed to save session cookies.")

        try:
            self.driver.get(f"https://www.facebook.com/messages/t/{FB_GC_ID}")

            # Wait for the page to load fully
            WebDriverWait(self.driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(random.uniform(2, 4))  # Small buffer

            # Scroll to bottom to make sure everything is visible
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait for the message box to be clickable
            message_box = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//div[@role='textbox']"))
            )

            # Use JavaScript to focus the element (helps if it’s not interactable normally)
            self.driver.execute_script("arguments[0].focus();", message_box)

            # Type the message using your human_type method
            self.human_type(message_box, message)

            time.sleep(random.uniform(0.5, 1.5))  # Wait before sending

            # Press Enter to send the message
            message_box.send_keys(Keys.RETURN)

            # Verify if any line of the message is visible in chat (optional, can be flaky)
            try:
                lines = message.splitlines()
                for line in lines:
                    if not line.strip():
                        continue  # Skip empty lines
                    try:
                        safe_text = self.escape_xpath_text(line.strip())
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), {safe_text})]"))
                        )
                        logger.info(f"✅ Verified message line in chat: {line.strip()}")
                        return True
                    except Exception:
                        continue

                logger.warning("⚠️ Could not verify any line from the message. It was likely still sent.")
                return True

            except Exception as verify_error:
                logger.warning(f"⚠️ Error during message verification: {verify_error}")
                return True


        except Exception as e:
            logger.error(f"❌ Failed to send message: {str(e)}")
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.driver.save_screenshot(f"send_message_error_{timestamp}.png")
                logger.info("📸 Saved screenshot of error state")
            except Exception as screenshot_err:
                logger.error(f"Failed to take screenshot: {screenshot_err}")
            return False

    def close(self):
        """Clean up the driver"""
        if self.driver:
            self.driver.quit()