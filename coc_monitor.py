# coc_monitor.py
import asyncio
from aiohttp import ClientSession
from datetime import datetime
import pytz
import logging
from config import COC_API_TOKEN, CLAN_TAG, TIMEZONE

logger = logging.getLogger(__name__)

class CocMonitor:
    def __init__(self):
        self.current_state = None
        self.last_opponent = None

    async def fetch_data(self, session, endpoint):
        """Generic API request handler"""
        try:
            url = f"https://api.clashofclans.com/v1{endpoint}"
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                logger.error(f"API Error: {response.status}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            return None

    async def get_clan_war_state(self):
        """Get current war state with proper error handling"""
        async with ClientSession(headers={
            "Authorization": f"Bearer {COC_API_TOKEN}",
            "Accept": "application/json"
        }) as session:
            # Fetch current war info
            war_data = await self.fetch_data(
                session, 
                f"/clans/{CLAN_TAG.replace('#', '%23')}/currentwar"
            )
            
            if not war_data:
                return None

            return {
                "state": war_data.get("state", "notInWar"),
                "opponent": war_data.get("opponent", {}).get("name"),
                "team_size": war_data.get("teamSize"),
                "start_time": war_data.get("startTime"),
                "end_time": war_data.get("endTime"),
                "prep_start_time": war_data.get("preparationStartTime")
            }

    async def get_war_results(self, clan_tag):
        """Get detailed war results when state='warEnded'"""
        async with ClientSession(headers={
            "Authorization": f"Bearer {COC_API_TOKEN}",
            "Accept": "application/json"
        }) as session:
            war_data = await self.fetch_data(
                session,
                f"/clans/{clan_tag.replace('#', '%23')}/currentwar"
            )
            
            if not war_data or war_data.get('state') != 'warEnded':
                return None

            # Extract basic info
            clan = war_data.get('clan', {})
            opponent = war_data.get('opponent', {})
            
            # Calculate winner
            clan_stars = clan.get('stars', 0)
            opp_stars = opponent.get('stars', 0)
            clan_destruction = clan.get('destructionPercentage', 0)
            opp_destruction = opponent.get('destructionPercentage', 0)
            
            if clan_stars > opp_stars or (
                clan_stars == opp_stars and clan_destruction > opp_destruction
            ):
                result = "VICTORY"
            elif clan_stars == opp_stars and clan_destruction == opp_destruction:
                result = "DRAW"
            else:
                result = "DEFEAT"

            # Get top performers
            def get_top_attackers(members, count=3):
                return sorted(
                    [m for m in members if m.get('attacks')],
                    key=lambda x: sum(a.get('stars', 0) for a in x.get('attacks', [])),
                    reverse=True
                )[:count]

            clan_top = get_top_attackers(clan.get('members', []))
            opp_top = get_top_attackers(opponent.get('members', []))

            return {
                'result': result,
                'clan': {
                    'name': clan.get('name'),
                    'stars': clan_stars,
                    'destruction': clan_destruction,
                    'top_attackers': clan_top
                },
                'opponent': {
                    'name': opponent.get('name'),
                    'stars': opp_stars,
                    'destruction': opp_destruction,
                    'top_attackers': opp_top
                }
            }

    def parse_coc_time(self, coc_time_str):
        """Parse COC API timestamp string to datetime"""
        if not coc_time_str:
            return None
        return datetime.strptime(coc_time_str, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=pytz.UTC)

    def get_local_time_str(self, utc_time_str):
        """Convert UTC time string to local time string"""
        utc_time = self.parse_coc_time(utc_time_str)
        if not utc_time:
            return "N/A"
        local_time = utc_time.astimezone(TIMEZONE)
        return local_time.strftime('%Y-%m-%d %H:%M:%S')

    def get_remaining_time_str(self, utc_time_str):
        """Get remaining time as string"""
        utc_time = self.parse_coc_time(utc_time_str)
        if not utc_time:
            return "N/A"
        now = datetime.now(TIMEZONE)
        end_time = utc_time.astimezone(TIMEZONE)
        remaining = end_time - now
        return str(remaining).split('.')[0]  # Remove microseconds