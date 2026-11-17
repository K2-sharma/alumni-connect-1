import sqlite3
import os
import json
from datetime import datetime
from config import Config

def get_db_connection():
    try:
        os.makedirs(os.path.dirname(Config.DATABASE), exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
    except Exception:
        pass
    
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'alumni', 'student')),
        phone TEXT,
        avatar TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS alumni_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        enrollment_no TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        alternative_phone TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        country TEXT DEFAULT 'India',
        postal_code TEXT,
        batch TEXT NOT NULL,
        course TEXT NOT NULL,
        department TEXT NOT NULL,
        graduation_year INTEGER NOT NULL,
        cgpa REAL,
        dob TEXT,
        emergency_contact_name TEXT,
        emergency_contact_relation TEXT,
        emergency_contact_phone TEXT,
        current_company TEXT,
        current_designation TEXT,
        industry TEXT,
        work_experience_years REAL DEFAULT 0,
        linkedin_url TEXT,
        bio TEXT,
        skills TEXT,
        willing_to_mentor INTEGER DEFAULT 0,
        mentor_domains TEXT,
        is_verified INTEGER DEFAULT 1,
        privacy_hide_phone INTEGER DEFAULT 0,
        privacy_hide_family INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS pending_profile_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumni_id INTEGER NOT NULL,
        requested_by_user_id INTEGER NOT NULL,
        changes_json TEXT NOT NULL,
        reason TEXT,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
        admin_comments TEXT,
        reviewed_by INTEGER,
        reviewed_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (alumni_id) REFERENCES alumni_profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (requested_by_user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS call_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumni_id INTEGER NOT NULL,
        staff_id INTEGER,
        staff_name TEXT NOT NULL,
        call_date TEXT NOT NULL,
        call_time TEXT,
        purpose TEXT NOT NULL,
        outcome TEXT NOT NULL,
        follow_up_date TEXT,
        notes TEXT,
        status TEXT DEFAULT 'completed' CHECK(status IN ('completed', 'unanswered', 'follow_up_required', 'scheduled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (alumni_id) REFERENCES alumni_profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (staff_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS helpdesk_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_no TEXT UNIQUE NOT NULL,
        requester_id INTEGER,
        requester_name TEXT NOT NULL,
        requester_email TEXT NOT NULL,
        requester_role TEXT NOT NULL,
        category TEXT NOT NULL,
        priority TEXT DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High', 'Urgent')),
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Open' CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
        assigned_to_id INTEGER,
        assigned_to_name TEXT,
        department TEXT,
        ai_suggested_category TEXT,
        ai_confidence REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (assigned_to_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS ticket_replies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        sender_id INTEGER,
        sender_name TEXT NOT NULL,
        sender_role TEXT NOT NULL,
        message TEXT NOT NULL,
        is_internal_note INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_id) REFERENCES helpdesk_tickets(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS notifications_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_email TEXT NOT NULL,
        recipient_name TEXT NOT NULL,
        notification_type TEXT NOT NULL,
        subject TEXT NOT NULL,
        message_preview TEXT NOT NULL,
        status TEXT DEFAULT 'Sent',
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_name TEXT NOT NULL,
        template_key TEXT UNIQUE NOT NULL,
        subject_template TEXT NOT NULL,
        body_template TEXT NOT NULL,
        category TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER,
        details TEXT,
        ip_address TEXT DEFAULT '127.0.0.1',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        target_audience TEXT DEFAULT 'all',
        author_id INTEGER,
        author_name TEXT NOT NULL,
        event_date TEXT,
        is_pinned INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS mentorship_connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentor_alumni_id INTEGER NOT NULL,
        student_user_id INTEGER NOT NULL,
        student_name TEXT NOT NULL,
        student_course TEXT,
        message TEXT,
        status TEXT DEFAULT 'requested' CHECK(status IN ('requested', 'accepted', 'declined')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mentor_alumni_id) REFERENCES alumni_profiles(id) ON DELETE CASCADE,
        FOREIGN KEY (student_user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    ''')
    
    conn.commit()
    conn.close()

def log_audit(user_id, user_name, action, entity_type, entity_id=None, details="", ip_address="127.0.0.1"):
    try:
        conn = get_db_connection()
        conn.execute(
            '''INSERT INTO audit_logs (user_id, user_name, action, entity_type, entity_id, details, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, user_name, action, entity_type, entity_id, details, ip_address)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging audit: {e}")
