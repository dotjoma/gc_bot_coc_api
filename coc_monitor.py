# coc_monitor.py
import asyncio
from aiohttp import ClientSession, TCPConnector
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
                elif response.status == 503:
                    logger.warning("⚠️ Clash of Clans API is under maintenance.")
                    return {"maintenance": True}
                else:
                    error_body = await response.text()
                    logger.error(f"API Error {response.status}: {error_body}")
                    return None

                logger.error(f"API Error: {response.status}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            return None

    async def get_raid_weekend_data(self):
        """Get the current capital raid season (raid weekend) data"""
        endpoint = f"/clans/{CLAN_TAG}/capitalraidseasons"
        
        async with ClientSession(headers={
            "Authorization": f"Bearer {COC_API_TOKEN}",
            "Accept": "application/json"
        }) as session:
            raid_data = await self.fetch_data(session, endpoint)
            
            if raid_data:
                state = raid_data.get('state', 'unknown')
                start_time = coc_monitor.get_local_time_str(raid_data.get('startTime'))
                end_time = coc_monitor.get_local_time_str(raid_data.get('endTime'))
                return {
                    "state": state,
                    "start_time": start_time,
                    "end_time": end_time
                }
            return None

    async def get_clan_war_state(self):
        """Get current war state with proper error handling"""
        async with ClientSession(
            connector=TCPConnector(limit=10),  # allow up to 10 connections
            headers={
                "Authorization": f"Bearer {COC_API_TOKEN}",
                "Accept": "application/json"
            }
        ) as session:
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

    async def get_clan_info(self):
        """Get general clan info including total war stats"""
        async with ClientSession(
            connector=TCPConnector(limit=10),
            headers={
                "Authorization": f"Bearer {COC_API_TOKEN}",
                "Accept": "application/json"
            }
        ) as session:
            data = await self.fetch_data(
                session,
                f"/clans/{CLAN_TAG.replace('#', '%23')}"
            )

            if not data:
                return None

            return {
                "name": data.get("name"),
                "war_wins": data.get("warWins"),
                "war_losses": data.get("warLosses"),
                "war_ties": data.get("warTies"),
                "war_league": data.get("warLeague", {}).get("name")
            }

    async def get_recent_attacks(self, count=1):
        """Get most recent attack(s) from your clan in current war"""
        async with ClientSession(
            connector=TCPConnector(limit=10),  # allow up to 10 connections
            headers={
                "Authorization": f"Bearer {COC_API_TOKEN}",
                "Accept": "application/json"
            }
        ) as session:
            war_data = await self.fetch_data(
                session,
                f"/clans/{CLAN_TAG.replace('#', '%23')}/currentwar"
            )

            if not war_data or war_data.get('state') not in ['inWar', 'warEnded']:
                # logger.warning("No active or ended war data available.")
                return []

            clan_members = war_data.get('clan', {}).get('members', [])
            enemy_members = war_data.get('opponent', {}).get('members', [])

            # Create a mapping of enemy tag to name
            defender_name_map = {member['tag']: member['name'] for member in enemy_members}

            all_attacks = []
            for member in clan_members:
                name = member.get('name')
                tag = member.get('tag')
                attacks = member.get('attacks', [])

                for attack in attacks:
                    defender_tag = attack.get('defenderTag')
                    attack_time = attack.get('order') or 0
                    all_attacks.append({
                        'attacker': name,
                        'attacker_tag': tag,
                        'stars': attack.get('stars'),
                        'destruction': attack.get('destructionPercentage'),
                        'defender_tag': defender_tag,
                        'defender_name': defender_name_map.get(defender_tag, defender_tag),
                        'order': attack_time
                    })

            # Sort by order (higher = more recent)
            sorted_attacks = sorted(all_attacks, key=lambda x: x['order'], reverse=True)

            return sorted_attacks[:count]

    async def get_war_results(self, clan_tag):
        """Get detailed war results when state='warEnded'"""
        async with ClientSession(
            connector=TCPConnector(limit=10),  # allow up to 10 connections
            headers={
                "Authorization": f"Bearer {COC_API_TOKEN}",
                "Accept": "application/json"
            }
        ) as session:
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