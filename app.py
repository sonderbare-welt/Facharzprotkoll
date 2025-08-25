#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Urologische Facharztprüfung Protokoll-Sammlung
Flask Web Application
"""

import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
import re

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import schedule

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Konfiguration der Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'msondermann93@gmail.com'  # Hier Ihre E-Mail eintragen
app.config['MAIL_PASSWORD'] = 'dsnfqeqetnfgxelw'  # Hier Ihr App-Passwort eintragen
app.config['MAIL_DEFAULT_SENDER'] = 'msondermann93@gmail.com'

mail = Mail(app)

# Datenbank-Pfad
DATABASE = 'urologie_pruefung.db'

# Vordefinierte Hashtags für Urologie
PREDEFINED_HASHTAGS = [
    '#Andrologie', '#Onkologie', '#Kinderurologie', '#Steinleiden', '#Harninkontinenz',
    '#Neurourologie', '#Transplantation', '#Endourologie', '#Infektiologie', '#Traumatologie',
    '#rekonstruktive-Urologie', '#Labordiagnostik', '#Bildgebung', '#Notfälle',
    '#Prostata', '#Hoden', '#Niere', '#Blase', '#Urethra', '#Anatomie', '#Physiologie',
    '#Prostatakarzinom','#Nierenzelkarzinom','#Urothelkarzinom','Hodentumor','#Peniskarzinom'
]

# Bundesländer
BUNDESLAENDER = [
    'Baden-Württemberg', 'Bayern', 'Berlin', 'Brandenburg', 'Bremen',
    'Hamburg', 'Hessen', 'Mecklenburg-Vorpommern', 'Niedersachsen',
    'Nordrhein-Westfalen', 'Rheinland-Pfalz', 'Saarland', 'Sachsen',
    'Sachsen-Anhalt', 'Schleswig-Holstein', 'Thüringen'
]


def init_db():
    """Datenbank initialisieren"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Benutzer-Tabelle
    c.execute('''
              CREATE TABLE IF NOT EXISTS users
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  name
                  TEXT
                  NOT
                  NULL,
                  email
                  TEXT
                  UNIQUE
                  NOT
                  NULL,
                  password_hash
                  TEXT
                  NOT
                  NULL,
                  ausbildungsjahr
                  INTEGER
                  NOT
                  NULL,
                  is_verified
                  BOOLEAN
                  DEFAULT
                  FALSE,
                  is_approved
                  BOOLEAN
                  DEFAULT
                  FALSE,
                  is_admin
                  BOOLEAN
                  DEFAULT
                  FALSE,
                  verification_token
                  TEXT,
                  created_at
                  TIMESTAMP
                  DEFAULT
                  CURRENT_TIMESTAMP
              )
              ''')

    # Prüfer-Tabelle
    c.execute('''
              CREATE TABLE IF NOT EXISTS pruefer
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  name
                  TEXT
                  NOT
                  NULL,
                  bundesland
                  TEXT
                  NOT
                  NULL,
                  created_at
                  TIMESTAMP
                  DEFAULT
                  CURRENT_TIMESTAMP
              )
              ''')

    # Protokoll-Tabelle
    c.execute('''
              CREATE TABLE IF NOT EXISTS protokolle
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  user_id
                  INTEGER
                  NOT
                  NULL,
                  datum
                  DATE
                  NOT
                  NULL,
                  bundesland
                  TEXT
                  NOT
                  NULL,
                  pruefer1_id
                  INTEGER
                  NOT
                  NULL,
                  pruefer2_id
                  INTEGER
                  NOT
                  NULL,
                  pruefer3_id
                  INTEGER
                  NOT
                  NULL,
                  inhalt
                  TEXT
                  NOT
                  NULL,
                  hashtags
                  TEXT,
                  kommentar
                  TEXT,
                  created_at
                  TIMESTAMP
                  DEFAULT
                  CURRENT_TIMESTAMP,
                  FOREIGN
                  KEY
              (
                  user_id
              ) REFERENCES users
              (
                  id
              ),
                  FOREIGN KEY
              (
                  pruefer1_id
              ) REFERENCES pruefer
              (
                  id
              ),
                  FOREIGN KEY
              (
                  pruefer2_id
              ) REFERENCES pruefer
              (
                  id
              ),
                  FOREIGN KEY
              (
                  pruefer3_id
              ) REFERENCES pruefer
              (
                  id
              )
                  )
              ''')

    # Erinnerungs-Tabelle
    c.execute('''
              CREATE TABLE IF NOT EXISTS erinnerungen
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  user_id
                  INTEGER
                  NOT
                  NULL,
                  pruefungsdatum
                  DATE
                  NOT
                  NULL,
                  naechste_erinnerung
                  TIMESTAMP
                  NOT
                  NULL,
                  anzahl_erinnerungen
                  INTEGER
                  DEFAULT
                  0,
                  protokoll_erstellt
                  BOOLEAN
                  DEFAULT
                  FALSE,
                  created_at
                  TIMESTAMP
                  DEFAULT
                  CURRENT_TIMESTAMP,
                  FOREIGN
                  KEY
              (
                  user_id
              ) REFERENCES users
              (
                  id
              )
                  )
              ''')

    # Admin-Benutzer erstellen (falls nicht vorhanden)
    c.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE')
    if c.fetchone()[0] == 0:
        admin_hash = generate_password_hash('admin123')
        c.execute('''
                  INSERT INTO users (name, email, password_hash, ausbildungsjahr, is_verified, is_approved, is_admin)
                  VALUES (?, ?, ?, ?, ?, ?, ?)
                  ''', ('Admin', 'admin@urologie-app.de', admin_hash, 6, True, True, True))

    # Beispiel-Prüfer hinzufügen
    beispiel_pruefer = [
        ('Prof. Dr. Müller', 'Bayern'),
        ('Dr. Schmidt', 'Nordrhein-Westfalen'),
        ('Prof. Dr. Weber', 'Baden-Württemberg'),
        ('Dr. Fischer', 'Berlin'),
        ('Prof. Dr. Meyer', 'Hamburg')
    ]

    for name, bundesland in beispiel_pruefer:
        c.execute('SELECT COUNT(*) FROM pruefer WHERE name = ? AND bundesland = ?', (name, bundesland))
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO pruefer (name, bundesland) VALUES (?, ?)', (name, bundesland))

    conn.commit()
    conn.close()


