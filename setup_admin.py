import sqlite3
from werkzeug.security import generate_password_hash
from config import Config

def setup_admin():
    db_path = Config.DATABASE
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    email = 'admin@gesru.de'
    password = 'admin123'
    hashed_password = generate_password_hash(password)
    name = 'Admin User'

    # Check if user exists
    user = c.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()

    if user:
        print(f"Updating existing user {email}...")
        c.execute('''
            UPDATE users 
            SET password_hash = ?, is_verified = 1, is_approved = 1, is_admin = 1 
            WHERE email = ?
        ''', (hashed_password, email))
    else:
        print(f"Creating new user {email}...")
        c.execute('''
            INSERT INTO users (name, email, password_hash, ausbildungsjahr, is_verified, is_approved, is_admin)
            VALUES (?, ?, ?, 6, 1, 1, 1)
        ''', (name, email, hashed_password))

    conn.commit()
    conn.close()
    print("Admin user setup complete.")

if __name__ == '__main__':
    setup_admin()
