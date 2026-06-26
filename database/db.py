import os
import sqlite3
from werkzeug.security import generate_password_hash

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH  = os.path.join(_BASE_DIR, 'spendly.db')


def get_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0:
            return

        cursor = conn.execute(
            'INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)',
            ('Demo User', 'demo@spendly.com', generate_password_hash('demo123'))
        )
        user_id = cursor.lastrowid

        expenses = [
            (user_id, 450.00,  'Food',          '2026-06-02', 'Lunch at office canteen'),
            (user_id, 180.00,  'Transport',     '2026-06-04', 'Metro card recharge'),
            (user_id, 1200.00, 'Bills',         '2026-06-06', 'Electricity bill'),
            (user_id, 650.00,  'Health',        '2026-06-10', 'Pharmacy - vitamins'),
            (user_id, 499.00,  'Entertainment', '2026-06-14', 'Netflix subscription'),
            (user_id, 2300.00, 'Shopping',      '2026-06-18', 'New shirt and trousers'),
            (user_id, 300.00,  'Other',         '2026-06-20', 'Charitable donation'),
            (user_id, 820.00,  'Food',          '2026-06-25', 'Weekly groceries'),
        ]
        conn.executemany(
            'INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)',
            expenses
        )
        conn.commit()
    finally:
        conn.close()
