from src.core.database import get_db, init_db

def seed_data():
    init_db()
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Seed test tenants
        tenants = [
            ('tenant_free_1', 'Acme Free Corp', 'free', 'active'),
            ('tenant_pro_1', 'Enterprise Pro Ltd', 'pro', 'active'),
            ('tenant_unpaid_1', 'Delinquent Inc', 'free', 'past_due')
        ]
        
        cursor.executemany("""
            INSERT OR REPLACE INTO tenants (id, name, plan_id, status)
            VALUES (?, ?, ?, ?);
        """, tenants)
        
    print("Seed executed successfully: tenant_free_1, tenant_pro_1, tenant_unpaid_1.")

if __name__ == "__main__":
    seed_data()
