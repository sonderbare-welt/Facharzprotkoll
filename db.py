import sqlite3
from flask import g, current_app

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    # Hier können Tabellen erstellt werden, falls nötig
    # In der ursprünglichen app.py war hier die Tabellenerstellung
    # Wir übernehmen das Schema aus der ursprünglichen Datei
    
    # Benutzer-Tabelle
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            passwort_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            ausbildungsjahr INTEGER,
            is_admin BOOLEAN DEFAULT 0,
            is_approved BOOLEAN DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0,
            verification_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Protokoll-Tabelle
    db.execute('''
        CREATE TABLE IF NOT EXISTS protokolle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pruefungsdatum DATE NOT NULL,
            bundesland TEXT NOT NULL,
            stadt TEXT NOT NULL,
            pruefer1_id INTEGER NOT NULL,
            pruefer2_id INTEGER NOT NULL,
            pruefer3_id INTEGER NOT NULL,
            inhalt TEXT NOT NULL,
            hashtags TEXT,
            kommentar TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (pruefer1_id) REFERENCES pruefer (id),
            FOREIGN KEY (pruefer2_id) REFERENCES pruefer (id),
            FOREIGN KEY (pruefer3_id) REFERENCES pruefer (id)
        )
    ''')

    # Prüfer-Tabelle
    db.execute('''
        CREATE TABLE IF NOT EXISTS pruefer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT,
            vorname TEXT,
            name TEXT NOT NULL,
            klinik TEXT,
            stadt TEXT,
            bundesland TEXT NOT NULL,
            fachgebiet TEXT DEFAULT 'Urologie',
            active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Erinnerungen-Tabelle
    db.execute('''
        CREATE TABLE IF NOT EXISTS erinnerungen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pruefungsdatum DATE NOT NULL,
            naechste_erinnerung TIMESTAMP,
            protokoll_erstellt BOOLEAN DEFAULT 0,
            erinnerung_gesendet BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Logs-Tabelle
    db.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    db.commit()

def init_app(app):
    app.teardown_appcontext(close_db)
