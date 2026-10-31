import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DATABASE_PATH", "billing.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Plans Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            monthly_api_calls_limit INTEGER NOT NULL,
            monthly_tokens_limit INTEGER NOT NULL,
            price_cents INTEGER NOT NULL
        );
        """)
        
        # 2. Tenants Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            plan_id TEXT NOT NULL REFERENCES plans(id),
            status TEXT NOT NULL DEFAULT 'active', -- active, past_due, canceled
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 3. Usage Events Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL REFERENCES tenants(id),
            event_type TEXT NOT NULL, -- 'api_call' or 'ai_tokens'
            quantity INTEGER NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            cached_input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            reasoning_tokens INTEGER DEFAULT 0,
            cost_nano_usd INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, idempotency_key)
        );
        """)
        
        # 4. Idempotency Response Cache Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_records (
            tenant_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            response_payload TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(tenant_id, idempotency_key)
        );
        """)
        
        # Indexes for fast monthly rollups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_tenant_date ON usage_events(tenant_id, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_idem ON usage_events(tenant_id, idempotency_key);")
        
        # Seed Base Plans
        cursor.execute("""
        INSERT OR IGNORE INTO plans (id, name, monthly_api_calls_limit, monthly_tokens_limit, price_cents)
        VALUES 
            ('free', 'Free Tier', 1000, 100000, 0),
            ('pro', 'Pro Subscription', 50000, 10000000, 2900);
        """)

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