def login_required(f):
    """Decorator für Login-Pflicht"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator für Admin-Rechte"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
        user = c.fetchone()
        conn.close()

        if not user or not user[0]:
            flash('Keine Berechtigung für diese Seite.', 'error')
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)

    return decorated_function


@app.route('/admin/benutzer')
@admin_required
def admin_benutzer():
    """Benutzerverwaltung"""
    # Filter-Parameter
    status_filter = request.args.get('status', 'all')  # all, pending, approved, admin
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'created_at')  # name, email, created_at, protokolle_count
    sort_order = request.args.get('order', 'desc')  # asc, desc

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Basis-Query mit Protokoll-Zählung
    base_query = '''
                 SELECT u.id, \
                        u.name, \
                        u.email, \
                        u.ausbildungsjahr, \
                        u.created_at,
                        u.is_verified, \
                        u.is_approved, \
                        u.is_admin,
                        COUNT(p.id)       as protokolle_count,
                        MAX(p.created_at) as letztes_protokoll
                 FROM users u
                          LEFT JOIN protokolle p ON u.id = p.user_id
                 WHERE 1 = 1 \
                 '''

    params = []

    # Status-Filter
    if status_filter == 'pending':
        base_query += ' AND u.is_verified = TRUE AND u.is_approved = FALSE'
    elif status_filter == 'approved':
        base_query += ' AND u.is_approved = TRUE AND u.is_admin = FALSE'
    elif status_filter == 'admin':
        base_query += ' AND u.is_admin = TRUE'

    # Such-Filter
    if search_query:
        base_query += ' AND (u.name LIKE ? OR u.email LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    # GROUP BY hinzufügen
    base_query += ' GROUP BY u.id, u.name, u.email, u.ausbildungsjahr, u.created_at, u.is_verified, u.is_approved, u.is_admin'

    # Sortierung
    valid_sorts = {
        'name': 'u.name',
        'email': 'u.email',
        'created_at': 'u.created_at',
        'protokolle_count': 'protokolle_count'
    }

    if sort_by in valid_sorts:
        order_direction = 'DESC' if sort_order == 'desc' else 'ASC'
        base_query += f' ORDER BY {valid_sorts[sort_by]} {order_direction}'
    else:
        base_query += ' ORDER BY u.created_at DESC'

    c.execute(base_query, params)
    alle_benutzer = c.fetchall()

    # Statistiken
    c.execute('SELECT COUNT(*) FROM users WHERE is_verified = TRUE AND is_approved = FALSE')
    wartende_benutzer = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM users WHERE is_approved = TRUE AND is_admin = FALSE')
    aktive_benutzer = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE')
    admin_benutzer = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM users')
    gesamt_benutzer = c.fetchone()[0]

    conn.close()

    return render_template('admin/benutzer.html',
                           benutzer=alle_benutzer,
                           status_filter=status_filter,
                           search_query=search_query,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           wartende_benutzer=wartende_benutzer,
                           aktive_benutzer=aktive_benutzer,
                           admin_benutzer=admin_benutzer,
                           gesamt_benutzer=gesamt_benutzer)


@app.route('/admin/benutzer/<int:user_id>/admin-status', methods=['POST'])
@admin_required
def toggle_admin_status(user_id):
    """Admin-Status eines Benutzers ändern"""
    action = request.form.get('action')  # 'promote' oder 'demote'

    # Nicht sich selbst degradieren
    if user_id == session['user_id']:
        flash('Sie können Ihren eigenen Admin-Status nicht ändern.', 'error')
        return redirect(url_for('admin_benutzer'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Benutzer-Informationen abrufen
    c.execute('SELECT id, name, email, is_admin, is_approved FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()

    if not user_data:
        flash('Benutzer nicht gefunden.', 'error')
        conn.close()
        return redirect(url_for('admin_benutzer'))

    user_name = user_data[1]
    user_email = user_data[2]
    is_current_admin = user_data[3]
    is_approved = user_data[4]

    try:
        if action == 'promote':
            if is_current_admin:
                flash(f'{user_name} ist bereits ein Administrator.', 'warning')
            else:
                # Benutzer muss approved sein
                if not is_approved:
                    flash('Benutzer muss erst freigeschaltet werden, bevor er zum Admin ernannt werden kann.', 'error')
                else:
                    c.execute('UPDATE users SET is_admin = TRUE WHERE id = ?', (user_id,))
                    conn.commit()

                    # E-Mail-Benachrichtigung senden
                    subject = "Sie wurden zum Administrator ernannt - Urologie Facharztprüfung"
                    body = f"""
                    <html>
                    <body>
                        <h2>🎉 Herzlichen Glückwunsch!</h2>
                        <p>Hallo {user_name},</p>
                        <p>Sie wurden zum Administrator der Urologie Facharztprüfung Plattform ernannt.</p>

                        <h3>Ihre neuen Berechtigungen:</h3>
                        <ul>
                            <li>✅ Benutzer freischalten und verwalten</li>
                            <li>👨‍⚕️ Prüfer hinzufügen und bearbeiten</li>
                            <li>📊 Admin-Dashboard Zugriff</li>
                            <li>🗑️ Protokolle moderieren</li>
                            <li>👥 Andere Administratoren ernennen</li>
                        </ul>

                        <p>Sie können jetzt über den "Admin" Bereich auf erweiterte Funktionen zugreifen.</p>

                        <p><a href="{url_for('admin_dashboard', _external=True)}" 
                           style="background-color: #3FA357; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           Zum Admin-Dashboard
                        </a></p>

                        <p>Vielen Dank für Ihr Engagement!</p>
                    </body>
                    </html>
                    """

                    if send_email(user_email, subject, body):
                        flash(f'{user_name} wurde erfolgreich zum Administrator ernannt und per E-Mail benachrichtigt.',
                              'success')
                    else:
                        flash(
                            f'{user_name} wurde zum Administrator ernannt, aber E-Mail-Benachrichtigung fehlgeschlagen.',
                            'warning')

        elif action == 'demote':
            if not is_current_admin:
                flash(f'{user_name} ist kein Administrator.', 'warning')
            else:
                # Prüfen ob es noch andere Admins gibt
                c.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE AND id != ?', (user_id,))
                andere_admins = c.fetchone()[0]

                if andere_admins == 0:
                    flash(
                        'Sie können den letzten Administrator nicht degradieren. Es muss mindestens ein Administrator vorhanden sein.',
                        'error')
                else:
                    c.execute('UPDATE users SET is_admin = FALSE WHERE id = ?', (user_id,))
                    conn.commit()

                    # E-Mail-Benachrichtigung senden
                    subject = "Administrator-Status entfernt - Urologie Facharztprüfung"
                    body = f"""
                    <html>
                    <body>
                        <h2>Administrator-Status geändert</h2>
                        <p>Hallo {user_name},</p>
                        <p>Ihr Administrator-Status für die Urologie Facharztprüfung Plattform wurde entfernt.</p>

                        <p>Sie haben weiterhin Zugriff auf alle normalen Funktionen der Plattform:</p>
                        <ul>
                            <li>📝 Protokolle erstellen und einsehen</li>
                            <li>🔍 In Protokollen suchen</li>
                            <li>👤 Ihr Profil verwalten</li>
                            <li>📧 Erinnerungen erhalten</li>
                        </ul>

                        <p>Bei Fragen wenden Sie sich an einen Administrator.</p>

                        <p><a href="{url_for('dashboard', _external=True)}" 
                           style="background-color: #606AAC; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           Zum Dashboard
                        </a></p>
                    </body>
                    </html>
                    """

                    if send_email(user_email, subject, body):
                        flash(f'Administrator-Status von {user_name} wurde entfernt und per E-Mail benachrichtigt.',
                              'success')
                    else:
                        flash(
                            f'Administrator-Status von {user_name} wurde entfernt, aber E-Mail-Benachrichtigung fehlgeschlagen.',
                            'warning')

        else:
            flash('Ungültige Aktion.', 'error')

    except Exception as e:
        conn.rollback()
        flash('Fehler beim Ändern des Admin-Status.', 'error')
        print(f"Admin-Status Änderung Fehler: {e}")
    finally:
        conn.close()

    return redirect(url_for('admin_benutzer'))


@app.route('/admin/benutzer/<int:user_id>/details')
@admin_required
def benutzer_details(user_id):
    """Benutzer-Details anzeigen"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Benutzer-Informationen
    c.execute('''
              SELECT id,
                     name,
                     email,
                     ausbildungsjahr,
                     created_at,
                     is_verified,
                     is_approved,
                     is_admin,
                     verification_token
              FROM users
              WHERE id = ?
              ''', (user_id,))
    user_data = c.fetchone()

    if not user_data:
        flash('Benutzer nicht gefunden.', 'error')
        conn.close()
        return redirect(url_for('admin_benutzer'))

    # Benutzer-Statistiken
    c.execute('SELECT COUNT(*) FROM protokolle WHERE user_id = ?', (user_id,))
    anzahl_protokolle = c.fetchone()[0]

    c.execute('''
              SELECT MIN(created_at), MAX(created_at)
              FROM protokolle
              WHERE user_id = ?
              ''', (user_id,))
    protokoll_zeitraum = c.fetchone()

    # Letzte Protokolle
    c.execute('''
              SELECT p.datum, p.bundesland, pr.name, p.hashtags, p.created_at
              FROM protokolle p
                       JOIN pruefer pr ON p.pruefer1_id = pr.id
              WHERE p.user_id = ?
              ORDER BY p.created_at DESC LIMIT 10
              ''', (user_id,))
    letzte_protokolle = c.fetchall()

    # Erinnerungen
    c.execute('''
              SELECT pruefungsdatum,
                     naechste_erinnerung,
                     anzahl_erinnerungen,
                     protokoll_erstellt,
                     created_at
              FROM erinnerungen
              WHERE user_id = ?
              ORDER BY created_at DESC
              ''', (user_id,))
    erinnerungen = c.fetchall()

    # Häufigste Hashtags
    c.execute('''
              SELECT hashtags
              FROM protokolle
              WHERE user_id = ?
                AND hashtags IS NOT NULL
                AND hashtags != ''
              ''', (user_id,))

    hashtag_results = c.fetchall()
    hashtag_counter = {}
    for result in hashtag_results:
        if result[0]:
            hashtags = result[0].split()
            for hashtag in hashtags:
                hashtag = hashtag.strip()
                if hashtag:
                    hashtag_counter[hashtag] = hashtag_counter.get(hashtag, 0) + 1

    top_hashtags = sorted(hashtag_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    conn.close()

    user_info = {
        'id': user_data[0],
        'name': user_data[1],
        'email': user_data[2],
        'ausbildungsjahr': user_data[3],
        'created_at': user_data[4],
        'is_verified': user_data[5],
        'is_approved': user_data[6],
        'is_admin': user_data[7],
        'verification_token': user_data[8],
        'anzahl_protokolle': anzahl_protokolle,
        'protokoll_zeitraum': protokoll_zeitraum,
        'letzte_protokolle': letzte_protokolle,
        'erinnerungen': erinnerungen,
        'top_hashtags': top_hashtags
    }

    return render_template('admin/benutzer_details.html', user=user_info)


@app.route('/admin/benutzer/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    """Benutzer sperren/entsperren"""
    action = request.form.get('action')  # 'suspend' oder 'unsuspend'
    reason = request.form.get('reason', '').strip()

    # Nicht sich selbst sperren
    if user_id == session['user_id']:
        flash('Sie können sich nicht selbst sperren.', 'error')
        return redirect(url_for('admin_benutzer'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Benutzer-Informationen abrufen
    c.execute('SELECT id, name, email, is_approved FROM users WHERE id = ?', (user_id,))
    user_data = c.fetchone()

    if not user_data:
        flash('Benutzer nicht gefunden.', 'error')
        conn.close()
        return redirect(url_for('admin_benutzer'))

    user_name = user_data[1]
    user_email = user_data[2]
    is_approved = user_data[3]

    try:
        if action == 'suspend':
            if not is_approved:
                flash(f'{user_name} ist bereits gesperrt.', 'warning')
            else:
                c.execute('UPDATE users SET is_approved = FALSE WHERE id = ?', (user_id,))
                conn.commit()

                # E-Mail-Benachrichtigung
                subject = "Account gesperrt - Urologie Facharztprüfung"
                body = f"""
                <html>
                <body>
                    <h2>Account vorübergehend gesperrt</h2>
                    <p>Hallo {user_name},</p>
                    <p>Ihr Account wurde vorübergehend gesperrt.</p>

                    {f'<p><strong>Grund:</strong> {reason}</p>' if reason else ''}

                    <p>Bei Fragen wenden Sie sich an einen Administrator.</p>
                </body>
                </html>
                """

                send_email(user_email, subject, body)
                flash(f'{user_name} wurde gesperrt.', 'success')

        elif action == 'unsuspend':
            if is_approved:
                flash(f'{user_name} ist nicht gesperrt.', 'warning')
            else:
                c.execute('UPDATE users SET is_approved = TRUE WHERE id = ?', (user_id,))
                conn.commit()

                # E-Mail-Benachrichtigung
                subject = "Account wieder freigeschaltet - Urologie Facharztprüfung"
                body = f"""
                <html>
                <body>
                    <h2>Account wieder freigeschaltet</h2>
                    <p>Hallo {user_name},</p>
                    <p>Ihr Account wurde wieder freigeschaltet. Sie können sich jetzt wieder anmelden.</p>

                    <p><a href="{url_for('login', _external=True)}" 
                       style="background-color: #3FA357; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       Jetzt anmelden
                    </a></p>
                </body>
                </html>
                """

                send_email(user_email, subject, body)
                flash(f'{user_name} wurde entsperrt.', 'success')

        else:
            flash('Ungültige Aktion.', 'error')

    except Exception as e:
        conn.rollback()
        flash('Fehler beim Ändern des Benutzer-Status.', 'error')
        print(f"Benutzer-Status Änderung Fehler: {e}")
    finally:
        conn.close()

    return redirect(url_for('admin_benutzer'))

@app.route('/admin/benutzer/bulk-actions', methods=['POST'])
@admin_required
def benutzer_bulk_actions():
    """Bulk-Aktionen für Benutzer"""
    action = request.form.get('action')
    user_ids = request.form.getlist('user_ids')

    if not user_ids:
        flash('Keine Benutzer ausgewählt.', 'error')
        return redirect(url_for('admin_benutzer'))

    # Eigene ID aus der Liste entfernen
    user_ids = [uid for uid in user_ids if int(uid) != session['user_id']]

    if not user_ids:
        flash('Sie können keine Bulk-Aktionen auf sich selbst anwenden.', 'error')
        return redirect(url_for('admin_benutzer'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    try:
        if action == 'approve':
            placeholders = ','.join(['?' for _ in user_ids])
            c.execute(f'''
                UPDATE users SET is_approved = TRUE 
                WHERE id IN ({placeholders}) AND is_verified = TRUE
            ''', user_ids)
            conn.commit()
            flash(f'{len(user_ids)} Benutzer wurden freigeschaltet.', 'success')

        elif action == 'suspend':
            placeholders = ','.join(['?' for _ in user_ids])
            c.execute(f'UPDATE users SET is_approved = FALSE WHERE id IN ({placeholders})', user_ids)
            conn.commit()
            flash(f'{len(user_ids)} Benutzer wurden gesperrt.', 'success')

        elif action == 'promote_admin':
            placeholders = ','.join(['?' for _ in user_ids])
            c.execute(f'''
                UPDATE users SET is_admin = TRUE 
                WHERE id IN ({placeholders}) AND is_approved = TRUE
            ''', user_ids)
            conn.commit()
            flash(f'{len(user_ids)} Benutzer wurden zu Administratoren ernannt.', 'success')

        elif action == 'demote_admin':
            # Prüfen ob genug Admins übrig bleiben
            c.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE')
            total_admins = c.fetchone()[0]

            if total_admins - len(user_ids) < 1:
                flash('Es muss mindestens ein Administrator übrig bleiben.', 'error')
            else:
                placeholders = ','.join(['?' for _ in user_ids])
                c.execute(f'UPDATE users SET is_admin = FALSE WHERE id IN ({placeholders})', user_ids)
                conn.commit()
                flash(f'{len(user_ids)} Administratoren wurden degradiert.', 'success')

        else:
            flash('Ungültige Aktion ausgewählt.', 'error')

    except Exception as e:
        conn.rollback()
        flash('Fehler bei der Bulk-Aktion.', 'error')
        print(f"Bulk-Action Fehler: {e}")
    finally:
        conn.close()

    return redirect(url_for('admin_benutzer'))

def send_email(to_email, subject, body):
    """E-Mail senden"""
    try:
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        text = msg.as_string()
        server.sendmail(app.config['MAIL_USERNAME'], to_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"E-Mail-Fehler: {e}")
        return False


@app.route('/')
def index():
    """Startseite"""
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Benutzerregistrierung"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        ausbildungsjahr = request.form.get('ausbildungsjahr')

        # Validierung
        if not all([name, email, password, ausbildungsjahr]):
            flash('Alle Felder sind erforderlich.', 'error')
            return render_template('register.html')

        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Ungültige E-Mail-Adresse.', 'error')
            return render_template('register.html')

        try:
            ausbildungsjahr = int(ausbildungsjahr)
            if ausbildungsjahr < 1 or ausbildungsjahr > 6:
                raise ValueError
        except ValueError:
            flash('Ausbildungsjahr muss zwischen 1 und 6 liegen.', 'error')
            return render_template('register.html')

        # Prüfen ob E-Mail bereits existiert
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM users WHERE email = ?', (email,))
        if c.fetchone()[0] > 0:
            conn.close()
            flash('E-Mail-Adresse bereits registriert.', 'error')
            return render_template('register.html')

        # Benutzer erstellen
        password_hash = generate_password_hash(password)
        verification_token = secrets.token_urlsafe(32)

        c.execute('''
                  INSERT INTO users (name, email, password_hash, ausbildungsjahr, verification_token)
                  VALUES (?, ?, ?, ?, ?)
                  ''', (name, email, password_hash, ausbildungsjahr, verification_token))

        conn.commit()
        conn.close()

        # Verifizierungs-E-Mail senden
        verification_link = url_for('verify_email', token=verification_token, _external=True)
        subject = "E-Mail-Verifizierung - Urologie Facharztprüfung"
        body = f"""
        <html>
        <body>
            <h2>Willkommen bei der Urologie Facharztprüfung Plattform!</h2>
            <p>Hallo {name},</p>
            <p>bitte klicken Sie auf den folgenden Link, um Ihre E-Mail-Adresse zu verifizieren:</p>
            <p><a href="{verification_link}" style="background-color: #007AFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">E-Mail verifizieren</a></p>
            <p>Nach der Verifizierung wird Ihr Account von einem Administrator geprüft und freigeschaltet.</p>
            <p>Vielen Dank!</p>
        </body>
        </html>
        """

        if send_email(email, subject, body):
            flash('Registrierung erfolgreich! Bitte prüfen Sie Ihre E-Mails zur Verifizierung.', 'success')
        else:
            flash('Registrierung erfolgreich, aber E-Mail konnte nicht gesendet werden.', 'warning')

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/verify/<token>')
def verify_email(token):
    """E-Mail-Verifizierung"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, name FROM users WHERE verification_token = ? AND is_verified = FALSE', (token,))
    user = c.fetchone()

    if user:
        c.execute('UPDATE users SET is_verified = TRUE, verification_token = NULL WHERE id = ?', (user[0],))
        conn.commit()
        flash('E-Mail erfolgreich verifiziert! Ihr Account wird nun von einem Administrator geprüft.', 'success')
    else:
        flash('Ungültiger oder bereits verwendeter Verifizierungslink.', 'error')

    conn.close()
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Benutzeranmeldung"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('E-Mail und Passwort sind erforderlich.', 'error')
            return render_template('login.html')

        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
                  SELECT id, name, password_hash, is_verified, is_approved, is_admin
                  FROM users
                  WHERE email = ?
                  ''', (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            if not user[3]:  # is_verified
                flash('Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.', 'error')
                return render_template('login.html')

            if not user[4]:  # is_approved
                flash('Ihr Account wurde noch nicht von einem Administrator freigeschaltet.', 'error')
                return render_template('login.html')

            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['is_admin'] = user[5]

            flash(f'Willkommen zurück, {user[1]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Ungültige Anmeldedaten.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Benutzerabmeldung"""
    session.clear()
    flash('Sie wurden erfolgreich abgemeldet.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Statistiken abrufen
    c.execute('SELECT COUNT(*) FROM protokolle WHERE user_id = ?', (session['user_id'],))
    meine_protokolle = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM protokolle')
    gesamt_protokolle = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM pruefer')
    anzahl_pruefer = c.fetchone()[0]

    # Neueste Protokolle
    c.execute('''
              SELECT p.datum, p.bundesland, pr1.name, p.hashtags, p.created_at
              FROM protokolle p
                       JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
              ORDER BY p.created_at DESC LIMIT 5
              ''')
    neueste_protokolle = c.fetchall()

    conn.close()

    return render_template('dashboard.html',
                           meine_protokolle=meine_protokolle,
                           gesamt_protokolle=gesamt_protokolle,
                           anzahl_pruefer=anzahl_pruefer,
                           neueste_protokolle=neueste_protokolle)


@app.route('/protokolle')
@login_required
def protokolle():
    """Protokoll-Übersicht mit Admin-Features"""
    bundesland_filter = request.args.get('bundesland', '')
    pruefer_filter = request.args.get('pruefer', '')
    hashtag_filter = request.args.get('hashtag', '')

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Basis-Query
    query = '''
            SELECT p.id, \
                   p.datum, \
                   p.bundesland, \
                   pr1.name as pruefer1, \
                   pr2.name as pruefer2,
                   pr3.name as pruefer3, \
                   p.hashtags, \
                   p.inhalt, \
                   p.kommentar, \
                   u.name   as user_name,
                   p.user_id
            FROM protokolle p
                     JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
                     JOIN pruefer pr2 ON p.pruefer2_id = pr2.id
                     JOIN pruefer pr3 ON p.pruefer3_id = pr3.id
                     JOIN users u ON p.user_id = u.id
            WHERE 1 = 1 \
            '''

    params = []

    if bundesland_filter:
        query += ' AND p.bundesland = ?'
        params.append(bundesland_filter)

    if pruefer_filter:
        query += ' AND (pr1.name LIKE ? OR pr2.name LIKE ? OR pr3.name LIKE ?)'
        params.extend([f'%{pruefer_filter}%'] * 3)

    if hashtag_filter:
        query += ' AND p.hashtags LIKE ?'
        params.append(f'%{hashtag_filter}%')

    query += ' ORDER BY p.created_at DESC'

    c.execute(query, params)
    protokoll_liste = c.fetchall()

    # Prüfer für Filter laden
    c.execute('SELECT DISTINCT name FROM pruefer ORDER BY name')
    alle_pruefer = [row[0] for row in c.fetchall()]

    # Prüfen ob aktueller Benutzer Admin ist
    is_admin = session.get('is_admin', False)

    conn.close()

    return render_template('protokolle.html',
                           protokolle=protokoll_liste,
                           bundeslaender=BUNDESLAENDER,
                           alle_pruefer=alle_pruefer,
                           predefined_hashtags=PREDEFINED_HASHTAGS,
                           bundesland_filter=bundesland_filter,
                           pruefer_filter=pruefer_filter,
                           hashtag_filter=hashtag_filter,
                           is_admin=is_admin)


@app.route('/protokoll/neu', methods=['GET', 'POST'])
@login_required
def neues_protokoll():
    """Neues Protokoll erstellen"""
    if request.method == 'POST':
        datum = request.form.get('datum')
        bundesland = request.form.get('bundesland')
        pruefer1_id = request.form.get('pruefer1')
        pruefer2_id = request.form.get('pruefer2')
        pruefer3_id = request.form.get('pruefer3')
        inhalt = request.form.get('inhalt')
        hashtags = request.form.get('hashtags')
        kommentar = request.form.get('kommentar', '')

        # Validierung
        if not all([datum, bundesland, pruefer1_id, pruefer2_id, pruefer3_id, inhalt]):
            flash('Alle Pflichtfelder müssen ausgefüllt werden.', 'error')
            return redirect(url_for('neues_protokoll'))

        # Prüfen ob Prüfer existieren
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        for pruefer_id in [pruefer1_id, pruefer2_id, pruefer3_id]:
            c.execute('SELECT COUNT(*) FROM pruefer WHERE id = ?', (pruefer_id,))
            if c.fetchone()[0] == 0:
                flash('Ungültiger Prüfer ausgewählt.', 'error')
                conn.close()
                return redirect(url_for('neues_protokoll'))

        # Protokoll speichern
        c.execute('''
                  INSERT INTO protokolle (user_id, datum, bundesland, pruefer1_id, pruefer2_id,
                                          pruefer3_id, inhalt, hashtags, kommentar)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                  ''', (session['user_id'], datum, bundesland, pruefer1_id, pruefer2_id,
                        pruefer3_id, inhalt, hashtags, kommentar))

        # Erinnerung als erledigt markieren (falls vorhanden)
        c.execute('''
                  UPDATE erinnerungen
                  SET protokoll_erstellt = TRUE
                  WHERE user_id = ?
                    AND protokoll_erstellt = FALSE
                  ''', (session['user_id'],))

        conn.commit()
        conn.close()

        flash('Protokoll erfolgreich erstellt!', 'success')
        return redirect(url_for('protokolle'))

    # Prüfer nach Bundesland laden
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name')
    alle_pruefer = c.fetchall()
    conn.close()

    # Prüfer nach Bundesland gruppieren
    pruefer_nach_bundesland = {}
    for pruefer in alle_pruefer:
        if pruefer[2] not in pruefer_nach_bundesland:
            pruefer_nach_bundesland[pruefer[2]] = []
        pruefer_nach_bundesland[pruefer[2]].append({'id': pruefer[0], 'name': pruefer[1]})

    return render_template('neues_protokoll.html',
                           bundeslaender=BUNDESLAENDER,
                           pruefer_nach_bundesland=pruefer_nach_bundesland,
                           predefined_hashtags=PREDEFINED_HASHTAGS)


@app.route('/admin/protokoll/<int:protokoll_id>')
@admin_required
def admin_protokoll_details(protokoll_id):
    """Admin-Ansicht für Protokoll-Details"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Protokoll-Informationen mit allen Details
    c.execute('''
              SELECT p.id,
                     p.datum,
                     p.bundesland,
                     p.inhalt,
                     p.hashtags,
                     p.kommentar,
                     p.created_at,
                     u.id,
                     u.name,
                     u.email,
                     pr1.id,
                     pr1.name,
                     pr1.bundesland,
                     pr2.id,
                     pr2.name,
                     pr2.bundesland,
                     pr3.id,
                     pr3.name,
                     pr3.bundesland
              FROM protokolle p
                       JOIN users u ON p.user_id = u.id
                       JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
                       JOIN pruefer pr2 ON p.pruefer2_id = pr2.id
                       JOIN pruefer pr3 ON p.pruefer3_id = pr3.id
              WHERE p.id = ?
              ''', (protokoll_id,))

    protokoll_data = c.fetchone()

    if not protokoll_data:
        flash('Protokoll nicht gefunden.', 'error')
        conn.close()
        return redirect(url_for('protokolle'))

    # Alle Prüfer für Bearbeitung laden
    c.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name')
    alle_pruefer = c.fetchall()

    conn.close()

    protokoll_info = {
        'id': protokoll_data[0],
        'datum': protokoll_data[1],
        'bundesland': protokoll_data[2],
        'inhalt': protokoll_data[3],
        'hashtags': protokoll_data[4],
        'kommentar': protokoll_data[5],
        'created_at': protokoll_data[6],
        'user': {
            'id': protokoll_data[7],
            'name': protokoll_data[8],
            'email': protokoll_data[9]
        },
        'pruefer1': {
            'id': protokoll_data[10],
            'name': protokoll_data[11],
            'bundesland': protokoll_data[12]
        },
        'pruefer2': {
            'id': protokoll_data[13],
            'name': protokoll_data[14],
            'bundesland': protokoll_data[15]
        },
        'pruefer3': {
            'id': protokoll_data[16],
            'name': protokoll_data[17],
            'bundesland': protokoll_data[18]
        }
    }

    # Prüfer nach Bundesland gruppieren
    pruefer_nach_bundesland = {}
    for pruefer in alle_pruefer:
        if pruefer[2] not in pruefer_nach_bundesland:
            pruefer_nach_bundesland[pruefer[2]] = []
        pruefer_nach_bundesland[pruefer[2]].append({'id': pruefer[0], 'name': pruefer[1]})

    return render_template('admin/protokoll_details.html',
                           protokoll=protokoll_info,
                           bundeslaender=BUNDESLAENDER,
                           pruefer_nach_bundesland=pruefer_nach_bundesland,
                           predefined_hashtags=PREDEFINED_HASHTAGS)


@app.route('/admin/protokoll/<int:protokoll_id>/bearbeiten', methods=['GET', 'POST'])
@admin_required
def admin_protokoll_bearbeiten(protokoll_id):
    """Protokoll als Admin bearbeiten"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    if request.method == 'GET':
        # Protokoll-Daten für Bearbeitung laden
        c.execute('''
                  SELECT p.id,
                         p.datum,
                         p.bundesland,
                         p.pruefer1_id,
                         p.pruefer2_id,
                         p.pruefer3_id,
                         p.inhalt,
                         p.hashtags,
                         p.kommentar,
                         p.created_at,
                         u.name
                  FROM protokolle p
                           JOIN users u ON p.user_id = u.id
                  WHERE p.id = ?
                  ''', (protokoll_id,))

        protokoll_data = c.fetchone()

        if not protokoll_data:
            flash('Protokoll nicht gefunden.', 'error')
            conn.close()
            return redirect(url_for('protokolle'))

        # Alle Prüfer laden
        c.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name')
        alle_pruefer = c.fetchall()

        conn.close()

        protokoll_info = {
            'id': protokoll_data[0],
            'datum': protokoll_data[1],
            'bundesland': protokoll_data[2],
            'pruefer1_id': protokoll_data[3],
            'pruefer2_id': protokoll_data[4],
            'pruefer3_id': protokoll_data[5],
            'inhalt': protokoll_data[6],
            'hashtags': protokoll_data[7],
            'kommentar': protokoll_data[8],
            'created_at': protokoll_data[9],
            'user_name': protokoll_data[10]
        }

        # Prüfer nach Bundesland gruppieren
        pruefer_nach_bundesland = {}
        for pruefer in alle_pruefer:
            if pruefer[2] not in pruefer_nach_bundesland:
                pruefer_nach_bundesland[pruefer[2]] = []
            pruefer_nach_bundesland[pruefer[2]].append({'id': pruefer[0], 'name': pruefer[1]})

        return render_template('admin/protokoll_bearbeiten.html',
                               protokoll=protokoll_info,
                               bundeslaender=BUNDESLAENDER,
                               pruefer_nach_bundesland=pruefer_nach_bundesland,
                               predefined_hashtags=PREDEFINED_HASHTAGS)

    # POST Request - Protokoll aktualisieren
    datum = request.form.get('datum', '').strip()
    bundesland = request.form.get('bundesland', '').strip()
    pruefer1_id = request.form.get('pruefer1', '').strip()
    pruefer2_id = request.form.get('pruefer2', '').strip()
    pruefer3_id = request.form.get('pruefer3', '').strip()
    inhalt = request.form.get('inhalt', '').strip()
    hashtags = request.form.get('hashtags', '').strip()
    kommentar = request.form.get('kommentar', '').strip()
    admin_notiz = request.form.get('admin_notiz', '').strip()

    # Validierung
    errors = []

    if not datum:
        errors.append('Datum ist erforderlich.')

    if not bundesland or bundesland not in BUNDESLAENDER:
        errors.append('Gültiges Bundesland ist erforderlich.')

    if not pruefer1_id or not pruefer2_id or not pruefer3_id:
        errors.append('Alle drei Prüfer müssen ausgewählt werden.')

    if not inhalt:
        errors.append('Prüfungsinhalt ist erforderlich.')
    elif len(inhalt) < 10:
        errors.append('Prüfungsinhalt muss mindestens 10 Zeichen lang sein.')

    # Prüfer-IDs validieren
    try:
        pruefer_ids = [int(pruefer1_id), int(pruefer2_id), int(pruefer3_id)]
        if len(set(pruefer_ids)) != 3:
            errors.append('Alle drei Prüfer müssen unterschiedlich sein.')

        # Prüfen ob Prüfer existieren
        for pruefer_id in pruefer_ids:
            c.execute('SELECT COUNT(*) FROM pruefer WHERE id = ?', (pruefer_id,))
            if c.fetchone()[0] == 0:
                errors.append(f'Prüfer mit ID {pruefer_id} existiert nicht.')
    except ValueError:
        errors.append('Ungültige Prüfer-IDs.')

    if errors:
        for error in errors:
            flash(error, 'error')
        conn.close()
        return redirect(url_for('admin_protokoll_bearbeiten', protokoll_id=protokoll_id))

    # Protokoll aktualisieren - KORRIGIERT
    try:
        c.execute('''
                  UPDATE protokolle
                  SET datum       = ?,
                      bundesland  = ?,
                      pruefer1_id = ?,
                      pruefer2_id = ?,
                      pruefer3_id = ?,
                      inhalt      = ?,
                      hashtags    = ?,
                      kommentar   = ?
                  WHERE id = ?
                  ''', (datum, bundesland, int(pruefer1_id), int(pruefer2_id), int(pruefer3_id),
                        inhalt, hashtags, kommentar, protokoll_id))

        # Admin-Bearbeitung protokollieren
        c.execute('''
                  CREATE TABLE IF NOT EXISTS admin_logs
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      admin_user_id
                      INTEGER
                      NOT
                      NULL,
                      action_type
                      TEXT
                      NOT
                      NULL,
                      target_type
                      TEXT
                      NOT
                      NULL,
                      target_id
                      INTEGER
                      NOT
                      NULL,
                      description
                      TEXT,
                      admin_notiz
                      TEXT,
                      created_at
                      TIMESTAMP
                      DEFAULT
                      CURRENT_TIMESTAMP,
                      FOREIGN
                      KEY
                  (
                      admin_user_id
                  ) REFERENCES users
                  (
                      id
                  )
                      )
                  ''')

        # Log-Eintrag erstellen
        log_description = f"Protokoll #{protokoll_id} bearbeitet"
        c.execute('''
                  INSERT INTO admin_logs (admin_user_id, action_type, target_type, target_id, description, admin_notiz)
                  VALUES (?, ?, ?, ?, ?, ?)
                  ''', (session['user_id'], 'edit', 'protokoll', protokoll_id, log_description, admin_notiz))

        conn.commit()

        # Benachrichtigung an ursprünglichen Autor
        if admin_notiz:
            c.execute('''
                      SELECT u.email, u.name
                      FROM protokolle p
                               JOIN users u ON p.user_id = u.id
                      WHERE p.id = ?
                      ''', (protokoll_id,))

            user_data = c.fetchone()
            if user_data:
                subject = "Ihr Protokoll wurde von einem Administrator bearbeitet"
                body = f"""
                <html>
                <body>
                    <h2>Protokoll bearbeitet</h2>
                    <p>Hallo {user_data[1]},</p>
                    <p>Ihr Protokoll vom {datum} wurde von einem Administrator bearbeitet.</p>

                    {f'<p><strong>Administratoren-Notiz:</strong><br>{admin_notiz}</p>' if admin_notiz else ''}

                    <p>Sie können das aktualisierte Protokoll in Ihrem Dashboard einsehen.</p>

                    <p><a href="{url_for('protokolle', _external=True)}" 
                       style="background-color: #3FA357; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       Protokoll ansehen
                    </a></p>
                </body>
                </html>
                """

                send_email(user_data[0], subject, body)

        flash('Protokoll wurde erfolgreich aktualisiert.', 'success')

    except Exception as e:
        conn.rollback()
        flash('Fehler beim Aktualisieren des Protokolls.', 'error')
        print(f"Protokoll-Update Fehler: {e}")
    finally:
        conn.close()

    return redirect(url_for('admin_protokoll_details', protokoll_id=protokoll_id))
@app.route('/admin/protokoll/<int:protokoll_id>/loeschen', methods=['POST'])
@admin_required
def admin_protokoll_loeschen(protokoll_id):
    """Protokoll als Admin löschen"""
    admin_grund = request.form.get('grund', '').strip()

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Protokoll-Informationen für Benachrichtigung abrufen
    c.execute('''
              SELECT p.datum, u.email, u.name
              FROM protokolle p
                       JOIN users u ON p.user_id = u.id
              WHERE p.id = ?
              ''', (protokoll_id,))

    protokoll_info = c.fetchone()

    if not protokoll_info:
        flash('Protokoll nicht gefunden.', 'error')
        conn.close()
        return redirect(url_for('protokolle'))

    datum, user_email, user_name = protokoll_info

    try:
        # Admin-Log erstellen bevor gelöscht wird
        c.execute('''
                  CREATE TABLE IF NOT EXISTS admin_logs
                  (
                      id
                      INTEGER
                      PRIMARY
                      KEY
                      AUTOINCREMENT,
                      admin_user_id
                      INTEGER
                      NOT
                      NULL,
                      action_type
                      TEXT
                      NOT
                      NULL,
                      target_type
                      TEXT
                      NOT
                      NULL,
                      target_id
                      INTEGER
                      NOT
                      NULL,
                      description
                      TEXT,
                      admin_notiz
                      TEXT,
                      created_at
                      TIMESTAMP
                      DEFAULT
                      CURRENT_TIMESTAMP,
                      FOREIGN
                      KEY
                  (
                      admin_user_id
                  ) REFERENCES users
                  (
                      id
                  )
                      )
                  ''')

        log_description = f"Protokoll #{protokoll_id} vom {datum} gelöscht"
        c.execute('''
                  INSERT INTO admin_logs (admin_user_id, action_type, target_type, target_id, description, admin_notiz)
                  VALUES (?, ?, ?, ?, ?, ?)
                  ''', (session['user_id'], 'delete', 'protokoll', protokoll_id, log_description, admin_grund))

        # Protokoll löschen
        c.execute('DELETE FROM protokolle WHERE id = ?', (protokoll_id,))

        conn.commit()

        # Benachrichtigung an ursprünglichen Autor
        if admin_grund:
            subject = "Ihr Protokoll wurde von einem Administrator entfernt"
            body = f"""
            <html>
            <body>
                <h2>Protokoll entfernt</h2>
                <p>Hallo {user_name},</p>
                <p>Ihr Protokoll vom {datum} wurde von einem Administrator entfernt.</p>

                <p><strong>Grund:</strong><br>{admin_grund}</p>

                <p>Bei Fragen wenden Sie sich an einen Administrator.</p>
            </body>
            </html>
            """

            send_email(user_email, subject, body)

        flash('Protokoll wurde gelöscht.', 'success')

    except Exception as e:
        conn.rollback()
        flash('Fehler beim Löschen des Protokolls.', 'error')
        print(f"Protokoll-Löschung Fehler: {e}")
    finally:
        conn.close()

    return redirect(url_for('protokolle'))


@app.route('/admin/protokolle')
@admin_required
def admin_protokolle():
    """Admin-Übersicht aller Protokolle"""
    # Filter-Parameter
    bundesland_filter = request.args.get('bundesland', '')
    pruefer_filter = request.args.get('pruefer', '')
    hashtag_filter = request.args.get('hashtag', '')
    user_filter = request.args.get('user', '')
    datum_von = request.args.get('datum_von', '')
    datum_bis = request.args.get('datum_bis', '')
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Erweiterte Query für Admin-Ansicht
    query = '''
            SELECT p.id, \
                   p.datum, \
                   p.bundesland, \
                   pr1.name as pruefer1, \
                   pr2.name as pruefer2,
                   pr3.name as pruefer3, \
                   p.hashtags, \
                   p.inhalt, \
                   p.kommentar, \
                   u.name   as user_name,
                   p.created_at, \
                   u.id     as user_id
            FROM protokolle p
                     JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
                     JOIN pruefer pr2 ON p.pruefer2_id = pr2.id
                     JOIN pruefer pr3 ON p.pruefer3_id = pr3.id
                     JOIN users u ON p.user_id = u.id
            WHERE 1 = 1 \
            '''

    params = []

    # Filter anwenden
    if bundesland_filter:
        query += ' AND p.bundesland = ?'
        params.append(bundesland_filter)

    if pruefer_filter:
        query += ' AND (pr1.name LIKE ? OR pr2.name LIKE ? OR pr3.name LIKE ?)'
        params.extend([f'%{pruefer_filter}%'] * 3)

    if hashtag_filter:
        query += ' AND p.hashtags LIKE ?'
        params.append(f'%{hashtag_filter}%')

    if user_filter:
        query += ' AND u.name LIKE ?'
        params.append(f'%{user_filter}%')

    if datum_von:
        query += ' AND p.datum >= ?'
        params.append(datum_von)

    if datum_bis:
        query += ' AND p.datum <= ?'
        params.append(datum_bis)

    # Sortierung
    valid_sorts = {
        'created_at': 'p.created_at',
        'datum': 'p.datum',
        'bundesland': 'p.bundesland',
        'user_name': 'u.name'
    }

    if sort_by in valid_sorts:
        order_direction = 'DESC' if sort_order == 'desc' else 'ASC'
        query += f' ORDER BY {valid_sorts[sort_by]} {order_direction}'
    else:
        query += ' ORDER BY p.created_at DESC'

    c.execute(query, params)
    protokoll_liste = c.fetchall()

    # Statistiken
    c.execute('SELECT COUNT(*) FROM protokolle')
    gesamt_protokolle = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT user_id) FROM protokolle')
    aktive_autoren = c.fetchone()[0]

    c.execute('SELECT COUNT(DISTINCT bundesland) FROM protokolle')
    bundeslaender_mit_protokollen = c.fetchone()[0]

    # Prüfer und Benutzer für Filter
    c.execute('SELECT DISTINCT name FROM pruefer ORDER BY name')
    alle_pruefer_namen = [row[0] for row in c.fetchall()]

    c.execute('SELECT DISTINCT name FROM users WHERE is_approved = TRUE ORDER BY name')
    alle_benutzer_namen = [row[0] for row in c.fetchall()]

    conn.close()

    return render_template('admin/protokolle.html',
                           protokolle=protokoll_liste,
                           bundeslaender=BUNDESLAENDER,
                           alle_pruefer_namen=alle_pruefer_namen,
                           alle_benutzer_namen=alle_benutzer_namen,
                           predefined_hashtags=PREDEFINED_HASHTAGS,
                           bundesland_filter=bundesland_filter,
                           pruefer_filter=pruefer_filter,
                           hashtag_filter=hashtag_filter,
                           user_filter=user_filter,
                           datum_von=datum_von,
                           datum_bis=datum_bis,
                           sort_by=sort_by,
                           sort_order=sort_order,
                           gesamt_protokolle=gesamt_protokolle,
                           aktive_autoren=aktive_autoren,
                           bundeslaender_mit_protokollen=bundeslaender_mit_protokollen)


@app.route('/admin/logs')
@admin_required
def admin_logs():
    """Admin-Aktivitätslogs anzeigen"""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Logs mit Admin-Namen abrufen
    c.execute('''
              SELECT l.id,
                     l.action_type,
                     l.target_type,
                     l.target_id,
                     l.description,
                     l.admin_notiz,
                     l.created_at,
                     u.name as admin_name
              FROM admin_logs l
                       JOIN users u ON l.admin_user_id = u.id
              ORDER BY l.created_at DESC LIMIT ?
              OFFSET ?
              ''', (per_page, (page - 1) * per_page))

    logs = c.fetchall()

    # Gesamt-Anzahl für Pagination
    c.execute('SELECT COUNT(*) FROM admin_logs')
    total_logs = c.fetchone()[0]

    conn.close()

    return render_template('admin/logs.html',
                           logs=logs,
                           page=page,
                           per_page=per_page,
                           total_logs=total_logs)


@app.route('/api/pruefer/<bundesland>')
@login_required
def api_pruefer(bundesland):
    """API: Prüfer nach Bundesland"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, name FROM pruefer WHERE bundesland = ? ORDER BY name', (bundesland,))
    pruefer = [{'id': row[0], 'name': row[1]} for row in c.fetchall()]
    conn.close()

    return jsonify(pruefer)


@app.route('/erinnerung', methods=['POST'])
@login_required
def erinnerung_erstellen():
    """Erinnerung für Protokoll erstellen"""
    pruefungsdatum = request.form.get('pruefungsdatum')

    if not pruefungsdatum:
        flash('Prüfungsdatum ist erforderlich.', 'error')
        return redirect(url_for('dashboard'))

    # Erste Erinnerung in 2 Tagen
    naechste_erinnerung = datetime.now() + timedelta(days=2)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
              INSERT INTO erinnerungen (user_id, pruefungsdatum, naechste_erinnerung)
              VALUES (?, ?, ?)
              ''', (session['user_id'], pruefungsdatum, naechste_erinnerung))
    conn.commit()
    conn.close()

    flash('Erinnerung wurde eingerichtet. Sie erhalten in 2 Tagen eine E-Mail.', 'success')
    return redirect(url_for('dashboard'))


# Admin-Bereich
@app.route('/admin')
@admin_required
def admin_dashboard():
    """Erweitertes Admin-Dashboard"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Nicht freigeschaltete Benutzer (wie bisher)
    c.execute('''
        SELECT id, name, email, ausbildungsjahr, created_at 
        FROM users 
        WHERE is_verified = TRUE AND is_approved = FALSE
        ORDER BY created_at DESC
        LIMIT 5
    ''')
    pending_users = c.fetchall()

    # Statistiken
    c.execute('SELECT COUNT(*) FROM users WHERE is_approved = TRUE')
    aktive_benutzer = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM protokolle')
    gesamt_protokolle = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM pruefer')
    gesamt_pruefer = c.fetchone()[0]

    c.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE')
    admin_count = c.fetchone()[0]

    # Neueste Aktivitäten
    c.execute('''
        SELECT 'protokoll' as typ, u.name, p.datum, p.created_at
        FROM protokolle p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
        LIMIT 5
    ''')
    neueste_aktivitaeten = c.fetchall()

    conn.close()

    return render_template('admin/dashboard.html',
                         pending_users=pending_users,
                         aktive_benutzer=aktive_benutzer,
                         gesamt_protokolle=gesamt_protokolle,
                         gesamt_pruefer=gesamt_pruefer,
                         admin_count=admin_count,
                         neueste_aktivitaeten=neueste_aktivitaeten)

@app.route('/admin/user/<int:user_id>/approve')
@admin_required
def approve_user(user_id):
    """Benutzer freischalten"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('SELECT name, email FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()

    if user:
        c.execute('UPDATE users SET is_approved = TRUE WHERE id = ?', (user_id,))
        conn.commit()

        # Willkommens-E-Mail senden
        subject = "Account freigeschaltet - Urologie Facharztprüfung"
        body = f"""
        <html>
        <body>
            <h2>Account freigeschaltet!</h2>
            <p>Hallo {user[0]},</p>
            <p>Ihr Account wurde erfolgreich freigeschaltet. Sie können sich jetzt anmelden und die Plattform nutzen.</p>
            <p><a href="{url_for('login', _external=True)}" style="background-color: #007AFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Jetzt anmelden</a></p>
            <p>Viel Erfolg bei der Prüfungsvorbereitung!</p>
        </body>
        </html>
        """

        send_email(user[1], subject, body)
        flash(f'Benutzer {user[0]} wurde freigeschaltet.', 'success')
    else:
        flash('Benutzer nicht gefunden.', 'error')

    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/pruefer')
@admin_required
def admin_pruefer():
    """Prüfer-Verwaltung"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name')
    alle_pruefer = c.fetchall()
    conn.close()

    return render_template('admin/pruefer.html',
                           pruefer=alle_pruefer,
                           bundeslaender=BUNDESLAENDER)


@app.route('/admin/pruefer/neu', methods=['POST'])
@admin_required
def neuer_pruefer():
    """Neuen Prüfer hinzufügen"""
    name = request.form.get('name')
    bundesland = request.form.get('bundesland')

    if not name or not bundesland:
        flash('Name und Bundesland sind erforderlich.', 'error')
        return redirect(url_for('admin_pruefer'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO pruefer (name, bundesland) VALUES (?, ?)', (name, bundesland))
    conn.commit()
    conn.close()

    flash(f'Prüfer {name} wurde hinzugefügt.', 'success')
    return redirect(url_for('admin_pruefer'))


@app.route('/admin/pruefer/<int:pruefer_id>/delete')
@admin_required
def delete_pruefer(pruefer_id):
    """Prüfer löschen"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Prüfen ob Prüfer in Protokollen verwendet wird
    c.execute('''
              SELECT COUNT(*)
              FROM protokolle
              WHERE pruefer1_id = ?
                 OR pruefer2_id = ?
                 OR pruefer3_id = ?
              ''', (pruefer_id, pruefer_id, pruefer_id))

    if c.fetchone()[0] > 0:
        flash('Prüfer kann nicht gelöscht werden, da er in Protokollen verwendet wird.', 'error')
    else:
        c.execute('DELETE FROM pruefer WHERE id = ?', (pruefer_id,))
        conn.commit()
        flash('Prüfer wurde gelöscht.', 'success')

    conn.close()
    return redirect(url_for('admin_pruefer'))


def erinnerungs_service():
    """Service für automatische Erinnerungen"""
    while True:
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()

            # Fällige Erinnerungen finden
            jetzt = datetime.now()
            c.execute('''
                      SELECT e.id, e.user_id, e.anzahl_erinnerungen, u.name, u.email
                      FROM erinnerungen e
                               JOIN users u ON e.user_id = u.id
                      WHERE e.naechste_erinnerung <= ?
                        AND e.protokoll_erstellt = FALSE
                      ''', (jetzt,))

            faellige_erinnerungen = c.fetchall()

            for erinnerung in faellige_erinnerungen:
                erinnerung_id, user_id, anzahl, name, email = erinnerung

                # E-Mail senden
                subject = "Erinnerung: Prüfungsprotokoll erstellen"
                body = f"""
                <html>
                <body>
                    <h2>Erinnerung: Prüfungsprotokoll</h2>
                    <p>Hallo {name},</p>
                    <p>Dies ist eine Erinnerung daran, Ihr Prüfungsprotokoll zu erstellen.</p>
                    <p>Ihre Erfahrungen helfen anderen Studierenden bei der Vorbereitung!</p>
                    <p><a href="{url_for('neues_protokoll', _external=True)}" style="background-color: #007AFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Protokoll erstellen</a></p>
                </body>
                </html>
                """

                if send_email(email, subject, body):
                    # Nächste Erinnerung planen (wöchentlich)
                    naechste_erinnerung = jetzt + timedelta(weeks=1)
                    anzahl += 1

                    c.execute('''
                              UPDATE erinnerungen
                              SET naechste_erinnerung = ?,
                                  anzahl_erinnerungen = ?
                              WHERE id = ?
                              ''', (naechste_erinnerung, anzahl, erinnerung_id))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Erinnerungs-Service Fehler: {e}")

        # 1 Stunde warten
        time.sleep(3600)


@app.route('/datenschutz')
def datenschutz():
    """Datenschutzerklärung"""
    return render_template('datenschutz.html')


@app.route('/impressum')
def impressum():
    """Impressum"""
    return render_template('impressum.html')


if __name__ == '__main__':
    init_db()

    # Erinnerungs-Service in separatem Thread starten
    reminder_thread = threading.Thread(target=erinnerungs_service, daemon=True)
    reminder_thread.start()

    app.run(debug=True, host='0.0.0.0', port=5000)


@app.route('/profil')
@login_required
def profil():
    """Profil anzeigen"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Benutzer-Informationen abrufen
    c.execute('''
              SELECT id, name, email, ausbildungsjahr, created_at, is_admin
              FROM users
              WHERE id = ?
              ''', (session['user_id'],))
    user_data = c.fetchone()

    # Benutzer-Statistiken
    c.execute('SELECT COUNT(*) FROM protokolle WHERE user_id = ?', (session['user_id'],))
    anzahl_protokolle = c.fetchone()[0]

    c.execute('''
              SELECT p.datum, pr.name, p.hashtags
              FROM protokolle p
                       JOIN pruefer pr ON p.pruefer1_id = pr.id
              WHERE p.user_id = ?
              ORDER BY p.created_at DESC LIMIT 5
              ''', (session['user_id'],))
    letzte_protokolle = c.fetchall()

    # Registrierungsdauer berechnen
    if user_data[4]:  # created_at
        try:
            created_date = datetime.strptime(user_data[4], '%Y-%m-%d %H:%M:%S')
            mitglied_seit = (datetime.now() - created_date).days
        except:
            mitglied_seit = 0
    else:
        mitglied_seit = 0

    conn.close()

    user_info = {
        'id': user_data[0],
        'name': user_data[1],
        'email': user_data[2],
        'ausbildungsjahr': user_data[3],
        'created_at': user_data[4],
        'is_admin': user_data[5],
        'anzahl_protokolle': anzahl_protokolle,
        'mitglied_seit': mitglied_seit,
        'letzte_protokolle': letzte_protokolle
    }

    return render_template('profil.html', user=user_info)


@app.route('/profil/bearbeiten', methods=['GET', 'POST'])
@login_required
def profil_bearbeiten():
    """Profil bearbeiten"""
    if request.method == 'GET':
        # Aktuelle Benutzerdaten laden
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
                  SELECT name, email, ausbildungsjahr
                  FROM users
                  WHERE id = ?
                  ''', (session['user_id'],))
        user_data = c.fetchone()
        conn.close()

        if user_data:
            user_info = {
                'name': user_data[0],
                'email': user_data[1],
                'ausbildungsjahr': user_data[2]
            }
            return render_template('profil_bearbeiten.html', user=user_info)
        else:
            flash('Benutzer nicht gefunden.', 'error')
            return redirect(url_for('dashboard'))

    # POST Request - Profil aktualisieren
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    ausbildungsjahr = request.form.get('ausbildungsjahr', '').strip()
    neues_passwort = request.form.get('neues_passwort', '').strip()
    passwort_bestaetigung = request.form.get('passwort_bestaetigung', '').strip()
    aktuelles_passwort = request.form.get('aktuelles_passwort', '').strip()

    # Validierung
    errors = []

    if not name:
        errors.append('Name ist erforderlich.')
    elif len(name) < 2:
        errors.append('Name muss mindestens 2 Zeichen lang sein.')

    if not email:
        errors.append('E-Mail ist erforderlich.')
    elif not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        errors.append('Ungültige E-Mail-Adresse.')

    if not ausbildungsjahr:
        errors.append('Ausbildungsjahr ist erforderlich.')
    else:
        try:
            ausbildungsjahr_int = int(ausbildungsjahr)
            if ausbildungsjahr_int < 1 or ausbildungsjahr_int > 6:
                errors.append('Ausbildungsjahr muss zwischen 1 und 6 liegen.')
        except ValueError:
            errors.append('Ungültiges Ausbildungsjahr.')

    # Passwort-Validierung (nur wenn neues Passwort angegeben)
    if neues_passwort:
        if len(neues_passwort) < 6:
            errors.append('Neues Passwort muss mindestens 6 Zeichen lang sein.')
        elif neues_passwort != passwort_bestaetigung:
            errors.append('Passwort-Bestätigung stimmt nicht überein.')

        # Aktuelles Passwort prüfen
        if not aktuelles_passwort:
            errors.append('Aktuelles Passwort ist erforderlich um das Passwort zu ändern.')
        else:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],))
            current_hash = c.fetchone()
            conn.close()

            if not current_hash or not check_password_hash(current_hash[0], aktuelles_passwort):
                errors.append('Aktuelles Passwort ist falsch.')

    # E-Mail-Eindeutigkeit prüfen (außer eigene E-Mail)
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users WHERE email = ? AND id != ?', (email, session['user_id']))
    if c.fetchone()[0] > 0:
        errors.append('Diese E-Mail-Adresse wird bereits verwendet.')
    conn.close()

    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('profil_bearbeiten.html', user={
            'name': name,
            'email': email,
            'ausbildungsjahr': ausbildungsjahr
        })

    # Daten aktualisieren
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    try:
        if neues_passwort:
            # Mit Passwort-Update
            password_hash = generate_password_hash(neues_passwort)
            c.execute('''
                      UPDATE users
                      SET name            = ?,
                          email           = ?,
                          ausbildungsjahr = ?,
                          password_hash   = ?
                      WHERE id = ?
                      ''', (name, email, int(ausbildungsjahr), password_hash, session['user_id']))
            flash('Profil und Passwort erfolgreich aktualisiert!', 'success')
        else:
            # Ohne Passwort-Update
            c.execute('''
                      UPDATE users
                      SET name            = ?,
                          email           = ?,
                          ausbildungsjahr = ?
                      WHERE id = ?
                      ''', (name, email, int(ausbildungsjahr), session['user_id']))
            flash('Profil erfolgreich aktualisiert!', 'success')

        # Session-Name aktualisieren
        session['user_name'] = name

        conn.commit()

    except Exception as e:
        conn.rollback()
        flash('Fehler beim Aktualisieren des Profils.', 'error')
        print(f"Profil-Update Fehler: {e}")

    finally:
        conn.close()

    return redirect(url_for('profil'))


@app.route('/profil/loeschen', methods=['GET', 'POST'])
@login_required
def profil_loeschen():
    """Profil löschen"""
    if request.method == 'GET':
        # Bestätigungsseite anzeigen
        return render_template('profil_loeschen.html')

    # POST Request - Profil löschen
    passwort = request.form.get('passwort', '').strip()
    bestaetigung = request.form.get('bestaetigung', '').strip()

    # Validierung
    if not passwort:
        flash('Passwort ist erforderlich.', 'error')
        return render_template('profil_loeschen.html')

    if bestaetigung != 'LÖSCHEN':
        flash('Bitte geben Sie "LÖSCHEN" zur Bestätigung ein.', 'error')
        return render_template('profil_loeschen.html')

    # Passwort prüfen
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT password_hash, name FROM users WHERE id = ?', (session['user_id'],))
    user_data = c.fetchone()

    if not user_data or not check_password_hash(user_data[0], passwort):
        flash('Falsches Passwort.', 'error')
        conn.close()
        return render_template('profil_loeschen.html')

    username = user_data[1]

    try:
        # Benutzer und zugehörige Daten löschen
        # 1. Erinnerungen löschen
        c.execute('DELETE FROM erinnerungen WHERE user_id = ?', (session['user_id'],))

        # 2. Protokolle löschen
        c.execute('DELETE FROM protokolle WHERE user_id = ?', (session['user_id'],))

        # 3. Benutzer löschen
        c.execute('DELETE FROM users WHERE id = ?', (session['user_id'],))

        conn.commit()

        # Session beenden
        session.clear()

        flash(f'Profil von {username} wurde erfolgreich gelöscht.', 'info')

    except Exception as e:
        conn.rollback()
        flash('Fehler beim Löschen des Profils.', 'error')
        print(f"Profil-Löschung Fehler: {e}")

    finally:
        conn.close()

    return redirect(url_for('index'))


@app.route('/profil/export')
@login_required
def profil_export():
    """Profil-Daten als JSON exportieren (DSGVO-Compliance)"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Benutzer-Daten
    c.execute('''
              SELECT name, email, ausbildungsjahr, created_at, is_verified, is_approved
              FROM users
              WHERE id = ?
              ''', (session['user_id'],))
    user_data = c.fetchone()

    # Protokolle des Benutzers
    c.execute('''
              SELECT p.datum,
                     p.bundesland,
                     pr1.name,
                     pr2.name,
                     pr3.name,
                     p.inhalt,
                     p.hashtags,
                     p.kommentar,
                     p.created_at
              FROM protokolle p
                       JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
                       JOIN pruefer pr2 ON p.pruefer2_id = pr2.id
                       JOIN pruefer pr3 ON p.pruefer3_id = pr3.id
              WHERE p.user_id = ?
              ORDER BY p.created_at DESC
              ''', (session['user_id'],))
    protokolle_data = c.fetchall()

    # Erinnerungen
    c.execute('''
              SELECT pruefungsdatum,
                     naechste_erinnerung,
                     anzahl_erinnerungen,
                     protokoll_erstellt,
                     created_at
              FROM erinnerungen
              WHERE user_id = ?
              ''', (session['user_id'],))
    erinnerungen_data = c.fetchall()

    conn.close()

    # Export-Daten zusammenstellen
    export_data = {
        'export_info': {
            'datum': datetime.now().isoformat(),
            'typ': 'DSGVO-konformer Datenexport',
            'benutzer_id': session['user_id']
        },
        'benutzer_daten': {
            'name': user_data[0] if user_data else None,
            'email': user_data[1] if user_data else None,
            'ausbildungsjahr': user_data[2] if user_data else None,
            'registriert_am': user_data[3] if user_data else None,
            'email_verifiziert': user_data[4] if user_data else None,
            'account_freigeschaltet': user_data[5] if user_data else None
        },
        'protokolle': [
            {
                'datum': protokoll[0],
                'bundesland': protokoll[1],
                'pruefer1': protokoll[2],
                'pruefer2': protokoll[3],
                'pruefer3': protokoll[4],
                'inhalt': protokoll[5],
                'hashtags': protokoll[6],
                'kommentar': protokoll[7],
                'erstellt_am': protokoll[8]
            }
            for protokoll in protokolle_data
        ],
        'erinnerungen': [
            {
                'pruefungsdatum': erinnerung[0],
                'naechste_erinnerung': erinnerung[1],
                'anzahl_erinnerungen': erinnerung[2],
                'protokoll_erstellt': erinnerung[3],
                'erstellt_am': erinnerung[4]
            }
            for erinnerung in erinnerungen_data
        ]
    }

    # Als JSON-Response zurückgeben
    response = app.response_class(
        response=json.dumps(export_data, indent=2, ensure_ascii=False),
        status=200,
        mimetype='application/json'
    )

    # Download-Header setzen
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'urologie_profil_export_{timestamp}.json'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    return response


# JSON Import für Flask Response
import json