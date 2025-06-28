# config.py
import os
import pytz
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# COC Configuration
COC_API_TOKEN = os.getenv('COC_API_TOKEN')
CLAN_TAG = os.getenv('CLAN_TAG')

# Facebook Configuration
FACEBOOK_EMAIL = os.getenv('FACEBOOK_EMAIL')
FACEBOOK_PASSWORD = os.getenv('FACEBOOK_PASSWORD')
FB_GC_ID = int(os.getenv('FB_GC_ID')) # GC for production.
# FB_GC_ID = int(os.getenv('TEST_GC_ID')) # GC for testing.

# Timezone Configuration
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Asia/Manila'))

# Monitoring Interval (seconds)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '180'))  # Default: 3 minutes

# Browser Configuration
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'  # Run browser in headless mode