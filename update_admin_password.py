"""
Quick script to update admin password to bcrypt
"""
from db_multitenant import get_db, hash_password

with get_db() as conn:
    # Check if admin exists
    user = conn.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()

    if user:
        print(f"[OK] Admin user found: {user['name']}")
        print(f"  Current hash starts with: {user['password_hash'][:20]}...")

        # Update to bcrypt
        new_hash = hash_password('admin123')
        conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, 'admin'))

        print(f"[OK] Password updated to bcrypt")
        print(f"  New hash starts with: {new_hash[:20]}...")
        print()
        print("Login credentials:")
        print("  Username: admin")
        print("  Password: admin123")
    else:
        print("[ERROR] Admin user not found!")
        print("Creating new admin user...")

        from db_multitenant import create_user
        user_id = create_user(
            username='admin',
            password='admin123',
            name='System Administrator',
            email='admin@friktionskompas.dk',
            role='admin',
            customer_id=None
        )

        print(f"[OK] Admin user created: {user_id}")
        print()
        print("Login credentials:")
        print("  Username: admin")
        print("  Password: admin123")
