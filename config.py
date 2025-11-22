import os
import secrets

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    DATABASE = 'urologie_pruefung.db'
    
    # Mail settings
    MAIL_SERVER = 'smtp.ionos.de'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'm.sondermann@gesru.de'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = 'm.sondermann@gesru.de'
