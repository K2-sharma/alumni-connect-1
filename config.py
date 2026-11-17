import os
import shutil

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'alumni-connect-secret-key-2026-secure')
    
    # If running on Vercel Serverless / AWS Lambda, use /tmp for writable database and dynamic uploads
    if os.environ.get('VERCEL') or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or '/var/task' in BASE_DIR:
        DATABASE = '/tmp/alumni_connect.db'
        UPLOAD_FOLDER = '/tmp/uploads'
        REPORTS_FOLDER = '/tmp/generated_reports'
        src_db = os.path.join(BASE_DIR, 'alumni_connect.db')
        if os.path.exists(src_db) and not os.path.exists('/tmp/alumni_connect.db'):
            try:
                shutil.copy2(src_db, '/tmp/alumni_connect.db')
            except Exception as e:
                print(f"Error copying DB to /tmp: {e}")
    else:
        DATABASE = os.path.join(BASE_DIR, 'alumni_connect.db')
        UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
        REPORTS_FOLDER = os.path.join(BASE_DIR, 'static', 'generated_reports')
        
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    
    # Email Automation configuration (simulated / real SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'alumni.connect.noreply@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    INSTITUTION_NAME = "Vivekananda Institute of Professional Studies - Technical Campus"
    INSTITUTION_ACRONYM = "VIPS-TC"
    UNIVERSITY_AFFILIATION = "Guru Gobind Singh Indraprastha University, Delhi"
    INSTITUTION_TAGLINE = "Jobs, internships and referrals from the VIPS-TC network"
