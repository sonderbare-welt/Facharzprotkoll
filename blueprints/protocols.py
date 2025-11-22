from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from db import get_db
from utils import login_required
from datetime import datetime, timedelta

bp = Blueprint('protocols', __name__)

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

@bp.route('/protokolle')
@login_required
def protokolle():
    """Protokoll-Übersicht mit Admin-Features"""
    bundesland_filter = request.args.get('bundesland', '')
    pruefer_filter = request.args.get('pruefer', '')
    hashtag_filter = request.args.get('hashtag', '')

    db = get_db()

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

    protokoll_liste = db.execute(query, params).fetchall()

    # Prüfer für Filter laden
    alle_pruefer = [row[0] for row in db.execute('SELECT DISTINCT name FROM pruefer ORDER BY name').fetchall()]

    # Prüfen ob aktueller Benutzer Admin ist
    is_admin = session.get('is_admin', False)

    return render_template('protokolle.html',
                           protokolle=protokoll_liste,
                           bundeslaender=BUNDESLAENDER,
                           alle_pruefer=alle_pruefer,
                           predefined_hashtags=PREDEFINED_HASHTAGS,
                           bundesland_filter=bundesland_filter,
                           pruefer_filter=pruefer_filter,
                           hashtag_filter=hashtag_filter,
                           is_admin=is_admin)

@bp.route('/protokoll/neu', methods=['GET', 'POST'])
@login_required
def neues_protokoll():
    """Neues Protokoll erstellen"""
    db = get_db()

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
            return redirect(url_for('protocols.neues_protokoll'))

        # Prüfen ob Prüfer existieren
        for pruefer_id in [pruefer1_id, pruefer2_id, pruefer3_id]:
            if db.execute('SELECT COUNT(*) FROM pruefer WHERE id = ?', (pruefer_id,)).fetchone()[0] == 0:
                flash('Ungültiger Prüfer ausgewählt.', 'error')
                return redirect(url_for('protocols.neues_protokoll'))

        # Protokoll speichern
        db.execute('''
            INSERT INTO protokolle (user_id, datum, bundesland, pruefer1_id, pruefer2_id,
                                    pruefer3_id, inhalt, hashtags, kommentar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], datum, bundesland, pruefer1_id, pruefer2_id,
              pruefer3_id, inhalt, hashtags, kommentar))

        # Erinnerung als erledigt markieren (falls vorhanden)
        db.execute('''
            UPDATE erinnerungen
            SET protokoll_erstellt = TRUE
            WHERE user_id = ?
              AND protokoll_erstellt = FALSE
        ''', (session['user_id'],))

        db.commit()

        flash('Protokoll erfolgreich erstellt!', 'success')
        return redirect(url_for('protocols.protokolle'))

    # Prüfer nach Bundesland laden
    alle_pruefer = db.execute('SELECT id, name, bundesland FROM pruefer ORDER BY bundesland, name').fetchall()

    # Prüfer nach Bundesland gruppieren
    pruefer_nach_bundesland = {}
    for pruefer in alle_pruefer:
        if pruefer['bundesland'] not in pruefer_nach_bundesland:
            pruefer_nach_bundesland[pruefer['bundesland']] = []
        pruefer_nach_bundesland[pruefer['bundesland']].append({'id': pruefer['id'], 'name': pruefer['name']})

    return render_template('neues_protokoll.html',
                           bundeslaender=BUNDESLAENDER,
                           pruefer_nach_bundesland=pruefer_nach_bundesland,
                           predefined_hashtags=PREDEFINED_HASHTAGS)

@bp.route('/api/pruefer/<bundesland>')
@login_required
def api_pruefer(bundesland):
    """API: Prüfer nach Bundesland"""
    db = get_db()
    pruefer = [{'id': row['id'], 'name': row['name']} for row in db.execute('SELECT id, name FROM pruefer WHERE bundesland = ? ORDER BY name', (bundesland,)).fetchall()]
    return jsonify(pruefer)

@bp.route('/erinnerung', methods=['POST'])
@login_required
def erinnerung_erstellen():
    """Erinnerung für Protokoll erstellen"""
    pruefungsdatum = request.form.get('pruefungsdatum')

    if not pruefungsdatum:
        flash('Prüfungsdatum ist erforderlich.', 'error')
        return redirect(url_for('main.dashboard'))

    # Erste Erinnerung in 2 Tagen
    naechste_erinnerung = datetime.now() + timedelta(days=2)

    db = get_db()
    db.execute('''
        INSERT INTO erinnerungen (user_id, pruefungsdatum, naechste_erinnerung)
        VALUES (?, ?, ?)
    ''', (session['user_id'], pruefungsdatum, naechste_erinnerung))
    db.commit()

    flash('Erinnerung wurde eingerichtet. Sie erhalten in 2 Tagen eine E-Mail.', 'success')
    return redirect(url_for('main.dashboard'))
