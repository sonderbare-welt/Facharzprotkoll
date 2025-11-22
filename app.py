from flask import Flask, render_template, redirect, url_for, flash, session # Trigger reloads import mail
from config import Config
from extensions import mail
from db import init_app
import threading
import time
from datetime import datetime, timedelta
import sqlite3

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    mail.init_app(app)
    init_app(app)

    # Register Blueprints
    from blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from blueprints.main import bp as main_bp
    app.register_blueprint(main_bp)

    from blueprints.protocols import bp as protocols_bp
    app.register_blueprint(protocols_bp)

    from blueprints.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    return app

app = create_app()

def erinnerungs_service():
    """Service für automatische Erinnerungen"""
    with app.app_context():
        while True:
            try:
                conn = sqlite3.connect(app.config['DATABASE'])
                c = conn.cursor()
                # ... existing logic ...
                conn.close()
            except Exception as e:
                print(f"Erinnerungs-Service Fehler: {e}")
            time.sleep(3600)

if __name__ == '__main__':
    # Erinnerungs-Service in separatem Thread starten
    # reminder_thread = threading.Thread(target=erinnerungs_service, daemon=True)
    # reminder_thread.start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)