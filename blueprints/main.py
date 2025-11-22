from flask import Blueprint, render_template, session, current_app
from db import get_db
from utils import login_required

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """Startseite"""
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard"""
    db = get_db()

    # Statistiken abrufen
    meine_protokolle = db.execute('SELECT COUNT(*) FROM protokolle WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    gesamt_protokolle = db.execute('SELECT COUNT(*) FROM protokolle').fetchone()[0]
    anzahl_pruefer = db.execute('SELECT COUNT(*) FROM pruefer').fetchone()[0]

    # Neueste Protokolle
    neueste_protokolle = db.execute('''
        SELECT p.datum, p.bundesland, pr1.name, p.hashtags, p.created_at
        FROM protokolle p
        JOIN pruefer pr1 ON p.pruefer1_id = pr1.id
        ORDER BY p.created_at DESC LIMIT 5
    ''').fetchall()

    return render_template('dashboard.html',
                           meine_protokolle=meine_protokolle,
                           gesamt_protokolle=gesamt_protokolle,
                           anzahl_pruefer=anzahl_pruefer,
                           neueste_protokolle=neueste_protokolle)

@bp.route('/datenschutz')
def datenschutz():
    """Datenschutzerklärung"""
    return render_template('datenschutz.html')

@bp.route('/impressum')
def impressum():
    """Impressum"""
    return render_template('impressum.html')
