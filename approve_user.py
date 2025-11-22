import sqlite3
from config import Config

def approve_test_user():
    db_path = Config.DATABASE
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    email = 'test@example.com'

    # Check if user exists
    user = c.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()

    if user:
        print(f"Approving user {email}...")
        c.execute('''
            UPDATE users 
            SET is_approved = 1
            WHERE email = ?
        ''', (email,))
        conn.commit()
        print("User approved.")
    else:
        print(f"User {email} not found.")

    conn.close()

if __name__ == '__main__':
    approve_test_user()
