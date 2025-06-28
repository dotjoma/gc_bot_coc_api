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
from config import FACEBOOK_EMAIL, FACEBOOK_PASSWORD, FB_GC_ID, HEADLESS_MODE
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
COOKIE_FILE = "fb_session_cookies.pkl"

class FacebookMessenger:
    def __init__(self):
        self.driver = None
        self.bot_name = None  # Will be set after login
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
    
    def handle_command(self, message: str, sender: str = None) -> str:
        """
        Handle incoming commands and return appropriate response
        
        Args:
            message: The message content
            sender: Name of the message sender (optional)
            
        Returns:
            Response message or None if no command was handled
        """
        try:
            if not message or not isinstance(message, str) or not message.startswith('!'):
                return None
                
            # Clean up the message
            message = message.strip()
            
            # Split into command and arguments
            command_parts = message[1:].split()
            if not command_parts:
                return None
                
            command = command_parts[0].lower()
            args = command_parts[1:]
            
            logger.info(f"Processing command: {command} with args: {args} from {sender}")
            
            if command == 'kudos':
                period = 'total'
                limit = 10
                
                # Parse period if provided
                if args and args[0].lower() in ['total', 'weekly']:
                    period = args[0].lower()
                    args = args[1:]
                
                # Parse limit if provided
                if args and args[0].isdigit():
                    limit = min(50, max(1, int(args[0])))  # Limit between 1-50
                
                return self.show_kudos(period, limit)
                
            elif command == 'help':
                return (
                    "=== BOT COMMANDS ===\n"
                    "!kudos [total|weekly] [limit] - Show kudos leaderboard\n"
                    "!help - Show this help message\n"
                    "=================="
                )
                
            return f"Unknown command: {command}. Type !help for available commands."
            
        except Exception as e:
            logger.error(f"Error handling command '{message}': {str(e)}")
            return None

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
        """Check if a message has already been processed"""
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM message_history 
                    WHERE message_id = ? 
                    LIMIT 1
                """, (message_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking message history: {e}")
            # If there's an error checking, assume message is processed to avoid duplicates
            return True


    def mark_message_as_processed(self, message_id, sender, message):
        """Mark a message as processed in the database"""
        processed_at = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect('fb_messages.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO message_history 
                    (message_id, sender, message, processed_at)
                    VALUES (?, ?, ?, ?)
                ''', (message_id, sender, message, processed_at))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark message as processed: {e}")
            # If we can't mark it as processed, we'll try again next time


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

    def get_bot_name(self):
        """Try to determine the bot's profile name from the UI"""
        try:
            # Wait for the page to be fully loaded
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='search']"))
            )
            
            # Try multiple ways to find the profile name
            name_sources = [
                # Method 1: Profile menu
                ("//span[contains(text(),'Your profile')]/ancestor::a", "profile menu"),
                # Method 2: Click profile picture to open menu
                ("//div[@role='banner']//div[@role='button'][@tabindex='0']//*[local-name()='image' or local-name()='img']", "profile picture"),
                # Method 3: Look for the user's name in the top bar
                ("//div[@role='banner']//span[contains(@class, 'x1lliihq') and contains(text(),' ')]", "top bar name")
            ]
            
            for xpath, source in name_sources:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    # If it's a clickable element, click it to open the menu
                    if 'button' in xpath or 'profile' in xpath.lower():
                        try:
                            element.click()
                            time.sleep(1)  # Wait for menu to open
                            # Now look for the name in the opened menu
                            name_element = WebDriverWait(self.driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, "//div[@role='menu']//span[contains(@class, 'x1lliihq')]"))
                            )
                            name = name_element.text.strip()
                        except:
                            name = element.get_attribute('aria-label') or element.text.strip()
                    else:
                        name = element.text.strip()
                    
                    if name and len(name) > 1:  # Ensure we got a valid name
                        self.bot_name = name.split('\n')[0].strip()  # Take first line if multiple
                        logger.info(f"Found bot name from {source}: {self.bot_name}")
                        return True
                        
                except Exception as e:
                    logger.debug(f"Could not get name from {source}: {str(e)}")
            
            logger.warning("Could not determine bot's name from any source")
            return False
            
        except Exception as e:
            logger.error(f"Failed to get bot name: {str(e)}")
            return False

    def login(self):
        """Robust login handler combining cookie and automated login."""
        try:
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            if HEADLESS_MODE:
                options.add_argument('--headless=new')
                options.add_argument('--window-size=1920,1080')
            else:
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
            if HEADLESS_MODE:
                options.add_argument('--headless=new')
                options.add_argument('--window-size=1920,1080')
            else:
                options.add_argument("--start-maximized")
            self.driver = uc.Chrome(options=options)

            if self.automated_login():
                self.get_bot_name()
                return True

        except Exception as e:
            logger.error(f"❌ Critical login failure: {str(e)}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            return False

    def get_latest_messages(self, fb_gc_id=None, limit=20):
        """
        Get new messages since the last check
        Args:
            fb_gc_id: Facebook Group Chat ID
            limit: Maximum number of messages to check (most recent first)
        Returns:
            List of unprocessed command messages from users (not from the bot itself)
        """
        messages = []
        try:
            fb_gc_id = str(fb_gc_id) if fb_gc_id is not None else None
            if not fb_gc_id:
                logger.error("No Facebook Group Chat ID provided")
                return []

            # Navigate to the chat if not already there
            try:
                if f"messages/t/{fb_gc_id}" not in self.driver.current_url:
                    self.driver.get(f"https://www.facebook.com/messages/t/{fb_gc_id}")
                    time.sleep(3)  # Wait for page load

                # Wait for chat container and scroll to load messages
                chat_container = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='main']"))
                )
                # Scroll to load more messages
                self.driver.execute_script("arguments[0].scrollTop = 0", chat_container)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Failed to load chat: {str(e)}")
                return []

            # Get all message elements
            try:
                message_elements = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH, 
                        "//div[@role='row' and .//div[@dir='auto']]"
                    ))
                )
                message_elements = message_elements[-limit:]  # Only check most recent messages
                logger.debug(f"Found {len(message_elements)} message elements to process")

                # Process messages from newest to oldest
                for element in reversed(message_elements):
                    if len(messages) >= 5:  # Limit to 5 new commands per check
                        break

                    try:
                        # Get message text
                        message_div = element.find_element(By.XPATH, ".//div[@dir='auto']")
                        message_text = message_div.text.strip()
                        
                        # Only process commands (messages starting with '!')
                        if not message_text or not message_text.startswith('!'):
                            continue

                        # Get sender name - try multiple approaches
                        sender = None
                        sender_elements = []
                        
                        # Try different XPath patterns to find the sender
                        xpath_patterns = [
                            ".//span[contains(@class, 'x1lliihq') or contains(@class, 'x1plvlek')]",
                            ".//a[contains(@href, 'profile.php') or contains(@href, '/messages/t/')]//span//span//span",
                            ".//a[contains(@href, 'profile.php') or contains(@href, '/messages/t/')]//span",
                            ".//a[contains(@href, 'profile.php') or contains(@href, '/messages/t/')]",
                            ".//span[contains(@class, 'x1s688f')]//span//span"
                        ]
                        
                        for xpath in xpath_patterns:
                            try:
                                sender_elements = element.find_elements(By.XPATH, xpath)
                                if sender_elements:
                                    sender = sender_elements[0].text.strip()
                                    if sender and len(sender) > 1:  # Ensure it's a valid name
                                        break
                            except:
                                continue
                        
                        if not sender:
                            logger.debug("Could not determine sender for message")
                            continue
                            
                        # Clean up sender name
                        sender = sender.split('\n')[0].strip()
                        
                        # Skip if we can't determine a valid sender
                        if not sender or len(sender) < 2:
                            logger.debug(f"Skipping message with invalid sender: {sender}")
                            continue
                            
                        # Skip messages from the bot itself
                        if self.bot_name and sender.lower() == self.bot_name.lower():
                            logger.debug(f"Skipping message from self (bot: {self.bot_name})")
                            continue
                            
                        # Skip system messages and notifications
                        skip_terms = [
                            'facebook', 'messenger', 'notification', 'message',
                            'you and', 'liked', 'reacted', 'shared', 'group',
                            'clash of clans', 'war', 'battle', 'attack',
                            'unknown', 'system', 'admin', 'joined', 'left',
                            'created', 'poll', 'event', 'call', 'video', 'photo'
                        ]
                        
                        if any(term in sender.lower() for term in skip_terms):
                            logger.debug(f"Skipping system message from: {sender}")
                            continue
                            
                        # Generate a message ID using content hash
                        message_id = hashlib.md5(
                            f"{fb_gc_id}_{sender}_{message_text}".encode()
                        ).hexdigest()
                        
                        # Check if we've already processed this message
                        if not self.is_message_processed(message_id):
                            self.mark_message_as_processed(message_id, sender, message_text)
                            messages.append({
                                'id': message_id,
                                'sender': sender,
                                'message': message_text
                            })
                            logger.info(f"New command from {sender}: {message_text}")
                            
                    except Exception as msg_error:
                        logger.debug(f"Error processing message element: {str(msg_error)}")
                        continue

            except Exception as e:
                logger.error(f"Error finding message elements: {str(e)}")
                return []

            return messages

        except Exception as e:
            logger.error(f"Failed to get latest messages: {str(e)}")
            return []

    def parse_command(self, text, sender=None):
        """
        Parse and respond to known commands
        
        Args:
            text: The message text to parse
            sender: Optional sender name for logging
            
        Returns:
            str: Response message or None if no command was handled
        """
        if not text or not text.startswith('!'):
            logger.debug(f"Not a command: {text}")
            return None
            
        logger.info(f"Processing command from {sender or 'unknown'}: {text}")
        
        try:
            # First try the new command handler
            response = self.handle_command(text, sender)
            if response is not None:
                logger.debug(f"Command handled by handle_command: {text}")
                return response
                
            # Fall back to legacy command handling
            text_lower = text.lower()
            
            if text_lower.startswith("!hey") or "hey bot" in text_lower:
                return "👋 Hello there! Type !help to see what I can do!"
                
            elif text_lower.startswith("!status"):
                return "🟢 I'm online and ready to help! Type !help for options."
                
            elif text_lower.startswith("!joke"):
                return random.choice([
                    # 👨‍💻 Programming Jokes
                    "Why don't programmers like nature? It has too many bugs.",
                    "Why do Java developers wear glasses? Because they don't C#.",
                    "How do you comfort a JavaScript bug? You console it.",
                    "I told my computer I needed a break, and now it won't stop sending me KitKat ads.",
                    "Programmer's diet: food() && sleep() && code();",

                    # 🏰 Clash of Clans Jokes
                    "Why did the Barbarian go to school? To improve his *clash*ifications.",
                    "Why did the Archer break up with the Giant? She needed space... 5 tiles, to be exact.",
                    "Why did the Clan Castle refuse to talk? It didn't want to *clash*.",
                    "What's a Wall Breaker's favorite song? 'We Will Rock You.'",
                    "Why was the Goblin always broke? He kept raiding the wrong storages.",
                    "Why did the Witch get kicked from the clan? Too many *skeletons* in her closet.",
                    "What do you call a Hog Rider who can't ride? Just a guy with a hammer.",
                    "Why did the P.E.K.K.A bring a pencil to battle? To draw first blood.",
                    "Why don't Clashers play hide and seek? Because you can't hide from an Eagle Artillery.",
                    "Why did the Town Hall blush? Because it saw the Archer Queen.",
                    "How do Clashers stay cool in battle? They chill near an Ice Golem.",
                    "Why was the Builder always calm? Because he knew how to constructively handle problems.",
                    "What's the Archer Queen's favorite movie? 'Legolas: A True Story'.",
                    "Why did the Lava Hound fail math? It always split during division.",
                ])
                
            elif text_lower.startswith("!info"):
                return """🤖 *Bot Information* 🤖

*Version*: 1.0.0  
*Last Updated*: 2025-04-17

*Features*:  
✅ Facebook Messenger automation  
✅ Command processing (!help for list)  
✅ Message tracking  
✅ Automated responses  
✅ War monitoring
✅ Kudos system

*Technical*:  
🐍 Python 3.10+  
🌐 Selenium WebDriver  
💾 SQLite database  
⏰ 24/7 operation  

*Maintained and Developed By*:  
👤 Joma  

Type `!help` for a list of commands"""

            elif text_lower.startswith("!kudos"):
                try:
                    # Extract CoC name after command
                    coc_name = text.split(maxsplit=1)[1].strip()
                    if self.give_kudos(coc_name):
                        return f"🎉 Kudos awarded to {coc_name}! 🎉"
                    return "❌ Failed to record kudos. Please try again later."
                except IndexError:
                    return "❌ Usage: !kudos [InGameName]"

            elif text_lower.startswith("!seekudos"):
                try:
                    # Default to total leaderboard
                    period = "total"
                    
                    # Check for weekly request
                    if "weekly" in text.lower():
                        period = "weekly"
                        
                    leaderboard = self.show_kudos(period=period, limit=15)  # Show top 15
                    if leaderboard:
                        return f"🏆 Top 15 Kudos ({period.capitalize()}) 🏆\n\n{leaderboard}"
                    return "No kudos data available yet."
                    
                except Exception as e:
                    logger.error(f"Kudos command error: {e}")
                    return "❌ Usage: !seekudos [weekly]"

            elif text_lower.startswith("!help"):
                return """🤖 *Available Commands* 🤖

*General Commands*:
`!help` - Show this help message
`!info` - Show bot information
`!status` - Check if bot is online
`!joke` - Get a random joke

*Kudos System*:
`!kudos @User` - Give kudos to a user
`!seekudos [weekly]` - Show kudos leaderboard

*War Commands*:
`!warstatus` - Check current war status
`!cwl` - Show CWL information

Type any command with `help` for more info (e.g., `!kudos help`)"""
            
            # If we get here, no command was matched
            logger.debug(f"No command matched for: {text}")
            return None
            
        except Exception as e:
            logger.error(f"Error in parse_command: {str(e)}")
            return f"❌ An error occurred while processing your command: {str(e)}"

    @staticmethod
    def generate_message_id(sender, message, timestamp):
        """Generate a unique ID for a message based on sender, content, and timestamp"""
        try:
            combined = f"{sender}|{message.strip().lower()}|{timestamp}"
            return hashlib.sha256(combined.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error(f"Error generating message ID: {str(e)}")
            # Fallback to a simple hash if there's an error
            return hashlib.md5(f"{time.time()}".encode()).hexdigest()

    async def listen_for_commands(self, fb_gc_id=None):
        """Main loop to listen for and process commands"""
        if not fb_gc_id:
            logger.error("No Facebook Group Chat ID provided")
            return

        fb_gc_id = str(fb_gc_id)
        logger.info(f"👂 Starting command listener for group: {fb_gc_id}")

        # Initialize last processed message ID
        last_processed_id = None
        error_count = 0
        last_cleanup = time.time()
        max_errors = 5

        try:
            # Navigate to the chat
            self.driver.get(f"https://www.facebook.com/messages/t/{fb_gc_id}")
            time.sleep(3)
            
            while True:
                try:
                    # Periodically clean up old messages (every hour)
                    current_time = time.time()
                    if current_time - last_cleanup > 3600:  # 1 hour
                        self.cleanup_old_messages(hours=24)  # Keep messages for 24 hours
                        last_cleanup = current_time

                    # Get new messages
                    messages = await asyncio.to_thread(self.get_latest_messages, fb_gc_id)
                    
                    if messages:
                        for msg in messages:
                            try:
                                # Skip if we've already processed this message
                                if last_processed_id and msg.get('id') == last_processed_id:
                                    continue

                                logger.info(f"Processing message from {msg.get('sender')}: {msg.get('message')}")

                                # Get message text and clean it up
                                message_text = msg.get('message', '').strip()
                                sender_name = msg.get('sender', 'Unknown')
                                
                                # Skip empty messages
                                if not message_text:
                                    continue
                                    
                                logger.info(f"Processing command from {sender_name}: {message_text}")
                                
                                # Handle the command and get response
                                response = None
                                
                                # First try the handle_command method (new style)
                                if hasattr(self, 'handle_command'):
                                    response = self.handle_command(message_text, sender_name)
                                
                                # If no response, try the parse_command method (legacy)
                                if response is None:
                                    response = self.parse_command(message_text, sender_name)
                                    
                                # If still no response and it's a command (starts with !), show help
                                if response is None and message_text.startswith('!'):
                                    response = "❌ Unknown command. Type `!help` for a list of available commands."

                                # If we got a response, send it back to the group
                                if response:
                                    logger.info(f"Sending response to {msg.get('sender')}")
                                    success = await asyncio.to_thread(
                                        self.send_message,
                                        response
                                    )

                                    if success:
                                        logger.info(f"✅ Responded to command from {msg.get('sender')}")
                                    else:
                                        logger.warning(f"Failed to send response to {msg.get('sender')}")

                                # Update last processed message ID
                                last_processed_id = msg.get('id')

                                # Small delay between processing messages
                                await asyncio.sleep(0.5)
                                
                            except Exception as e:
                                error_count += 1
                                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                                if error_count > max_errors:
                                    logger.error("⚠️ Too many errors, restarting command listener...")
                                    try:
                                        self.driver.refresh()
                                        time.sleep(5)
                                        error_count = 0
                                    except Exception as refresh_error:
                                        logger.error(f"Failed to refresh page: {str(refresh_error)}")
                                        await asyncio.sleep(30)  # Wait longer if refresh fails
                                await asyncio.sleep(5)  # Wait before retrying on error
                                continue
                    
                    # Reset error count on successful iteration
                    error_count = 0
                    
                    # Short sleep to prevent high CPU usage
                    await asyncio.sleep(2)
                    
                    # Refresh the page occasionally to prevent staleness
                    if random.random() < 0.1:  # ~10% chance on each iteration
                        try:
                            self.driver.refresh()
                            time.sleep(2)
                        except Exception as e:
                            logger.error(f"Error refreshing page: {str(e)}")
                            
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error in command loop: {str(e)}", exc_info=True)
                    if error_count > max_errors:
                        logger.error("Multiple errors occurred, waiting before retrying...")
                        await asyncio.sleep(10)
                    else:
                        await asyncio.sleep(2)
                        
        except KeyboardInterrupt:
            logger.info("Command listener stopped by user")
        except Exception as e:
            logger.error(f"Fatal error in command listener: {str(e)}", exc_info=True)
        finally:
            logger.info("Command listener stopped")



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