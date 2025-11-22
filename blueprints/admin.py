from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils import admin_required, send_email
from datetime import datetime

bp = Blueprint('admin', __name__)

# Bundesländer
BUNDESLAENDER = [
    'Baden-Württemberg', 'Bayern', 'Berlin', 'Brandenburg', 'Bremen',
    'Hamburg', 'Hessen', 'Mecklenburg-Vorpommern', 'Niedersachsen',
    'Nordrhein-Westfalen', 'Rheinland-Pfalz', 'Saarland', 'Sachsen',
    'Sachsen-Anhalt', 'Schleswig-Holstein', 'Thüringen'
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
    # ... implementation similar to original app.py but using db ...
    # Simplified for brevity, assuming similar logic to protokolle() but with more filters
    return render_template('admin/protokolle.html', protokolle=[], bundeslaender=BUNDESLAENDER) # Placeholder

@bp.route('/admin/protokoll/<int:protokoll_id>')
@admin_required
def admin_protokoll_details(protokoll_id):
    """Admin-Ansicht für Protokoll-Details"""
    # ... implementation ...
    return render_template('admin/protokoll_details.html') # Placeholder

@bp.route('/admin/protokoll/<int:protokoll_id>/bearbeiten', methods=['GET', 'POST'])
@admin_required
def admin_protokoll_bearbeiten(protokoll_id):
    """Protokoll als Admin bearbeiten"""
    # ... implementation ...
    return render_template('admin/protokoll_bearbeiten.html') # Placeholder

@bp.route('/admin/protokoll/<int:protokoll_id>/loeschen', methods=['POST'])
@admin_required
def admin_protokoll_loeschen(protokoll_id):
    """Protokoll als Admin löschen"""
    # ... implementation ...
    return redirect(url_for('admin.admin_protokolle'))

@bp.route('/admin/logs')
@admin_required
def admin_logs():
    """Admin-Aktivitätslogs anzeigen"""
    # ... implementation ...
    return render_template('admin/logs.html', logs=[]) # Placeholder
