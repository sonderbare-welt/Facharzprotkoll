from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils import admin_required, send_email
from datetime import datetime

bp = Blueprint('admin', __name__)

# Bundesländer
BUNDESLAENDER = [
    'Baden-Württemberg', 'Bayern', 'Berlin', 'Brandenburg', 'Bremen',
    'Hamburg', 'Hessen', 'Mecklenburg-Vorpommern', 'Niedersachsen',
    'Nordrhein', 'Rheinland-Pfalz', 'Saarland', 'Sachsen',
    'Sachsen-Anhalt', 'Schleswig-Holstein', 'Thüringen', 'Westfalen-Lippe'
]

# Vordefinierte Hashtags
PREDEFINED_HASHTAGS = [
    '#Andrologie', '#Onkologie', '#Kinderurologie', '#Steinleiden', '#Harninkontinenz',
    '#Neurourologie', '#Transplantation', '#Endourologie', '#Infektiologie', '#Traumatologie',
    '#rekonstruktive-Urologie', '#Labordiagnostik', '#Bildgebung', '#Notfälle',
    '#Prostata', '#Hoden', '#Niere', '#Blase', '#Urethra', '#Anatomie', '#Physiologie',
    '#Prostatakarzinom','#Nierenzelkarzinom','#Urothelkarzinom','Hodentumor','#Peniskarzinom'
]

@bp.route('/admin')
@admin_required
def admin_dashboard():
    """Erweitertes Admin-Dashboard"""
    db = get_db()

    # Nicht freigeschaltete Benutzer
    pending_users = db.execute('''
        SELECT id, name, email, ausbildungsjahr, created_at 
        FROM users 
        WHERE is_verified = TRUE AND is_approved = FALSE
        ORDER BY created_at DESC
        LIMIT 5
    ''').fetchall()

    # Statistiken
    aktive_benutzer = db.execute('SELECT COUNT(*) FROM users WHERE is_approved = TRUE').fetchone()[0]
    gesamt_protokolle = db.execute('SELECT COUNT(*) FROM protokolle').fetchone()[0]
    gesamt_pruefer = db.execute('SELECT COUNT(*) FROM pruefer').fetchone()[0]
    admin_count = db.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE').fetchone()[0]

    # Neueste Aktivitäten
    neueste_aktivitaeten = db.execute('''
        SELECT 'protokoll' as typ, u.name, p.datum, p.created_at
        FROM protokolle p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
        LIMIT 5
    ''').fetchall()

    return render_template('admin/dashboard.html',
                         pending_users=pending_users,
                         aktive_benutzer=aktive_benutzer,
                         gesamt_protokolle=gesamt_protokolle,
                         gesamt_pruefer=gesamt_pruefer,
                         admin_count=admin_count,
                         neueste_aktivitaeten=neueste_aktivitaeten)

@bp.route('/admin/benutzer')
@admin_required
def admin_benutzer():
    """Benutzerverwaltung"""
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')

    db = get_db()

    base_query = '''
        SELECT u.id, u.name, u.email, u.ausbildungsjahr, u.created_at,
               u.is_verified, u.is_approved, u.is_admin,
               COUNT(p.id) as protokolle_count,
               MAX(p.created_at) as letztes_protokoll
        FROM users u
        LEFT JOIN protokolle p ON u.id = p.user_id
        WHERE 1 = 1
    '''

    params = []

    if status_filter == 'pending':
        base_query += ' AND u.is_verified = TRUE AND u.is_approved = FALSE'
    elif status_filter == 'approved':
        base_query += ' AND u.is_approved = TRUE AND u.is_admin = FALSE'
    elif status_filter == 'admin':
        base_query += ' AND u.is_admin = TRUE'

    if search_query:
        base_query += ' AND (u.name LIKE ? OR u.email LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    base_query += ' GROUP BY u.id, u.name, u.email, u.ausbildungsjahr, u.created_at, u.is_verified, u.is_approved, u.is_admin'

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

    alle_benutzer = db.execute(base_query, params).fetchall()

    # Statistiken
    wartende_benutzer = db.execute('SELECT COUNT(*) FROM users WHERE is_verified = TRUE AND is_approved = FALSE').fetchone()[0]
    aktive_benutzer = db.execute('SELECT COUNT(*) FROM users WHERE is_approved = TRUE AND is_admin = FALSE').fetchone()[0]
    admin_benutzer = db.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE').fetchone()[0]
    gesamt_benutzer = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]

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

