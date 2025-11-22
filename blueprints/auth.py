from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
from utils import send_email, login_required
import secrets
import re
from datetime import datetime

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
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
        db = get_db()
        if db.execute('SELECT COUNT(*) FROM users WHERE email = ?', (email,)).fetchone()[0] > 0:
            flash('E-Mail-Adresse bereits registriert.', 'error')
            return render_template('register.html')

        # Benutzer erstellen
        password_hash = generate_password_hash(password)
        verification_token = secrets.token_urlsafe(32)

        db.execute('''
            INSERT INTO users (name, email, password_hash, ausbildungsjahr, verification_token)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, password_hash, ausbildungsjahr, verification_token))
        db.commit()

        # Verifizierungs-E-Mail senden
        verification_link = url_for('auth.verify_email', token=verification_token, _external=True)
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

        return redirect(url_for('auth.login'))

    return render_template('register.html')

@bp.route('/verify/<token>')
def verify_email(token):
    """E-Mail-Verifizierung"""
    db = get_db()
    user = db.execute('SELECT id, name FROM users WHERE verification_token = ? AND is_verified = FALSE', (token,)).fetchone()

    if user:
        db.execute('UPDATE users SET is_verified = TRUE, verification_token = NULL WHERE id = ?', (user['id'],))
        db.commit()
        flash('E-Mail erfolgreich verifiziert! Ihr Account wird nun von einem Administrator geprüft.', 'success')
    else:
        flash('Ungültiger oder bereits verwendeter Verifizierungslink.', 'error')

    return redirect(url_for('auth.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Benutzeranmeldung"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('E-Mail und Passwort sind erforderlich.', 'error')
            return render_template('login.html')

        db = get_db()
        user = db.execute('''
            SELECT id, name, password_hash, is_verified, is_approved, is_admin
            FROM users
            WHERE email = ?
        ''', (email,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # E-Mail-Verifizierung deaktiviert (auf Kundenwunsch)
            # if not user['is_verified']:
            #     flash('Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.', 'error')
            #     return render_template('login.html')

            if not user['is_approved']:
                flash('Ihr Account wurde noch nicht von einem Administrator freigeschaltet.', 'error')
                return render_template('login.html')

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']

            flash(f'Willkommen zurück, {user["name"]}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Ungültige Anmeldedaten.', 'error')

    return render_template('login.html')

@bp.route('/logout')
def logout():
    """Benutzerabmeldung"""
    session.clear()
    flash('Sie wurden erfolgreich abgemeldet.', 'info')
    return redirect(url_for('main.index'))

@bp.route('/profil')
@login_required
def profil():
    """Profil anzeigen"""
    db = get_db()
    
    # Benutzer-Informationen abrufen
    user_data = db.execute('''
        SELECT id, name, email, ausbildungsjahr, created_at, is_admin
        FROM users
        WHERE id = ?
    ''', (session['user_id'],)).fetchone()

    # Benutzer-Statistiken
    anzahl_protokolle = db.execute('SELECT COUNT(*) FROM protokolle WHERE user_id = ?', (session['user_id'],)).fetchone()[0]

    letzte_protokolle = db.execute('''
        SELECT p.datum, pr.name, p.hashtags
        FROM protokolle p
        JOIN pruefer pr ON p.pruefer1_id = pr.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC LIMIT 5
    ''', (session['user_id'],)).fetchall()

    # Registrierungsdauer berechnen
    if user_data['created_at']:
        try:
            created_date = datetime.strptime(user_data['created_at'], '%Y-%m-%d %H:%M:%S')
            mitglied_seit = (datetime.now() - created_date).days
        except:
            mitglied_seit = 0
    else:
        mitglied_seit = 0

    user_info = {
        'id': user_data['id'],
        'name': user_data['name'],
        'email': user_data['email'],
        'ausbildungsjahr': user_data['ausbildungsjahr'],
        'created_at': user_data['created_at'],
        'is_admin': user_data['is_admin'],
        'anzahl_protokolle': anzahl_protokolle,
        'mitglied_seit': mitglied_seit,
        'letzte_protokolle': letzte_protokolle
    }

    return render_template('profil.html', user=user_info)

@bp.route('/profil/bearbeiten', methods=['GET', 'POST'])
@login_required
def profil_bearbeiten():
    """Profil bearbeiten"""
    db = get_db()
    
    if request.method == 'GET':
        # Aktuelle Benutzerdaten laden
        user_data = db.execute('''
            SELECT name, email, ausbildungsjahr
            FROM users
            WHERE id = ?
        ''', (session['user_id'],)).fetchone()

        if user_data:
            user_info = {
                'name': user_data['name'],
                'email': user_data['email'],
                'ausbildungsjahr': user_data['ausbildungsjahr']
            }
            return render_template('profil_bearbeiten.html', user=user_info)
        else:
            flash('Benutzer nicht gefunden.', 'error')
            return redirect(url_for('main.dashboard'))

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
            current_hash = db.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],)).fetchone()

            if not current_hash or not check_password_hash(current_hash['password_hash'], aktuelles_passwort):
                errors.append('Aktuelles Passwort ist falsch.')

    # E-Mail-Eindeutigkeit prüfen (außer eigene E-Mail)
    if db.execute('SELECT COUNT(*) FROM users WHERE email = ? AND id != ?', (email, session['user_id'])).fetchone()[0] > 0:
        errors.append('Diese E-Mail-Adresse wird bereits verwendet.')

    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('profil_bearbeiten.html', user={
            'name': name,
            'email': email,
            'ausbildungsjahr': ausbildungsjahr
        })

    try:
        if neues_passwort:
            # Mit Passwort-Update
            password_hash = generate_password_hash(neues_passwort)
            db.execute('''
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
            db.execute('''
                UPDATE users
                SET name            = ?,
                    email           = ?,
                    ausbildungsjahr = ?
                WHERE id = ?
            ''', (name, email, int(ausbildungsjahr), session['user_id']))
            flash('Profil erfolgreich aktualisiert!', 'success')

        # Session-Name aktualisieren
        session['user_name'] = name

        db.commit()

    except Exception as e:
        db.rollback()
        flash('Fehler beim Aktualisieren des Profils.', 'error')
        print(f"Profil-Update Fehler: {e}")

    return redirect(url_for('auth.profil'))

@bp.route('/profil/loeschen', methods=['GET', 'POST'])
@login_required
def profil_loeschen():
    """Profil löschen"""
    if request.method == 'GET':
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

    db = get_db()
    user_data = db.execute('SELECT password_hash, name FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if not user_data or not check_password_hash(user_data['password_hash'], passwort):
        flash('Falsches Passwort.', 'error')
        return render_template('profil_loeschen.html')

    username = user_data['name']

    try:
        # Benutzer und zugehörige Daten löschen
        db.execute('DELETE FROM erinnerungen WHERE user_id = ?', (session['user_id'],))
        db.execute('DELETE FROM protokolle WHERE user_id = ?', (session['user_id'],))
        db.execute('DELETE FROM users WHERE id = ?', (session['user_id'],))

        db.commit()

        # Session beenden
        session.clear()

        flash(f'Profil von {username} wurde erfolgreich gelöscht.', 'info')

    except Exception as e:
        db.rollback()
        flash('Fehler beim Löschen des Profils.', 'error')
        print(f"Profil-Löschung Fehler: {e}")

    return redirect(url_for('main.index'))
