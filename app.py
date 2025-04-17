import coc
import asyncio
from aiohttp import ClientSession
from datetime import datetime
import pytz
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CocApiClient:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://api.clashofclans.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json"
        }
        self.rate_limit_remaining = 30  # Default rate limit
        self.session = None

    async def __aenter__(self):
        self.session = ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()

    async def fetch_data(self, endpoint):
        """Generic API request handler with rate limiting"""
        try:
            # Check rate limits
            if self.rate_limit_remaining <= 5:
                logger.warning("Approaching rate limit, waiting...")
                await asyncio.sleep(10)

            async with self.session.get(f"{self.base_url}{endpoint}") as response:
                # Update rate limit tracking
                self.rate_limit_remaining = int(
                    response.headers.get("X-Ratelimit-Remaining", 30)
                )

                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(
                        f"API Error: {response.status} - {await response.text()}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            return None

async def get_clan_data(api_token, clan_tag):
    """Get comprehensive clan data with proper error handling"""
    async with CocApiClient(api_token) as client:
        # Fetch clan info
        clan_data = await client.fetch_data(f"/clans/{clan_tag.replace('#', '%23')}")
        if not clan_data:
            return None

        # Fetch current war info
        war_data = await client.fetch_data(f"/clans/{clan_tag.replace('#', '%23')}/currentwar")
        
        return {
            "info": {
                "name": clan_data.get("name"),
                "tag": clan_data.get("tag"),
                "level": clan_data.get("clanLevel"),
                "members": clan_data.get("members"),
                "war_league": clan_data.get("warLeague", {}).get("name")
            },
            "war": {
                "state": war_data.get("state") if war_data else "notInWar",
                "opponent": war_data.get("opponent", {}).get("name") if war_data else None,
                "team_size": war_data.get("teamSize") if war_data else None,
                "start_time": war_data.get("startTime") if war_data else None,
                "end_time": war_data.get("endTime") if war_data else None,
                "prep_start_time": war_data.get("preparationStartTime") if war_data else None
            } if war_data else None
        }

def parse_coc_time(coc_time_str):
    return datetime.strptime(coc_time_str, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=pytz.UTC)

def get_local_time(utc_time_str, tz_name="Asia/Manila"):
    local_tz = pytz.timezone(tz_name)
    utc_time = parse_coc_time(utc_time_str)
    local_time = utc_time.astimezone(local_tz)
    return local_time

def get_remaining_time_local(utc_time_str, tz_name="Asia/Manila"):
    local_tz = pytz.timezone(tz_name)
    now = datetime.now(local_tz)
    end_time = parse_coc_time(utc_time_str).astimezone(local_tz)
    return end_time - now

async def main():
    API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjYwZWU5ZWI2LWVhMTktNDY5Zi04Y2JkLTVkNzc2NWJkODA1ZCIsImlhdCI6MTc0NDQyODQ3Niwic3ViIjoiZGV2ZWxvcGVyL2E2MjgyYjgwLWNjYWQtMjgyZC0zYWY0LTU3ODcxOTM3NjVlMiIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjEzNi4xNTguNy4xMTAiLCIwLjAuMC4wIl0sInR5cGUiOiJjbGllbnQifV19.gsOQYyiRDvUFSetN238_qmOBxHYXlIdg4z9ZUOTIssZPO85tNwmMkEo_DP4rxeaOIAs-6Lcge7toyJgq3wTMPA"
    CLAN_TAG = "#P0R22UY2"
    last_state = None

    while True:
        data = await get_clan_data(API_TOKEN, CLAN_TAG)
        if data:
            print(f"\n[{datetime.now()}]\n=== Clan Information ===")
            print(f"Name: {data['info']['name']}")
            print(f"Tag: {data['info']['tag']}")
            print(f"Level: {data['info']['level']}")
            print(f"Members: {data['info']['members']}/50")
            print(f"War League: {data['info']['war_league']}")

            if data['war']:
                new_state = data['war']['state']
                if new_state != last_state:
                    print(f"\n[{datetime.now()}] ⚔️ War state changed: {last_state} → {new_state}")
                    last_state = new_state
                else:
                    print(f"[{datetime.now()}] War state unchanged: {new_state}")

                if data['war']['opponent']:
                    print(f"Opponent: {data['war']['opponent']}")
                    print(f"Size: {data['war']['team_size']}v{data['war']['team_size']}")

                if new_state == "preparation":
                    war_start_local = get_local_time(data['war']['start_time'])
                    remaining = get_remaining_time_local(data['war']['start_time'])
                    print(f"🛡️ War starts at (local): {war_start_local.strftime('%Y-%m-%d %H:%M:%S')}")
                if new_state == "inWar":
                    war_end_local = get_local_time(data['war']['end_time'])
                    remaining = get_remaining_time_local(data['war']['end_time'])
                    print(f"🔥 War ends at (local): {war_end_local.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"\n[{datetime.now()}] No current war data available")

        else:
            print(f"[{datetime.now()}] Failed to fetch data.")

        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())