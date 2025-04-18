import asyncio
import logging
import sqlite3
import random
from datetime import datetime
from coc_monitor import CocMonitor
from fb_bot import FacebookMessenger
from config import CHECK_INTERVAL, CLAN_TAG, FB_GC_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Initializing database...")
    conn = sqlite3.connect('war_status.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS war_state (
            id INTEGER PRIMARY KEY,
            state TEXT
        )
    ''')

    # Ensure there is one row
    c.execute('SELECT COUNT(*) FROM war_state')
    count = c.fetchone()[0]
    logger.info(f"Rows in war_state table: {count}")
    if count == 0:
        logger.info("Inserting default empty state...")
        c.execute('INSERT INTO war_state (state) VALUES (?)', ('',))
    conn.commit()
    conn.close()
    logger.info("Database initialized.\n")

def init_attack_log_db():
    logger.info("Initializing war_attacks.db for logging attacks...")
    conn = sqlite3.connect('war_attacks.db')
    c = conn.cursor()

    # Create table for logging processed attacks
    c.execute('''
        CREATE TABLE IF NOT EXISTS logged_attacks (
            attacker_tag TEXT,
            attacker_name TEXT,
            defender_name TEXT,
            destruction_percentage TEXT,
            attack_order INTEGER,
            PRIMARY KEY (attacker_tag, defender_name, attack_order)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("war_attacks.db initialized.\n")

def is_attack_logged(attacker_tag, defender_name, attack_order):
    conn = sqlite3.connect('war_attacks.db')
    c = conn.cursor()
    c.execute('''
        SELECT 1 FROM logged_attacks
        WHERE attacker_tag = ? AND defender_name = ? AND attack_order = ?
    ''', (attacker_tag, defender_name, attack_order))
    result = c.fetchone()
    conn.close()
    return result is not None

def log_attack(attacker_tag, attacker_name, defender_name, destruction, attack_order):
    conn = sqlite3.connect('war_attacks.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO logged_attacks (attacker_tag,attacker_name,defender_name,destruction_percentage,attack_order)
        VALUES (?,?,?,?,?)
    ''', (attacker_tag,attacker_name,defender_name,destruction,attack_order))
    conn.commit()
    conn.close()

def get_last_state():
    logger.info("Fetching last known war state from DB...")
    conn = sqlite3.connect('war_status.db')
    c = conn.cursor()
    c.execute('SELECT state FROM war_state WHERE id = 1')
    result = c.fetchone()
    conn.close()
    last_state = result[0] if result else ''
    logger.info(f"Last state retrieved: '{last_state}'\n")
    return last_state

def update_state(new_state):
    logger.info(f"Updating war state to: '{new_state}'")
    conn = sqlite3.connect('war_status.db')
    c = conn.cursor()
    c.execute('UPDATE war_state SET state = ? WHERE id = 1', (new_state,))
    conn.commit()
    conn.close()
    logger.info("War state updated.\n")

async def recent_attack(coc_monitor, fb_bot):
    """Fetch and send recent attacks from clan war, avoiding duplicates."""

    zero_destruction_msgs = [
        "Connection issues? That attack didn’t go through.",
        "Oof! 0%—something must’ve gone wrong.",
        "Maybe a disconnect? Better luck next round!",
        "That looked like an unfinished attack!"
    ]

    low_destruction_msgs = [
        "Keep pushing!",
        "Not bad, next one will be better!",
        "We all have those days—GG!",
        "Nice effort, learn and improve!"
    ]

    good_destruction_msgs = [
        "Nice hit!",
        "Great work out there!",
        "That was solid!",
        "You're bringing the heat!"
    ]

    almost_perfect_msgs = [
        "So close to perfection!",
        "That was a beast of an attack!",
        "Massive damage, almost 3-star worthy!",
        "Just a bit more and that base was dust!"
    ]

    perfect_msgs = [
        "🔥 Flawless victory!",
        "100%! Absolute perfection!",
        "That base didn’t stand a chance!",
        "A triple! You’re unstoppable!"
    ]

    while True:
        recent_attacks = await coc_monitor.get_recent_attacks(count=3)
        for attack in recent_attacks:
            attacker_tag = attack['attacker_tag']
            attacker_name = attack['attacker']
            defender_name = attack['defender_name']
            attack_order = attack['order']

            if is_attack_logged(attacker_tag, defender_name, attack_order):
                continue

            destruction = attack['destruction'] or 0

            if destruction == 0:
                remark = random.choice(zero_destruction_msgs)
            elif destruction < 70:
                remark = random.choice(low_destruction_msgs)
            elif 70 <= destruction < 95:
                remark = random.choice(good_destruction_msgs)
            elif 95 <= destruction < 100:
                remark = random.choice(almost_perfect_msgs)
            else:
                remark = random.choice(perfect_msgs)

            message = (
                f"{attack['attacker']} got {attack['stars']}stars on {defender_name} "
                f"with {destruction}% destruction. {remark}"
            )

            print(message)
            await asyncio.to_thread(fb_bot.send_message, message)
            log_attack(attacker_tag, attacker_name, defender_name, destruction, attack_order)

        await asyncio.sleep(10)

async def main():
    coc_monitor = CocMonitor()
    fb_bot = FacebookMessenger()
    
    # Initialize Facebook bot
    if not fb_bot.login():
        logger.error("Failed to initialize Facebook bot")
        return

    logger.info("✅ Bot is now listening for commands. Type `!help` to see options.")

    # Create tasks for both operations
    init_db()
    init_attack_log_db()

    try:
        # Run both tasks concurrently
        await asyncio.gather(
            coc_monitor_loop(coc_monitor, fb_bot),
            # fb_bot.listen_for_commands(FB_GC_ID),
            recent_attack(coc_monitor, fb_bot)
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        fb_bot.close()

async def coc_monitor_loop(coc_monitor, fb_bot):
    """Handle the CoC war monitoring in a separate async loop"""
    while True:
        try:
            war_data = await coc_monitor.get_clan_war_state()
            
            if war_data:
                new_state = war_data['state']
                last_state = get_last_state()
                
                if new_state != last_state:
                    logger.info(f"War state changed: {last_state} → {new_state}")
                    update_state(new_state)
                    coc_monitor.current_state = new_state

                    opponent = war_data['opponent']
                    
                    # Prepare appropriate message
                    if new_state == "preparation":
                        start_time = coc_monitor.get_local_time_str(war_data['start_time'])
                        war_size = f"{war_data['team_size']}v{war_data['team_size']}"
                        
                        message = (
                            f"=== WAR PREPARATION ===\n"
                            f"Opponent: {opponent}\n"
                            f"War Size: {war_size}\n"
                            f"Battle Starts: {start_time}\n\n"
                            f"Please set your war bases and plan your attacks!\n"
                            f"War starts in {coc_monitor.get_remaining_time_str(war_data['start_time'])}"
                        )
                    elif new_state == "inWar":
                            # Get formatted end time
                            end_time = coc_monitor.get_local_time_str(war_data['end_time'])
                            
                            # Calculate remaining time
                            remaining_time = coc_monitor.get_remaining_time_str(war_data['end_time'])
                            remaining_str = str(remaining_time).split('.')[0]  # Remove microseconds
                            
                            # Get war size (e.g., "15v15", "30v30")
                            war_size = f"{war_data['team_size']}v{war_data['team_size']}"
                            
                            message = (
                                f"=== WAR NOTIFICATION ===\n"
                                f"Opponent: {opponent}\n"
                                f"War Size: {war_size}\n"
                                f"End Time: {end_time}\n"
                                f"Time Remaining: {remaining_str}\n\n"
                                f"All clan members please complete your attacks!\n"
                                f"Good luck everyone!"
                            )
                    elif new_state == "warEnded":
                        try:
                            war_results = await coc_monitor.get_war_results(CLAN_TAG)
                            
                            if not war_results:
                                message = "War has ended! Could not fetch detailed results."
                            else:
                                # Basic war info with validation
                                opponent_name = war_results['opponent'].get('name', 'Unknown Opponent')
                                result = war_results.get('result', 'UNKNOWN RESULT')
                                
                                # Stats with fallback values
                                clan_stars = war_results['clan'].get('stars', 0)
                                opp_stars = war_results['opponent'].get('stars', 0)
                                clan_destruction = war_results['clan'].get('destruction', 0)
                                opp_destruction = war_results['opponent'].get('destruction', 0)
                                
                                message = (
                                    f"=== WAR AGAINST {opponent_name} HAS ENDED ===\n"
                                    f"RESULT: {result}\n"
                                    f"Stars: {clan_stars} vs {opp_stars}\n"
                                    f"Destruction: {clan_destruction}% vs {opp_destruction}%\n"
                                )
                                
                                # Add top performers only if available
                                if war_results['clan'].get('top_attackers'):
                                    message += "\n[OUR TOP PLAYERS]\n"
                                    for i, attacker in enumerate(war_results['clan']['top_attackers'], 1):
                                        attacks = attacker.get('attacks', [])
                                        name = attacker.get('name', 'Unknown Player')
                                        
                                        if attacks:
                                            total_stars = sum(a.get('stars', 0) for a in attacks)
                                            th_level = attacks[0].get('townhallLevel', '?')
                                            message += f"{i}. {name}: {total_stars} stars (TH{th_level})\n"
                                        else:
                                            message += f"{i}. {name}: No attacks\n"
                                
                                # Add notable enemies if available
                                if war_results['opponent'].get('top_attackers'):
                                    message += "\n[TOP ENEMY PLAYERS]\n"
                                    for i, attacker in enumerate(war_results['opponent']['top_attackers'][:3], 1):
                                        attacks = attacker.get('attacks', [])
                                        name = attacker.get('name', 'Unknown Enemy')
                                        
                                        if attacks:
                                            total_stars = sum(a.get('stars', 0) for a in attacks)
                                            th_level = attacks[0].get('townhallLevel', '?')
                                            message += f"{i}. {name}: {total_stars} stars (TH{th_level})\n"
                                
                                message += "\nCheck the game for full details!"

                        except Exception as e:
                            logger.error(f"Error processing war results: {str(e)}")
                            message = "War has ended! Error generating detailed report."

                    elif new_state == "notInWar":
                        message = (
                            f"=== NO ACTIVE WAR ===\n"
                            f"There is currently no ongoing or upcoming war.\n"
                            f"Stay ready for the next battle!"
                        )

                    else:
                        message = f"War state changed to {new_state}"
                    
                    # Send message via Facebook
                    # fb_bot.send_message(message)
                    await asyncio.to_thread(fb_bot.send_message, message)
                    logger.info("Message sent to Facebook:\n" + message)
            
            await asyncio.sleep(CHECK_INTERVAL)
            print(f"♻️ Refreshed at {datetime.today().strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            logger.error(f"⚠️ Error in CoC monitor: {str(e)}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())