@bp.route('/admin/user/<int:user_id>/approve')
@admin_required
def approve_user(user_id):
    """Benutzer freischalten (Manuelle Verifizierung)"""
    db = get_db()
    user = db.execute('SELECT name, email FROM users WHERE id = ?', (user_id,)).fetchone()

    if user:
        db.execute('UPDATE users SET is_approved = TRUE WHERE id = ?', (user_id,))
        db.commit()

        subject = "Account freigeschaltet - Urologie Facharztprüfung"
        body = f"""
        <html>
        <body>
            <h2>Account freigeschaltet!</h2>
            <p>Hallo {user['name']},</p>
            <p>Ihr Account wurde erfolgreich freigeschaltet. Sie können sich jetzt anmelden und die Plattform nutzen.</p>
            <p><a href="{url_for('auth.login', _external=True)}" style="background-color: #007AFF; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Jetzt anmelden</a></p>
            <p>Viel Erfolg bei der Prüfungsvorbereitung!</p>
        </body>
        </html>
        """
        send_email(user['email'], subject, body)
        flash(f'Benutzer {user["name"]} wurde freigeschaltet.', 'success')
    else:
        flash('Benutzer nicht gefunden.', 'error')

    return redirect(url_for('admin.admin_dashboard'))

@bp.route('/admin/benutzer/<int:user_id>/admin-status', methods=['POST'])
@admin_required
def toggle_admin_status(user_id):
    """Admin-Status eines Benutzers ändern"""
    action = request.form.get('action')

    if user_id == session['user_id']:
        flash('Sie können Ihren eigenen Admin-Status nicht ändern.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    db = get_db()
    user_data = db.execute('SELECT id, name, email, is_admin, is_approved FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user_data:
        flash('Benutzer nicht gefunden.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    try:
        if action == 'promote':
            if user_data['is_admin']:
                flash(f'{user_data["name"]} ist bereits ein Administrator.', 'warning')
            elif not user_data['is_approved']:
                flash('Benutzer muss erst freigeschaltet werden, bevor er zum Admin ernannt werden kann.', 'error')
            else:
                db.execute('UPDATE users SET is_admin = TRUE WHERE id = ?', (user_id,))
                db.commit()
                
                # Email notification logic here (simplified for brevity)
                flash(f'{user_data["name"]} wurde erfolgreich zum Administrator ernannt.', 'success')

        elif action == 'demote':
            if not user_data['is_admin']:
                flash(f'{user_data["name"]} ist kein Administrator.', 'warning')
            else:
                andere_admins = db.execute('SELECT COUNT(*) FROM users WHERE is_admin = TRUE AND id != ?', (user_id,)).fetchone()[0]
                if andere_admins == 0:
                    flash('Sie können den letzten Administrator nicht degradieren.', 'error')
                else:
                    db.execute('UPDATE users SET is_admin = FALSE WHERE id = ?', (user_id,))
                    db.commit()
                    flash(f'Administrator-Status von {user_data["name"]} wurde entfernt.', 'success')
        else:
            flash('Ungültige Aktion.', 'error')

    except Exception as e:
        db.rollback()
        flash('Fehler beim Ändern des Admin-Status.', 'error')
        print(f"Admin-Status Änderung Fehler: {e}")

    return redirect(url_for('admin.admin_benutzer'))

@bp.route('/admin/benutzer/<int:user_id>/details')
@admin_required
def benutzer_details(user_id):
    """Benutzer-Details anzeigen"""
    db = get_db()
    user_data = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user_data:
        flash('Benutzer nicht gefunden.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    anzahl_protokolle = db.execute('SELECT COUNT(*) FROM protokolle WHERE user_id = ?', (user_id,)).fetchone()[0]
    protokoll_zeitraum = db.execute('SELECT MIN(created_at), MAX(created_at) FROM protokolle WHERE user_id = ?', (user_id,)).fetchone()
    
    letzte_protokolle = db.execute('''
        SELECT p.datum, p.bundesland, pr.name, p.hashtags, p.created_at
        FROM protokolle p
        JOIN pruefer pr ON p.pruefer1_id = pr.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC LIMIT 10
    ''', (user_id,)).fetchall()

    erinnerungen = db.execute('SELECT * FROM erinnerungen WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()

    # Hashtag logic (simplified)
    hashtag_results = db.execute('SELECT hashtags FROM protokolle WHERE user_id = ? AND hashtags IS NOT NULL', (user_id,)).fetchall()
    hashtag_counter = {}
    for result in hashtag_results:
        if result['hashtags']:
            for hashtag in result['hashtags'].split():
                hashtag = hashtag.strip()
                if hashtag:
                    hashtag_counter[hashtag] = hashtag_counter.get(hashtag, 0) + 1
    top_hashtags = sorted(hashtag_counter.items(), key=lambda x: x[1], reverse=True)[:10]

    user_info = dict(user_data)
    user_info.update({
        'anzahl_protokolle': anzahl_protokolle,
        'protokoll_zeitraum': protokoll_zeitraum,
        'letzte_protokolle': letzte_protokolle,
        'erinnerungen': erinnerungen,
        'top_hashtags': top_hashtags
    })

    return render_template('admin/benutzer_details.html', user=user_info)

@bp.route('/admin/benutzer/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    """Benutzer sperren/entsperren"""
    action = request.form.get('action')
    reason = request.form.get('reason', '').strip()

    if user_id == session['user_id']:
        flash('Sie können sich nicht selbst sperren.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    db = get_db()
    user_data = db.execute('SELECT id, name, email, is_approved FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user_data:
        flash('Benutzer nicht gefunden.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    try:
        if action == 'suspend':
            if not user_data['is_approved']:
                flash(f'{user_data["name"]} ist bereits gesperrt.', 'warning')
            else:
                db.execute('UPDATE users SET is_approved = FALSE WHERE id = ?', (user_id,))
                db.commit()
                # Email notification logic here
                flash(f'{user_data["name"]} wurde gesperrt.', 'success')

        elif action == 'unsuspend':
            if user_data['is_approved']:
                flash(f'{user_data["name"]} ist nicht gesperrt.', 'warning')
            else:
                db.execute('UPDATE users SET is_approved = TRUE WHERE id = ?', (user_id,))
                db.commit()
                # Email notification logic here
                flash(f'{user_data["name"]} wurde entsperrt.', 'success')
        else:
            flash('Ungültige Aktion.', 'error')

    except Exception as e:
        db.rollback()
        flash('Fehler beim Ändern des Benutzer-Status.', 'error')
        print(f"Benutzer-Status Änderung Fehler: {e}")

    return redirect(url_for('admin.admin_benutzer'))

@bp.route('/admin/benutzer/bulk-actions', methods=['POST'])
@admin_required
def benutzer_bulk_actions():
    """Bulk-Aktionen für Benutzer"""
    action = request.form.get('action')
    user_ids = request.form.getlist('user_ids')

    if not user_ids:
        flash('Keine Benutzer ausgewählt.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    user_ids = [uid for uid in user_ids if int(uid) != session['user_id']]

    if not user_ids:
        flash('Sie können keine Bulk-Aktionen auf sich selbst anwenden.', 'error')
        return redirect(url_for('admin.admin_benutzer'))

    db = get_db()
    try:
        placeholders = ','.join(['?' for _ in user_ids])
        if action == 'approve':
            db.execute(f'UPDATE users SET is_approved = TRUE WHERE id IN ({placeholders}) AND is_verified = TRUE', user_ids)
            db.commit()
            flash(f'{len(user_ids)} Benutzer wurden freigeschaltet.', 'success')
        elif action == 'suspend':
            db.execute(f'UPDATE users SET is_approved = FALSE WHERE id IN ({placeholders})', user_ids)
            db.commit()
            flash(f'{len(user_ids)} Benutzer wurden gesperrt.', 'success')
        # ... other actions ...
    except Exception as e:
        db.rollback()
        flash('Fehler bei Bulk-Aktion.', 'error')

    return redirect(url_for('admin.admin_benutzer'))

@bp.route('/admin/pruefer')
@admin_required
def admin_pruefer():
    """Prüfer-Verwaltung"""
    db = get_db()
    alle_pruefer = db.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name').fetchall()
    return render_template('admin/pruefer.html', pruefer=alle_pruefer, bundeslaender=BUNDESLAENDER)

@bp.route('/admin/pruefer/neu', methods=['POST'])
@admin_required
def neuer_pruefer():
    """Neuen Prüfer hinzufügen"""
    name = request.form.get('name')
    bundesland = request.form.get('bundesland')

    if not name or not bundesland:
        flash('Name und Bundesland sind erforderlich.', 'error')
        return redirect(url_for('admin.admin_pruefer'))

    db = get_db()
    db.execute('INSERT INTO pruefer (name, bundesland) VALUES (?, ?)', (name, bundesland))
    db.commit()

    flash(f'Prüfer {name} wurde hinzugefügt.', 'success')
    return redirect(url_for('admin.admin_pruefer'))

@bp.route('/admin/pruefer/<int:pruefer_id>/delete')
@admin_required
def delete_pruefer(pruefer_id):
    """Prüfer löschen"""
    db = get_db()
    
    count = db.execute('''
        SELECT COUNT(*) FROM protokolle 
        WHERE pruefer1_id = ? OR pruefer2_id = ? OR pruefer3_id = ?
    ''', (pruefer_id, pruefer_id, pruefer_id)).fetchone()[0]

    if count > 0:
        flash('Prüfer kann nicht gelöscht werden, da er in Protokollen verwendet wird.', 'error')
    else:
        db.execute('DELETE FROM pruefer WHERE id = ?', (pruefer_id,))
        db.commit()
        flash('Prüfer wurde gelöscht.', 'success')

    return redirect(url_for('admin.admin_pruefer'))

@bp.route('/admin/pruefer/<int:pruefer_id>/bearbeiten', methods=['GET', 'POST'])
@admin_required
def admin_pruefer_bearbeiten(pruefer_id):
    """Prüfer bearbeiten"""
    db = get_db()
    
    if request.method == 'POST':
        name = request.form.get('name')
        bundesland = request.form.get('bundesland')
        
        if not name or not bundesland:
            flash('Name und Bundesland sind erforderlich.', 'error')
        else:
            db.execute('UPDATE pruefer SET name = ?, bundesland = ? WHERE id = ?', (name, bundesland, pruefer_id))
            db.commit()
            flash('Prüfer erfolgreich aktualisiert.', 'success')
            return redirect(url_for('admin.admin_pruefer'))
    
    pruefer = db.execute('SELECT id, name, bundesland FROM pruefer WHERE id = ?', (pruefer_id,)).fetchone()
    if not pruefer:
        flash('Prüfer nicht gefunden.', 'error')
        return redirect(url_for('admin.admin_pruefer'))
        
    return render_template('admin/pruefer_bearbeiten.html', pruefer=pruefer, bundeslaender=BUNDESLAENDER)

@bp.route('/admin/protokolle')
@admin_required
def admin_protokolle():
    """Admin-Übersicht aller Protokolle"""
    db = get_db()

    # Filter Parameter
    user_filter = request.args.get('user', '')
    bundesland_filter = request.args.get('bundesland', '')
    pruefer_filter = request.args.get('pruefer', '')
    hashtag_filter = request.args.get('hashtag', '')
    datum_von = request.args.get('datum_von', '')
    datum_bis = request.args.get('datum_bis', '')
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')

    # Query Bauen
    query = '''
        SELECT p.id, p.datum, p.bundesland, 
               pr1.name as pruefer1, pr2.name as pruefer2, pr3.name as pruefer3,
               p.hashtags, p.inhalt, p.kommentar, u.name as user_name, p.created_at, p.user_id
        FROM protokolle p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
        LEFT JOIN pruefer pr2 ON p.pruefer2_id = pr2.id
        LEFT JOIN pruefer pr3 ON p.pruefer3_id = pr3.id
        WHERE 1=1
    '''
    params = []

    if user_filter:
        query += ' AND u.name LIKE ?'
        params.append(f'%{user_filter}%')
    if bundesland_filter:
        query += ' AND p.bundesland = ?'
        params.append(bundesland_filter)
    if pruefer_filter:
        query += ' AND (pr1.name LIKE ? OR pr2.name LIKE ? OR pr3.name LIKE ?)'
        params.extend([f'%{pruefer_filter}%'] * 3)
    if hashtag_filter:
        query += ' AND p.hashtags LIKE ?'
        params.append(f'%{hashtag_filter}%')
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
    sort_col = valid_sorts.get(sort_by, 'p.created_at')
    direction = 'ASC' if sort_order == 'asc' else 'DESC'
    query += f' ORDER BY {sort_col} {direction}'

    protokolle = db.execute(query, params).fetchall()

    # Statistiken
    gesamt_protokolle = db.execute('SELECT COUNT(*) FROM protokolle').fetchone()[0]
    aktive_autoren = db.execute('SELECT COUNT(DISTINCT user_id) FROM protokolle').fetchone()[0]
    bundeslaender_mit_protokollen = db.execute('SELECT COUNT(DISTINCT bundesland) FROM protokolle').fetchone()[0]
    
    # Listen für Filter
    alle_benutzer_namen = [r[0] for r in db.execute('SELECT DISTINCT name FROM users ORDER BY name').fetchall()]
    alle_pruefer_namen = [r[0] for r in db.execute('SELECT DISTINCT name FROM pruefer ORDER BY name').fetchall()]

    return render_template('admin/protokolle.html',
                           protokolle=protokolle,
                           gesamt_protokolle=gesamt_protokolle,
                           aktive_autoren=aktive_autoren,
                           bundeslaender_mit_protokollen=bundeslaender_mit_protokollen,
                           alle_benutzer_namen=alle_benutzer_namen,
                           alle_pruefer_namen=alle_pruefer_namen,
                           bundeslaender=BUNDESLAENDER,
                           predefined_hashtags=PREDEFINED_HASHTAGS,
                           user_filter=user_filter,
                           bundesland_filter=bundesland_filter,
                           pruefer_filter=pruefer_filter,
                           hashtag_filter=hashtag_filter,
                           datum_von=datum_von,
                           datum_bis=datum_bis,
                           sort_by=sort_by,
                           sort_order=sort_order)

@bp.route('/admin/protokoll/<int:protokoll_id>')
@admin_required
def admin_protokoll_details(protokoll_id):
    """Admin-Ansicht für Protokoll-Details"""
    db = get_db()
    row = db.execute('''
        SELECT p.*, u.name as user_name, u.email as user_email,
               pr1.name as pr1_name, pr1.bundesland as pr1_land,
               pr2.name as pr2_name, pr2.bundesland as pr2_land,
               pr3.name as pr3_name, pr3.bundesland as pr3_land
        FROM protokolle p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
        LEFT JOIN pruefer pr2 ON p.pruefer2_id = pr2.id
        LEFT JOIN pruefer pr3 ON p.pruefer3_id = pr3.id
        WHERE p.id = ?
    ''', (protokoll_id,)).fetchone()

    if not row:
        flash('Protokoll nicht gefunden', 'error')
        return redirect(url_for('admin.admin_protokolle'))

    # Strukturieren für Template
    protokoll = {
        'id': row['id'],
        'datum': row['datum'],
        'bundesland': row['bundesland'],
        'inhalt': row['inhalt'],
        'kommentar': row['kommentar'],
        'hashtags': row['hashtags'],
        'created_at': row['created_at'],
        'user': {'id': row['user_id'], 'name': row['user_name'], 'email': row['user_email']},
        'pruefer1': {'name': row['pr1_name'], 'bundesland': row['pr1_land']},
        'pruefer2': {'name': row['pr2_name'], 'bundesland': row['pr2_land']},
        'pruefer3': {'name': row['pr3_name'], 'bundesland': row['pr3_land']},
    }

    return render_template('admin/protokoll_details.html', protokoll=protokoll)

@bp.route('/admin/protokoll/<int:protokoll_id>/bearbeiten', methods=['GET', 'POST'])
@admin_required
def admin_protokoll_bearbeiten(protokoll_id):
    """Protokoll als Admin bearbeiten"""
    db = get_db()
    
    if request.method == 'POST':
        inhalt = request.form.get('inhalt')
        kommentar = request.form.get('kommentar')
        hashtags = request.form.get('hashtags')
        datum = request.form.get('datum')
        bundesland = request.form.get('bundesland')
        pruefer1 = request.form.get('pruefer1')
        pruefer2 = request.form.get('pruefer2')
        pruefer3 = request.form.get('pruefer3')
        admin_notiz = request.form.get('admin_notiz')
        
        db.execute('''
            UPDATE protokolle 
            SET inhalt = ?, kommentar = ?, hashtags = ?, datum = ?, bundesland = ?,
                pruefer1_id = ?, pruefer2_id = ?, pruefer3_id = ?
            WHERE id = ?
        ''', (inhalt, kommentar, hashtags, datum, bundesland, pruefer1, pruefer2, pruefer3, protokoll_id))
        db.commit()
        
        # Log action
        db.execute('INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)',
                   (session['user_id'], 'PROTOKOLL_BEARBEITET', f'Protokoll {protokoll_id} bearbeitet. Notiz: {admin_notiz if admin_notiz else "Keine"}'))
        db.commit()

        # Email an User senden, wenn Notiz vorhanden
        if admin_notiz:
            # User Email laden
            user = db.execute('''
                SELECT u.email, u.name 
                FROM users u 
                JOIN protokolle p ON p.user_id = u.id 
                WHERE p.id = ?
            ''', (protokoll_id,)).fetchone()
            
            if user:
                subject = f"Änderung an Ihrem Gedächtnisprotokoll #{protokoll_id}"
                body = f"""
                <html>
                <body>
                    <h2>Hallo {user['name']},</h2>
                    <p>Ein Administrator hat Ihr Gedächtnisprotokoll #{protokoll_id} bearbeitet.</p>
                    <p><strong>Nachricht des Administrators:</strong></p>
                    <blockquote style="background: #f9f9f9; border-left: 10px solid #ccc; margin: 1.5em 10px; padding: 0.5em 10px;">
                        {admin_notiz}
                    </blockquote>
                    <p>Sie können das aktualisierte Protokoll in Ihrem Dashboard einsehen.</p>
                </body>
                </html>
                """
                send_email(user['email'], subject, body)
                flash('Protokoll aktualisiert und Benutzer benachrichtigt', 'success')
            else:
                flash('Protokoll aktualisiert (Benutzer für Benachrichtigung nicht gefunden)', 'warning')
        else:
            flash('Protokoll aktualisiert', 'success')

        return redirect(url_for('admin.admin_protokoll_details', protokoll_id=protokoll_id))

    # GET
    protokoll = db.execute('''
        SELECT p.*, u.name as user_name 
        FROM protokolle p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.id = ?
    ''', (protokoll_id,)).fetchone()
    
    # Prüfer nach Bundesland laden für das Select-Menü
    alle_pruefer = db.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name').fetchall()
    pruefer_nach_bundesland = {}
    for pruefer in alle_pruefer:
        if pruefer['bundesland'] not in pruefer_nach_bundesland:
            pruefer_nach_bundesland[pruefer['bundesland']] = []
        pruefer_nach_bundesland[pruefer['bundesland']].append({'id': pruefer['id'], 'name': pruefer['name']})
    
    return render_template('admin/protokoll_bearbeiten_alternative.html', 
                           protokoll=protokoll,
                           bundeslaender=BUNDESLAENDER,
                           predefined_hashtags=PREDEFINED_HASHTAGS,
                           pruefer_nach_bundesland=pruefer_nach_bundesland)

@bp.route('/admin/protokoll/<int:protokoll_id>/loeschen', methods=['POST'])
@admin_required
def admin_protokoll_loeschen(protokoll_id):
    """Protokoll als Admin löschen"""
    grund = request.form.get('grund')
    db = get_db()
    
    # Info für Log und Email holen vor dem Löschen
    p = db.execute('SELECT user_id, datum FROM protokolle WHERE id = ?', (protokoll_id,)).fetchone()
    if p:
        # Email Logik hier einfügen (Platzhalter)
        pass

    db.execute('DELETE FROM protokolle WHERE id = ?', (protokoll_id,))
    
    # Log
    db.execute('INSERT INTO logs (user_id, action, details) VALUES (?, ?, ?)',
               (session['user_id'], 'PROTOKOLL_GELOESCHT', f'Protokoll {protokoll_id} gelöscht. Grund: {grund}'))
    db.commit()
    
    flash('Protokoll gelöscht', 'success')
    return redirect(url_for('admin.admin_protokolle'))

@bp.route('/admin/logs')
@admin_required
def admin_logs():
    """Admin-Aktivitätslogs anzeigen"""
    db = get_db()
    logs = db.execute('''
        SELECT l.*, u.name as user_name 
        FROM logs l 
        LEFT JOIN users u ON l.user_id = u.id 
        ORDER BY l.timestamp DESC LIMIT 100
    ''').fetchall()
    return render_template('admin/logs.html', logs=logs)
