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
    conn = sqlite3.connect('war_attacks_test.db')
    c = conn.cursor()

    # Create table for logging processed attacks
    c.execute('''
        CREATE TABLE IF NOT EXISTS logged_attacks (
            attacker_tag TEXT,
            defender_name TEXT,
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

def log_attack(attacker_tag, defender_name, attack_order):
    conn = sqlite3.connect('war_attacks.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO logged_attacks (attacker_tag, defender_name, attack_order)
        VALUES (?, ?, ?)
    ''', (attacker_tag, defender_name, attack_order))
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

async def recent_attack(coc_monitor):
    """Fetch and send recent attacks from clan war, avoiding duplicates."""

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
            defender_name = attack['defender_name']
            attack_order = attack['order']

            if is_attack_logged(attacker_tag, defender_name, attack_order):
                continue

            destruction = attack['destruction'] or 0

            # Choose message
            if destruction < 70:
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
            log_attack(attacker_tag, defender_name, attack_order)

        await asyncio.sleep(10)

async def main():
    coc_monitor = CocMonitor()

    init_db()
    init_attack_log_db()

    try:
        # Run both tasks concurrently
        await asyncio.gather(
            recent_attack(coc_monitor)
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())