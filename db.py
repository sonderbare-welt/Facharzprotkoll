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
        CREATE TABLE IF NOT EXISTS benutzer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            passwort_hash TEXT NOT NULL,
            vorname TEXT NOT NULL,
            nachname TEXT NOT NULL,
            klinik TEXT,
            weiterbildungsjahr INTEGER,
            bundesland TEXT,
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
            ersteller_id INTEGER NOT NULL,
            datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pruefungsdatum DATE NOT NULL,
            bundesland TEXT NOT NULL,
            stadt TEXT NOT NULL,
            pruefer1 TEXT NOT NULL,
            pruefer2 TEXT NOT NULL,
            pruefer3 TEXT NOT NULL,
            inhalt TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (ersteller_id) REFERENCES benutzer (id)
        )
    ''')

    # Prüfer-Tabelle
    db.execute('''
        CREATE TABLE IF NOT EXISTS pruefer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT,
            vorname TEXT,
            nachname TEXT NOT NULL,
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
            erinnerung_gesendet BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES benutzer (id)
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
            FOREIGN KEY (user_id) REFERENCES benutzer (id)
        )
    ''')
    
    db.commit()

def init_app(app):
    app.teardown_appcontext(close_db)
