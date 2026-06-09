import sqlite3

DB_NAME = "bans.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bans (
        code TEXT PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        reason TEXT,
        moderator_id INTEGER,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


def add_ban(code, user_id, username, reason, moderator_id, created_at):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO bans (code, user_id, username, reason, moderator_id, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (code, user_id, username, reason, moderator_id, created_at))

    conn.commit()
    conn.close()


def get_ban(code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bans WHERE code = ?", (code,))
    result = cursor.fetchone()

    conn.close()
    return result