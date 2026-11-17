import os
import json
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, send_from_directory, abort
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import openpyxl

from config import Config, BASE_DIR
from database import get_db_connection, init_db, log_audit
from ai_engine import AIEngine
from reports import (
    generate_alumni_directory_pdf,
    generate_call_report_pdf,
    export_alumni_to_excel,
    generate_excel_sample_template,
    get_report_filepath
)

app = Flask(__name__)
app.config.from_object(Config)

# Ensure folders exist safely (ignore read-only filesystem restrictions on serverless platforms)
try:
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
except Exception:
    pass

# Ensure database tables and initial records exist on startup
try:
    from seed_data import seed_database
    seed_database()
except Exception as e:
    print(f"Database auto-seed notice: {e}")

# -------------------------------------------------------------
# Context Processors & Template Filters
# -------------------------------------------------------------
@app.context_processor
def inject_global_data():
    user = None
    pending_approvals_count = 0
    today_birthdays_count = 0
    open_tickets_count = 0
    
    conn = get_db_connection()
    if 'user_id' in session:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        
    try:
        # Quick counts for badges
        pending_approvals_count = conn.execute(
            "SELECT COUNT(*) FROM pending_profile_updates WHERE status = 'pending'"
        ).fetchone()[0]
        
        # Today's birthdays (month and day match)
        today_md = datetime.now().strftime('-%m-%d')
        today_birthdays_count = conn.execute(
            "SELECT COUNT(*) FROM alumni_profiles WHERE dob LIKE ?", (f"%{today_md}",)
        ).fetchone()[0]
        
        open_tickets_count = conn.execute(
            "SELECT COUNT(*) FROM helpdesk_tickets WHERE status IN ('Open', 'In Progress')"
        ).fetchone()[0]
    except Exception:
        pass
    finally:
        conn.close()
        
    return {
        'current_user': user,
        'institution_name': Config.INSTITUTION_NAME,
        'institution_acronym': Config.INSTITUTION_ACRONYM,
        'university_affiliation': getattr(Config, 'UNIVERSITY_AFFILIATION', 'Guru Gobind Singh Indraprastha University, Delhi'),
        'institution_tagline': getattr(Config, 'INSTITUTION_TAGLINE', 'Jobs, internships and referrals from the VIPS-TC network'),
        'pending_approvals_count': pending_approvals_count,
        'today_birthdays_count': today_birthdays_count,
        'open_tickets_count': open_tickets_count,
        'current_date': datetime.now().strftime('%d %B %Y')
    }

# -------------------------------------------------------------
# Authentication & Role Decorators
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please sign in first.", "warning")
                return redirect(url_for('login'))
            user_role = session.get('user_role')
            if user_role not in allowed_roles:
                flash("Access denied: You do not have permission for this module.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# -------------------------------------------------------------
# Auth Routes & Quick Demo Switcher
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND status = 'active'", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_role'] = user['role']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            
            log_audit(user['id'], user['full_name'], 'LOGIN', 'User', user['id'], 'User logged in successfully', request.remote_addr)
            flash(f"Welcome back, {user['full_name']}! Signed in as {user['role'].title()}.", "success")
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash("Invalid email or password. Please try again.", "danger")
            
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    uid = session.get('user_id')
    uname = session.get('user_name', 'User')
    if uid:
        log_audit(uid, uname, 'LOGOUT', 'User', uid, 'User signed out', request.remote_addr)
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'alumni')
        phone = request.form.get('phone', '').strip()
        enrollment_no = request.form.get('enrollment_no', '').strip()
        course = request.form.get('course', 'B.Tech')
        batch = request.form.get('batch', '2020-2024')
        department = request.form.get('department', 'Computer Science')
        graduation_year = int(request.form.get('graduation_year', 2024))
        
        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("An account with this email already exists.", "warning")
            return redirect(url_for('register'))
            
        cursor = conn.cursor()
        username = email.split('@')[0]
        pw_hash = generate_password_hash(password)
        
        cursor.execute(
            '''INSERT INTO users (username, email, password_hash, full_name, role, phone)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (username, email, pw_hash, full_name, role, phone)
        )
        new_user_id = cursor.lastrowid
        
        if role == 'alumni':
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            cursor.execute(
                '''INSERT INTO alumni_profiles (
                    user_id, enrollment_no, first_name, last_name, email, phone,
                    batch, course, department, graduation_year, willing_to_mentor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                (new_user_id, enrollment_no or f"EN{graduation_year}{course[:3].upper()}{new_user_id:03d}",
                 first_name, last_name, email, phone, batch, course, department, graduation_year)
            )
            
        conn.commit()
        conn.close()
        flash("Registration successful! You may now sign in.", "success")
        return redirect(url_for('login'))
        
    return render_template('auth/register.html')

# -------------------------------------------------------------
# Main Dashboard
# -------------------------------------------------------------
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    role = session.get('user_role')
    user_id = session.get('user_id')
    
    # Common stats
    total_alumni = conn.execute("SELECT COUNT(*) FROM alumni_profiles").fetchone()[0]
    total_calls = conn.execute("SELECT COUNT(*) FROM call_logs").fetchone()[0]
    pending_calls = conn.execute("SELECT COUNT(*) FROM call_logs WHERE status IN ('follow_up_required', 'scheduled')").fetchone()[0]
    total_tickets = conn.execute("SELECT COUNT(*) FROM helpdesk_tickets").fetchone()[0]
    unresolved_tickets = conn.execute("SELECT COUNT(*) FROM helpdesk_tickets WHERE status IN ('Open', 'In Progress')").fetchone()[0]
    
    # Today's birthdays
    today_md = datetime.now().strftime('-%m-%d')
    today_birthdays = conn.execute(
        "SELECT * FROM alumni_profiles WHERE dob LIKE ?", (f"%{today_md}",)
    ).fetchall()
    
    # Recent announcements
    announcements = conn.execute(
        "SELECT * FROM announcements ORDER BY is_pinned DESC, created_at DESC LIMIT 5"
    ).fetchall()
    
    # Course breakdown for Chart
    course_counts = conn.execute(
        "SELECT course, COUNT(*) as count FROM alumni_profiles GROUP BY course"
    ).fetchall()
    course_labels = [r['course'] for r in course_counts]
    course_data = [r['count'] for r in course_counts]
    
    # Top Industries for Chart
    industry_counts = conn.execute(
        "SELECT industry, COUNT(*) as count FROM alumni_profiles WHERE industry IS NOT NULL AND industry != '' GROUP BY industry ORDER BY count DESC LIMIT 5"
    ).fetchall()
    industry_labels = [r['industry'] for r in industry_counts]
    industry_data = [r['count'] for r in industry_counts]
    
    # Recent activity / audit
    recent_audits = conn.execute(
        "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 6"
    ).fetchall()
    
    # Teachers list for ticket assignment dropdowns
    teachers_list = conn.execute(
        "SELECT id, full_name, email FROM users WHERE role IN ('admin', 'staff') ORDER BY full_name ASC"
    ).fetchall()

    # Role-tailored datasets
    recommended_mentors = []
    student_connections = []
    user_tickets = []
    my_profile = None
    incoming_mentorship = []
    faculty_assigned_tickets = []
    faculty_calls = []
    unassigned_tickets = []
    pending_approvals = []
    
    if role == 'student':
        # Student: Connect with Alumni (LinkedIn, Mentorship, skills)
        recommended_mentors = conn.execute(
            '''SELECT * FROM alumni_profiles 
               WHERE willing_to_mentor = 1 
               ORDER BY work_experience_years DESC, graduation_year DESC LIMIT 8'''
        ).fetchall()
        student_connections = conn.execute(
            '''SELECT m.*, a.first_name, a.last_name, a.current_company, a.current_designation, a.linkedin_url, a.course, a.batch, a.email as alumni_email
               FROM mentorship_connections m
               JOIN alumni_profiles a ON m.mentor_alumni_id = a.id
               WHERE m.student_user_id = ? ORDER BY m.created_at DESC''',
            (user_id,)
        ).fetchall()
        user_tickets = conn.execute(
            "SELECT * FROM helpdesk_tickets WHERE requester_id = ? ORDER BY created_at DESC LIMIT 5",
            (user_id,)
        ).fetchall()

    elif role == 'alumni':
        # Alumni: Raise degree/certificate/helpdesk queries & manage student mentorship
        my_profile = conn.execute("SELECT * FROM alumni_profiles WHERE user_id = ?", (user_id,)).fetchone()
        user_tickets = conn.execute(
            "SELECT * FROM helpdesk_tickets WHERE requester_id = ? ORDER BY created_at DESC LIMIT 8",
            (user_id,)
        ).fetchall()
        if my_profile:
            incoming_mentorship = conn.execute(
                '''SELECT m.*, u.full_name as student_full_name, u.email as student_email
                   FROM mentorship_connections m
                   JOIN users u ON m.student_user_id = u.id
                   WHERE m.mentor_alumni_id = ? ORDER BY m.created_at DESC''',
                (my_profile['id'],)
            ).fetchall()

    elif role == 'staff':
        # Faculty / Teacher: Assigned tickets, excel export, alumni details, calls
        faculty_assigned_tickets = conn.execute(
            '''SELECT * FROM helpdesk_tickets 
               WHERE assigned_to_id = ? 
               ORDER BY CASE WHEN status = 'Open' THEN 1 WHEN status = 'In Progress' THEN 2 ELSE 3 END, created_at DESC LIMIT 10''',
            (user_id,)
        ).fetchall()
        faculty_calls = conn.execute(
            '''SELECT c.*, a.first_name, a.last_name, a.course, a.batch 
               FROM call_logs c 
               JOIN alumni_profiles a ON c.alumni_id = a.id 
               WHERE c.staff_id = ? ORDER BY c.created_at DESC LIMIT 5''',
            (user_id,)
        ).fetchall()

    elif role == 'admin':
        # Admin: Full operations, unassigned tickets queue for teacher assignment
        unassigned_tickets = conn.execute(
            '''SELECT * FROM helpdesk_tickets 
               WHERE (assigned_to_id IS NULL OR assigned_to_id = '') AND status IN ('Open', 'In Progress') 
               ORDER BY CASE WHEN priority = 'Urgent' THEN 1 WHEN priority = 'High' THEN 2 ELSE 3 END, created_at DESC LIMIT 10'''
        ).fetchall()
        pending_approvals = conn.execute(
            '''SELECT p.*, a.first_name, a.last_name, a.enrollment_no, a.course, a.batch, u.full_name as requester_name 
               FROM pending_profile_updates p 
               JOIN alumni_profiles a ON p.alumni_id = a.id 
               JOIN users u ON p.requested_by_user_id = u.id 
               WHERE p.status = 'pending' ORDER BY p.created_at DESC LIMIT 5'''
        ).fetchall()
        
    conn.close()
    
    return render_template(
        'index.html',
        total_alumni=total_alumni,
        total_calls=total_calls,
        pending_calls=pending_calls,
        total_tickets=total_tickets,
        unresolved_tickets=unresolved_tickets,
        today_birthdays=today_birthdays,
        announcements=announcements,
        course_labels=course_labels,
        course_data=course_data,
        industry_labels=industry_labels,
        industry_data=industry_data,
        recent_audits=recent_audits,
        teachers_list=teachers_list,
        recommended_mentors=recommended_mentors,
        student_connections=student_connections,
        user_tickets=user_tickets,
        my_profile=my_profile,
        incoming_mentorship=incoming_mentorship,
        faculty_assigned_tickets=faculty_assigned_tickets,
        faculty_calls=faculty_calls,
        unassigned_tickets=unassigned_tickets,
        pending_approvals=pending_approvals
    )

# -------------------------------------------------------------
# Module A: Alumni Database Management
# -------------------------------------------------------------
@app.route('/alumni')
@login_required
def alumni_list():
    search_query = request.args.get('q', '').strip()
    nl_query = request.args.get('nl_query', '').strip()
    batch_filter = request.args.get('batch', '').strip()
    course_filter = request.args.get('course', '').strip()
    dept_filter = request.args.get('dept', '').strip()
    city_filter = request.args.get('city', '').strip()
    company_filter = request.args.get('company', '').strip()
    industry_filter = request.args.get('industry', '').strip()
    role_filter = request.args.get('role', '').strip()
    mentor_only = request.args.get('mentor_only', '') == '1'
    
    conn = get_db_connection()
    
    # If natural language query was submitted (or q contains a multi-word conversational search)
    nl_interpreted = None
    active_nl = nl_query
    if not active_nl and search_query and len(search_query.split()) >= 3:
        active_nl = search_query

    if active_nl:
        nl_interpreted = AIEngine.parse_natural_language_query(active_nl)
        if nl_interpreted.get('batch_year'):
            batch_filter = nl_interpreted['batch_year']
        if nl_interpreted.get('course'):
            course_filter = nl_interpreted['course']
        if nl_interpreted.get('department'):
            dept_filter = nl_interpreted['department']
        if nl_interpreted.get('company'):
            company_filter = nl_interpreted['company']
        if nl_interpreted.get('location'):
            city_filter = nl_interpreted['location']
        if nl_interpreted.get('role'):
            role_filter = nl_interpreted['role']
        if nl_interpreted.get('industry') and not company_filter:
            industry_filter = nl_interpreted['industry']
        if nl_interpreted.get('mentor_only'):
            mentor_only = True
        if nl_interpreted.get('keywords'):
            search_query = " ".join(nl_interpreted['keywords'])
        elif not search_query:
            search_query = ""
            
    sql = "SELECT * FROM alumni_profiles WHERE 1=1"
    params = []
    
    if course_filter:
        clean_c = course_filter.replace('.', '')
        sql += " AND (course LIKE ? OR course LIKE ? OR course LIKE ?)"
        params.extend([f"%{course_filter}%", f"%{clean_c}%", f"%{clean_c.lower()}%"])
        
    if batch_filter:
        sql += " AND (batch LIKE ? OR graduation_year = ?)"
        params.extend([f"%{batch_filter}%", batch_filter])
        
    if dept_filter:
        sql += " AND department LIKE ?"
        params.append(f"%{dept_filter}%")
        
    if city_filter:
        sql += " AND (city LIKE ? OR state LIKE ? OR country LIKE ? OR address LIKE ?)"
        params.extend([f"%{city_filter}%", f"%{city_filter}%", f"%{city_filter}%", f"%{city_filter}%"])
        
    if company_filter:
        sql += " AND current_company LIKE ?"
        params.append(f"%{company_filter}%")

    if role_filter:
        sql += " AND current_designation LIKE ?"
        params.append(f"%{role_filter}%")

    if industry_filter:
        sql += " AND (industry LIKE ? OR current_designation LIKE ? OR skills LIKE ?)"
        params.extend([f"%{industry_filter}%", f"%{industry_filter}%", f"%{industry_filter}%"])
        
    if mentor_only:
        sql += " AND willing_to_mentor = 1"

    if search_query:
        tokens = [t.strip() for t in search_query.split() if t.strip()]
        if len(tokens) > 1:
            # Whole phrase match against full name or other fields OR token-wise match
            sql += """ AND (
                (first_name || ' ' || last_name) LIKE ? 
                OR current_company LIKE ?
                OR current_designation LIKE ?
                OR skills LIKE ?
                OR (
            """
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])
            token_clauses = []
            for t in tokens:
                term = f"%{t}%"
                token_clauses.append("""(first_name LIKE ? OR last_name LIKE ? OR enrollment_no LIKE ? 
                                        OR email LIKE ? OR current_company LIKE ? OR current_designation LIKE ? 
                                        OR department LIKE ? OR skills LIKE ? OR city LIKE ?)""")
                params.extend([term, term, term, term, term, term, term, term, term])
            sql += " AND ".join(token_clauses) + "))"
        else:
            term = f"%{search_query}%"
            sql += """ AND (first_name LIKE ? OR last_name LIKE ? OR (first_name || ' ' || last_name) LIKE ? 
                        OR enrollment_no LIKE ? OR email LIKE ? OR current_company LIKE ? OR current_designation LIKE ? 
                        OR department LIKE ? OR skills LIKE ? OR city LIKE ? OR bio LIKE ?)"""
            params.extend([term, term, term, term, term, term, term, term, term, term, term])
        
    sql += " ORDER BY graduation_year DESC, first_name ASC"
    alumni = conn.execute(sql, params).fetchall()
    
    # Distinct filter values for dropdowns
    batches = [r[0] for r in conn.execute("SELECT DISTINCT batch FROM alumni_profiles ORDER BY batch DESC").fetchall() if r[0]]
    courses = [r[0] for r in conn.execute("SELECT DISTINCT course FROM alumni_profiles ORDER BY course").fetchall() if r[0]]
    departments = [r[0] for r in conn.execute("SELECT DISTINCT department FROM alumni_profiles ORDER BY department").fetchall() if r[0]]
    cities = [r[0] for r in conn.execute("SELECT DISTINCT city FROM alumni_profiles WHERE city IS NOT NULL ORDER BY city").fetchall() if r[0]]
    
    conn.close()
    
    return render_template(
        'alumni/list.html',
        alumni=alumni,
        batches=batches,
        courses=courses,
        departments=departments,
        cities=cities,
        search_query=search_query,
        nl_query=nl_query,
        nl_interpreted=nl_interpreted,
        batch_filter=batch_filter,
        course_filter=course_filter,
        dept_filter=dept_filter,
        city_filter=city_filter,
        company_filter=company_filter,
        mentor_only=mentor_only
    )

@app.route('/alumni/<int:id>')
@login_required
def alumni_view(id):
    conn = get_db_connection()
    alumnus = conn.execute("SELECT * FROM alumni_profiles WHERE id = ?", (id,)).fetchone()
    if not alumnus:
        conn.close()
        flash("Alumnus record not found.", "warning")
        return redirect(url_for('alumni_list'))
        
    # Call logs for this alumnus
    calls = conn.execute("SELECT * FROM call_logs WHERE alumni_id = ? ORDER BY call_date DESC, created_at DESC", (id,)).fetchall()
    
    # Profile update history
    updates = conn.execute("SELECT * FROM pending_profile_updates WHERE alumni_id = ? ORDER BY created_at DESC", (id,)).fetchall()
    
    # Process updates JSON if any
    parsed_updates = []
    for u in updates:
        parsed_updates.append({
            'id': u['id'],
            'status': u['status'],
            'created_at': u['created_at'],
            'reason': u['reason'],
            'admin_comments': u['admin_comments'],
            'changes': json.loads(u['changes_json']) if u['changes_json'] else {}
        })
        
    conn.close()
    return render_template('alumni/view.html', alumnus=alumnus, calls=calls, updates=parsed_updates)

@app.route('/alumni/new', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'staff'])
def alumni_create():
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        
        enrollment_no = request.form.get('enrollment_no', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        alt_phone = request.form.get('alternative_phone', '').strip()
        batch = request.form.get('batch', '').strip()
        course = request.form.get('course', '').strip()
        department = request.form.get('department', '').strip()
        graduation_year = int(request.form.get('graduation_year', 2024))
        cgpa = float(request.form.get('cgpa', 0.0) or 0.0)
        dob = request.form.get('dob', '').strip()
        
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        country = request.form.get('country', 'India').strip()
        postal_code = request.form.get('postal_code', '').strip()
        
        em_name = request.form.get('emergency_contact_name', '').strip()
        em_rel = request.form.get('emergency_contact_relation', '').strip()
        em_phone = request.form.get('emergency_contact_phone', '').strip()
        
        company = request.form.get('current_company', '').strip()
        designation = request.form.get('current_designation', '').strip()
        industry = request.form.get('industry', '').strip()
        experience = float(request.form.get('work_experience_years', 0.0) or 0.0)
        linkedin = request.form.get('linkedin_url', '').strip()
        skills = request.form.get('skills', '').strip()
        bio = request.form.get('bio', '').strip()
        willing_to_mentor = 1 if request.form.get('willing_to_mentor') == 'on' else 0
        mentor_domains = request.form.get('mentor_domains', '').strip()
        
        try:
            cursor.execute(
                '''INSERT INTO alumni_profiles (
                    enrollment_no, first_name, last_name, email, phone, alternative_phone,
                    batch, course, department, graduation_year, cgpa, dob,
                    address, city, state, country, postal_code,
                    emergency_contact_name, emergency_contact_relation, emergency_contact_phone,
                    current_company, current_designation, industry, work_experience_years,
                    linkedin_url, skills, bio, willing_to_mentor, mentor_domains
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (enrollment_no, first_name, last_name, email, phone, alt_phone,
                 batch, course, department, graduation_year, cgpa, dob,
                 address, city, state, country, postal_code,
                 em_name, em_rel, em_phone,
                 company, designation, industry, experience,
                 linkedin, skills, bio, willing_to_mentor, mentor_domains)
            )
            new_id = cursor.lastrowid
            conn.commit()
            log_audit(session['user_id'], session['user_name'], 'CREATE_ALUMNI', 'AlumniProfile', new_id, f"Added alumnus {first_name} {last_name} ({enrollment_no})", request.remote_addr)
            conn.close()
            flash(f"Alumnus {first_name} {last_name} registered successfully!", "success")
            return redirect(url_for('alumni_view', id=new_id))
        except Exception as e:
            conn.close()
            flash(f"Error adding alumnus record: {e}", "danger")
            
    return render_template('alumni/create.html')

@app.route('/alumni/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def alumni_edit(id):
    conn = get_db_connection()
    alumnus = conn.execute("SELECT * FROM alumni_profiles WHERE id = ?", (id,)).fetchone()
    if not alumnus:
        conn.close()
        flash("Record not found.", "warning")
        return redirect(url_for('alumni_list'))
        
    if request.method == 'POST':
        cursor = conn.cursor()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        alt_phone = request.form.get('alternative_phone', '').strip()
        batch = request.form.get('batch', '').strip()
        course = request.form.get('course', '').strip()
        department = request.form.get('department', '').strip()
        graduation_year = int(request.form.get('graduation_year', 2024))
        cgpa = float(request.form.get('cgpa', 0.0) or 0.0)
        dob = request.form.get('dob', '').strip()
        
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        country = request.form.get('country', 'India').strip()
        postal_code = request.form.get('postal_code', '').strip()
        
        em_name = request.form.get('emergency_contact_name', '').strip()
        em_rel = request.form.get('emergency_contact_relation', '').strip()
        em_phone = request.form.get('emergency_contact_phone', '').strip()
        
        company = request.form.get('current_company', '').strip()
        designation = request.form.get('current_designation', '').strip()
        industry = request.form.get('industry', '').strip()
        experience = float(request.form.get('work_experience_years', 0.0) or 0.0)
        linkedin = request.form.get('linkedin_url', '').strip()
        skills = request.form.get('skills', '').strip()
        bio = request.form.get('bio', '').strip()
        willing_to_mentor = 1 if request.form.get('willing_to_mentor') == 'on' else 0
        mentor_domains = request.form.get('mentor_domains', '').strip()
        
        cursor.execute(
            '''UPDATE alumni_profiles SET
                first_name=?, last_name=?, email=?, phone=?, alternative_phone=?,
                batch=?, course=?, department=?, graduation_year=?, cgpa=?, dob=?,
                address=?, city=?, state=?, country=?, postal_code=?,
                emergency_contact_name=?, emergency_contact_relation=?, emergency_contact_phone=?,
                current_company=?, current_designation=?, industry=?, work_experience_years=?,
                linkedin_url=?, skills=?, bio=?, willing_to_mentor=?, mentor_domains=?,
                updated_at=CURRENT_TIMESTAMP
               WHERE id = ?''',
            (first_name, last_name, email, phone, alt_phone,
             batch, course, department, graduation_year, cgpa, dob,
             address, city, state, country, postal_code,
             em_name, em_rel, em_phone,
             company, designation, industry, experience,
             linkedin, skills, bio, willing_to_mentor, mentor_domains, id)
        )
        conn.commit()
        log_audit(session['user_id'], session['user_name'], 'DIRECT_UPDATE_ALUMNI', 'AlumniProfile', id, f"Admin updated record for {first_name} {last_name}", request.remote_addr)
        conn.close()
        flash("Alumni record updated successfully.", "success")
        return redirect(url_for('alumni_view', id=id))
        
    conn.close()
    return render_template('alumni/edit.html', alumnus=alumnus)

@app.route('/alumni/my-profile')
@login_required
def my_profile():
    conn = get_db_connection()
    alumnus = conn.execute("SELECT * FROM alumni_profiles WHERE user_id = ?", (session['user_id'],)).fetchone()
    
    if not alumnus and session.get('user_role') == 'alumni':
        # Auto-link or find by email
        alumnus = conn.execute("SELECT * FROM alumni_profiles WHERE email = ?", (session.get('user_email'),)).fetchone()
        if alumnus:
            conn.execute("UPDATE alumni_profiles SET user_id = ? WHERE id = ?", (session['user_id'], alumnus['id']))
            conn.commit()
            
    pending_updates = []
    if alumnus:
        pending_updates = conn.execute(
            "SELECT * FROM pending_profile_updates WHERE alumni_id = ? AND status = 'pending'", (alumnus['id'],)
        ).fetchall()
        
    conn.close()
    return render_template('alumni/my_profile.html', alumnus=alumnus, pending_updates=pending_updates)

@app.route('/alumni/request-update', methods=['GET', 'POST'])
@login_required
def request_profile_update():
    """
    Module E: Admin Approval and Record Verification.
    Alumni can submit profile update requests. Proposed changes are stored
    separately in pending_profile_updates for admin review and approval.
    """
    conn = get_db_connection()
    alumnus = conn.execute("SELECT * FROM alumni_profiles WHERE user_id = ? OR email = ?",
                           (session['user_id'], session.get('user_email'))).fetchone()
    if not alumnus:
        conn.close()
        flash("Alumni record not linked with your account. Please contact the administrator.", "warning")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        reason = request.form.get('update_reason', 'Profile details modification request.').strip()
        
        # Check what fields have changed
        possible_fields = [
            'phone', 'alternative_phone', 'address', 'city', 'state', 'postal_code',
            'current_company', 'current_designation', 'industry', 'work_experience_years',
            'linkedin_url', 'bio', 'skills', 'willing_to_mentor', 'mentor_domains',
            'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation'
        ]
        
        changes = {}
        for f in possible_fields:
            new_val = request.form.get(f)
            if f == 'willing_to_mentor':
                new_val = 1 if new_val == 'on' or new_val == '1' else 0
            if f == 'work_experience_years' and new_val:
                new_val = float(new_val)
                
            old_val = alumnus[f]
            if str(new_val or '').strip() != str(old_val or '').strip():
                changes[f] = new_val
                
        if not changes:
            conn.close()
            flash("No changes detected in the form. Please modify at least one field to submit.", "info")
            return redirect(url_for('request_profile_update'))
            
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO pending_profile_updates (alumni_id, requested_by_user_id, changes_json, reason, status)
               VALUES (?, ?, ?, ?, 'pending')''',
            (alumnus['id'], session['user_id'], json.dumps(changes), reason)
        )
        update_id = cursor.lastrowid
        conn.commit()
        
        log_audit(session['user_id'], session['user_name'], 'SUBMIT_UPDATE_REQUEST', 'PendingProfileUpdate', update_id,
                  f"Submitted {len(changes)} profile change(s) for admin approval.", request.remote_addr)
        conn.close()
        
        flash("Your profile update request has been submitted to the administrator for review!", "success")
        return redirect(url_for('my_profile'))
        
    conn.close()
    return render_template('alumni/request_update.html', alumnus=alumnus)

# -------------------------------------------------------------
# Module E: Admin Approval & Verification Portal
# -------------------------------------------------------------
@app.route('/approvals')
@login_required
@role_required(['admin'])
def approvals_list():
    conn = get_db_connection()
    status_filter = request.args.get('status', 'pending')
    
    sql = '''
        SELECT p.*, a.first_name, a.last_name, a.enrollment_no, a.email as alumni_email, a.course, a.batch,
               u.full_name as requester_name
        FROM pending_profile_updates p
        JOIN alumni_profiles a ON p.alumni_id = a.id
        JOIN users u ON p.requested_by_user_id = u.id
    '''
    if status_filter != 'all':
        sql += " WHERE p.status = ?"
        updates = conn.execute(sql + " ORDER BY p.created_at DESC", (status_filter,)).fetchall()
    else:
        updates = conn.execute(sql + " ORDER BY p.created_at DESC").fetchall()
        
    parsed_items = []
    for u in updates:
        parsed_items.append({
            'record': u,
            'changes': json.loads(u['changes_json']) if u['changes_json'] else {}
        })
        
    conn.close()
    return render_template('approvals/list.html', items=parsed_items, status_filter=status_filter)

@app.route('/approvals/<int:id>/action', methods=['POST'])
@login_required
@role_required(['admin'])
def approval_action(id):
    action = request.form.get('action') # 'approve' or 'reject'
    admin_comments = request.form.get('admin_comments', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    update_req = cursor.execute(
        "SELECT * FROM pending_profile_updates WHERE id = ?", (id,)
    ).fetchone()
    
    if not update_req or update_req['status'] != 'pending':
        conn.close()
        flash("Invalid or already processed update request.", "warning")
        return redirect(url_for('approvals_list'))
        
    alumnus = cursor.execute("SELECT * FROM alumni_profiles WHERE id = ?", (update_req['alumni_id'],)).fetchone()
    changes = json.loads(update_req['changes_json']) if update_req['changes_json'] else {}
    
    if action == 'approve':
        # Apply changes to alumni_profiles table
        set_clauses = []
        params = []
        for field, new_val in changes.items():
            set_clauses.append(f"{field} = ?")
            params.append(new_val)
            
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(update_req['alumni_id'])
        
        update_sql = f"UPDATE alumni_profiles SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(update_sql, params)
        
        # Update request status
        cursor.execute(
            '''UPDATE pending_profile_updates SET
                status = 'approved', admin_comments = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (admin_comments, session['user_id'], id)
        )
        
        # Log notification
        cursor.execute(
            '''INSERT INTO notifications_log (recipient_email, recipient_name, notification_type, subject, message_preview, status)
               VALUES (?, ?, 'profile_approval', 'Your Alumni Profile Update Request has been Approved!', ?, 'Sent')''',
            (alumnus['email'], f"{alumnus['first_name']} {alumnus['last_name']}",
             f"Admin approved changes to: {', '.join(changes.keys())}. {admin_comments}")
        )
        
        log_audit(session['user_id'], session['user_name'], 'APPROVE_PROFILE_UPDATE', 'PendingProfileUpdate', id,
                  f"Approved profile updates for {alumnus['first_name']} {alumnus['last_name']}", request.remote_addr)
        flash("Profile changes approved and official record successfully updated!", "success")
        
    elif action == 'reject':
        cursor.execute(
            '''UPDATE pending_profile_updates SET
                status = 'rejected', admin_comments = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (admin_comments, session['user_id'], id)
        )
        cursor.execute(
            '''INSERT INTO notifications_log (recipient_email, recipient_name, notification_type, subject, message_preview, status)
               VALUES (?, ?, 'profile_approval', 'Update on your Alumni Profile Change Request', ?, 'Sent')''',
            (alumnus['email'], f"{alumnus['first_name']} {alumnus['last_name']}",
             f"Update request was rejected. Admin feedback: {admin_comments or 'Insufficient verification info'}")
        )
        log_audit(session['user_id'], session['user_name'], 'REJECT_PROFILE_UPDATE', 'PendingProfileUpdate', id,
                  f"Rejected update request. Reason: {admin_comments}", request.remote_addr)
        flash("Profile update request has been rejected.", "info")
        
    conn.commit()
    conn.close()
    return redirect(url_for('approvals_list'))

# -------------------------------------------------------------
# Module B: Alumni Call Management
# -------------------------------------------------------------
@app.route('/calls')
@login_required
@role_required(['admin', 'staff'])
def calls_list():
    status_filter = request.args.get('status', '').strip()
    search_q = request.args.get('q', '').strip()
    
    conn = get_db_connection()
    sql = '''
        SELECT c.*, a.first_name, a.last_name, a.enrollment_no, a.email as alumni_email, a.phone as alumni_phone, a.course, a.batch
        FROM call_logs c
        JOIN alumni_profiles a ON c.alumni_id = a.id
        WHERE 1=1
    '''
    params = []
    if status_filter:
        sql += " AND c.status = ?"
        params.append(status_filter)
    if search_q:
        sql += " AND (a.first_name LIKE ? OR a.last_name LIKE ? OR c.purpose LIKE ? OR c.notes LIKE ?)"
        term = f"%{search_q}%"
        params.extend([term, term, term, term])
        
    sql += " ORDER BY c.call_date DESC, c.created_at DESC"
    calls = conn.execute(sql, params).fetchall()
    
    # All alumni for log call dropdown
    all_alumni = conn.execute("SELECT id, first_name, last_name, enrollment_no, course, batch, phone FROM alumni_profiles ORDER BY first_name ASC").fetchall()
    conn.close()
    
    return render_template('calls/list.html', calls=calls, status_filter=status_filter, search_q=search_q, all_alumni=all_alumni)

@app.route('/calls/log', methods=['POST'])
@login_required
@role_required(['admin', 'staff'])
def log_call():
    alumni_id = int(request.form.get('alumni_id'))
    call_date = request.form.get('call_date', datetime.now().strftime('%Y-%m-%d'))
    call_time = request.form.get('call_time', datetime.now().strftime('%I:%M %p'))
    purpose = request.form.get('purpose', '').strip()
    outcome = request.form.get('outcome', '').strip()
    follow_up_date = request.form.get('follow_up_date', '').strip() or None
    notes = request.form.get('notes', '').strip()
    status = request.form.get('status', 'completed')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO call_logs (alumni_id, staff_id, staff_name, call_date, call_time, purpose, outcome, follow_up_date, notes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (alumni_id, session['user_id'], session['user_name'], call_date, call_time, purpose, outcome, follow_up_date, notes, status)
    )
    call_id = cursor.lastrowid
    conn.commit()
    
    log_audit(session['user_id'], session['user_name'], 'LOG_CALL', 'CallLog', call_id,
              f"Logged call with Alumnus ID #{alumni_id} - Outcome: {outcome}", request.remote_addr)
    conn.close()
    
    flash("Call interaction recorded successfully!", "success")
    return redirect(url_for('calls_list'))

# -------------------------------------------------------------
# Module C: Help Desk Management
# -------------------------------------------------------------
@app.route('/helpdesk')
@login_required
def helpdesk_list():
    status_filter = request.args.get('status', 'all')
    category_filter = request.args.get('category', 'all')
    assigned_filter = request.args.get('assigned', 'all')
    user_role = session.get('user_role')
    user_id = session.get('user_id')
    
    conn = get_db_connection()
    sql = "SELECT * FROM helpdesk_tickets WHERE 1=1"
    params = []
    
    # Alumni and students only see their own tickets unless admin/staff
    if user_role not in ['admin', 'staff']:
        sql += " AND requester_id = ?"
        params.append(user_id)
        
    if status_filter != 'all':
        sql += " AND status = ?"
        params.append(status_filter)
        
    if category_filter != 'all':
        sql += " AND category = ?"
        params.append(category_filter)

    if assigned_filter == 'unassigned':
        sql += " AND (assigned_to_id IS NULL OR assigned_to_id = '')"
    elif assigned_filter == 'me':
        sql += " AND assigned_to_id = ?"
        params.append(user_id)
        
    sql += " ORDER BY CASE WHEN status = 'Open' THEN 1 WHEN status = 'In Progress' THEN 2 ELSE 3 END, created_at DESC"
    tickets = conn.execute(sql, params).fetchall()
    
    # Counts
    base_user_clause = "" if user_role in ['admin', 'staff'] else f" WHERE requester_id = {user_id}"
    open_count = conn.execute(f"SELECT COUNT(*) FROM helpdesk_tickets {base_user_clause} {'AND' if base_user_clause else 'WHERE'} status = 'Open'").fetchone()[0]
    in_prog_count = conn.execute(f"SELECT COUNT(*) FROM helpdesk_tickets {base_user_clause} {'AND' if base_user_clause else 'WHERE'} status = 'In Progress'").fetchone()[0]
    resolved_count = conn.execute(f"SELECT COUNT(*) FROM helpdesk_tickets {base_user_clause} {'AND' if base_user_clause else 'WHERE'} status IN ('Resolved', 'Closed')").fetchone()[0]
    
    # Teachers list for assignment dropdown
    teachers_list = conn.execute(
        "SELECT id, full_name, email FROM users WHERE role IN ('admin', 'staff') ORDER BY full_name ASC"
    ).fetchall()
    
    conn.close()
    return render_template(
        'helpdesk/list.html',
        tickets=tickets,
        status_filter=status_filter,
        category_filter=category_filter,
        assigned_filter=assigned_filter,
        open_count=open_count,
        in_prog_count=in_prog_count,
        resolved_count=resolved_count,
        teachers_list=teachers_list
    )

@app.route('/helpdesk/new', methods=['GET', 'POST'])
@login_required
def helpdesk_create():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip()
        priority = request.form.get('priority', 'Medium')
        
        # AI Classification integration
        ai_res = AIEngine.classify_ticket(subject, description)
        if not category or category == 'auto':
            category = ai_res['suggested_category']
        if not priority or priority == 'auto':
            priority = ai_res['priority']
            
        ticket_no = f"TKT-{datetime.now().strftime('%Y')}-{datetime.now().strftime('%m%d%H%M%S')[-4:]}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO helpdesk_tickets (
                ticket_no, requester_id, requester_name, requester_email, requester_role,
                category, priority, subject, description, status, department,
                ai_suggested_category, ai_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?)''',
            (ticket_no, session['user_id'], session['user_name'], session.get('user_email', ''),
             session.get('user_role', 'student'), category, priority, subject, description,
             ai_res['department'], ai_res['suggested_category'], ai_res['confidence'])
        )
        tkt_id = cursor.lastrowid
        conn.commit()
        
        log_audit(session['user_id'], session['user_name'], 'CREATE_TICKET', 'HelpDeskTicket', tkt_id,
                  f"Created ticket #{ticket_no} - {category} ({priority})", request.remote_addr)
        conn.close()
        
        flash(f"Support ticket {ticket_no} submitted successfully! Our desk has received your request.", "success")
        return redirect(url_for('helpdesk_view', id=tkt_id))
        
    initial_category = request.args.get('category', '')
    return render_template('helpdesk/create.html', initial_category=initial_category)

@app.route('/helpdesk/<int:id>')
@login_required
def helpdesk_view(id):
    conn = get_db_connection()
    ticket = conn.execute("SELECT * FROM helpdesk_tickets WHERE id = ?", (id,)).fetchone()
    if not ticket:
        conn.close()
        flash("Ticket not found.", "warning")
        return redirect(url_for('helpdesk_list'))
        
    # Permission check: Requester or staff/admin
    if session.get('user_role') not in ['admin', 'staff'] and ticket['requester_id'] != session['user_id']:
        conn.close()
        flash("Unauthorized to view this ticket.", "danger")
        return redirect(url_for('helpdesk_list'))
        
    replies = conn.execute(
        "SELECT * FROM ticket_replies WHERE ticket_id = ? ORDER BY created_at ASC", (id,)
    ).fetchall()
    
    staff_users = conn.execute("SELECT id, full_name, email FROM users WHERE role IN ('admin', 'staff')").fetchall()
    conn.close()
    return render_template('helpdesk/view.html', ticket=ticket, replies=replies, staff_users=staff_users)

@app.route('/helpdesk/<int:id>/reply', methods=['POST'])
@login_required
def helpdesk_reply(id):
    message = request.form.get('message', '').strip()
    is_internal = 1 if request.form.get('is_internal_note') == 'on' and session.get('user_role') in ['admin', 'staff'] else 0
    new_status = request.form.get('new_status')
    
    if not message:
        flash("Reply message cannot be empty.", "warning")
        return redirect(url_for('helpdesk_view', id=id))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO ticket_replies (ticket_id, sender_id, sender_name, sender_role, message, is_internal_note)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (id, session['user_id'], session['user_name'], session.get('user_role', 'user'), message, is_internal)
    )
    
    if new_status:
        resolved_at = datetime.now() if new_status in ['Resolved', 'Closed'] else None
        cursor.execute(
            '''UPDATE helpdesk_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP, resolved_at = ?
               WHERE id = ?''',
            (new_status, resolved_at, id)
        )
    else:
        cursor.execute("UPDATE helpdesk_tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (id,))
        
    conn.commit()
    conn.close()
    flash("Reply posted successfully.", "success")
    return redirect(url_for('helpdesk_view', id=id))

@app.route('/helpdesk/<int:id>/update-meta', methods=['POST'])
@login_required
@role_required(['admin', 'staff'])
def helpdesk_update_meta(id):
    status = request.form.get('status')
    priority = request.form.get('priority')
    assigned_to_id = request.form.get('assigned_to_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    assigned_name = None
    if assigned_to_id:
        st_user = cursor.execute("SELECT full_name FROM users WHERE id = ?", (assigned_to_id,)).fetchone()
        if st_user:
            assigned_name = st_user['full_name']
            
    resolved_at = datetime.now() if status in ['Resolved', 'Closed'] else None
    
    cursor.execute(
        '''UPDATE helpdesk_tickets SET
            status = ?, priority = ?, assigned_to_id = ?, assigned_to_name = ?,
            resolved_at = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (status, priority, assigned_to_id or None, assigned_name, resolved_at, id)
    )
    conn.commit()
    conn.close()
    flash("Ticket details updated successfully.", "success")
    return redirect(url_for('helpdesk_view', id=id))

@app.route('/helpdesk/<int:id>/assign', methods=['POST'])
@login_required
@role_required(['admin'])
def helpdesk_assign_teacher(id):
    teacher_id = request.form.get('assigned_to_id')
    priority = request.form.get('priority')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    teacher_name = None
    if teacher_id:
        t_user = cursor.execute("SELECT full_name FROM users WHERE id = ?", (teacher_id,)).fetchone()
        if t_user:
            teacher_name = t_user['full_name']
            
    sql = "UPDATE helpdesk_tickets SET assigned_to_id = ?, assigned_to_name = ?, updated_at = CURRENT_TIMESTAMP"
    params = [teacher_id or None, teacher_name]
    if priority:
        sql += ", priority = ?"
        params.append(priority)
    sql += ", status = CASE WHEN status = 'Open' THEN 'In Progress' ELSE status END"
    sql += " WHERE id = ?"
    params.append(id)
    
    cursor.execute(sql, params)
    conn.commit()
    
    log_audit(
        user_id=session['user_id'],
        user_name=session['user_name'],
        action="ASSIGN_TEACHER",
        entity_type="helpdesk_tickets",
        entity_id=id,
        details=f"Admin assigned ticket #{id} to faculty {teacher_name or 'Unassigned'}"
    )
    conn.close()
    flash(f"Ticket #{id} assigned to {teacher_name or 'unassigned'} successfully.", "success")
    return redirect(request.referrer or url_for('helpdesk_list'))

# -------------------------------------------------------------
# Module D: Automated Birthday & Email Notifications
# -------------------------------------------------------------
@app.route('/communication/birthdays')
@login_required
@role_required(['admin', 'staff'])
def birthdays():
    conn = get_db_connection()
    
    # Today's date components
    today_month_day = datetime.now().strftime('-%m-%d')
    
    # Alumni having birthday today
    today_alumni = conn.execute(
        "SELECT * FROM alumni_profiles WHERE dob LIKE ?", (f"%{today_month_day}",)
    ).fetchall()
    
    # Sent birthday wishes logs
    sent_wishes = conn.execute(
        "SELECT * FROM notifications_log WHERE notification_type = 'birthday' ORDER BY sent_at DESC LIMIT 20"
    ).fetchall()
    
    # Default template preview
    template = conn.execute(
        "SELECT * FROM email_templates WHERE template_key = 'birthday_default'"
    ).fetchone()
    
    conn.close()
    return render_template(
        'communication/birthdays.html',
        today_alumni=today_alumni,
        sent_wishes=sent_wishes,
        template=template
    )

@app.route('/communication/birthdays/send-wishes', methods=['POST'])
@login_required
@role_required(['admin', 'staff'])
def send_birthday_wishes():
    """
    Automated Birthday Wish Execution:
    Identifies all alumni celebrating their birthday today and dispatches
    personalized greetings via email, recording them into notifications_log.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today_month_day = datetime.now().strftime('-%m-%d')
    today_alumni = cursor.execute(
        "SELECT * FROM alumni_profiles WHERE dob LIKE ?", (f"%{today_month_day}",)
    ).fetchall()
    
    template = cursor.execute(
        "SELECT * FROM email_templates WHERE template_key = 'birthday_default'"
    ).fetchone()
    
    count_sent = 0
    for alum in today_alumni:
        subj = template['subject_template'].format(
            institution_name=Config.INSTITUTION_NAME,
            first_name=alum['first_name'],
            last_name=alum['last_name']
        ) if template else f"Happy Birthday from {Config.INSTITUTION_NAME}! 🎂"
        
        body = template['body_template'].format(
            institution_name=Config.INSTITUTION_NAME,
            first_name=alum['first_name'],
            last_name=alum['last_name'],
            course=alum['course'],
            batch=alum['batch']
        ) if template else f"Dear {alum['first_name']}, Happy Birthday!"
        
        cursor.execute(
            '''INSERT INTO notifications_log (recipient_email, recipient_name, notification_type, subject, message_preview, status)
               VALUES (?, ?, 'birthday', ?, ?, 'Sent')''',
            (alum['email'], f"{alum['first_name']} {alum['last_name']}", subj, body[:250])
        )
        count_sent += 1
        
    conn.commit()
    log_audit(session['user_id'], session['user_name'], 'TRIGGER_BIRTHDAY_WISHES', 'Notification', None,
              f"Triggered automated birthday wishes to {count_sent} alumni celebrating today.", request.remote_addr)
    conn.close()
    
    flash(f"Success! Automated birthday greetings delivered to {count_sent} alumni celebrating today.", "success")
    return redirect(url_for('birthdays'))

@app.route('/communication/campaigns', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'staff'])
def campaigns():
    conn = get_db_connection()
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'post_announcement':
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            target = request.form.get('target_audience', 'all')
            event_date = request.form.get('event_date', '') or None
            is_pinned = 1 if request.form.get('is_pinned') == 'on' else 0
            
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO announcements (title, content, target_audience, author_id, author_name, event_date, is_pinned)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (title, content, target, session['user_id'], session['user_name'], event_date, is_pinned)
            )
            conn.commit()
            flash("Campus announcement published successfully!", "success")
            
        elif action == 'broadcast_email':
            subject = request.form.get('subject', '').strip()
            body = request.form.get('body', '').strip()
            target_course = request.form.get('target_course', 'all')
            
            # Find recipients
            sql = "SELECT first_name, last_name, email FROM alumni_profiles WHERE email IS NOT NULL"
            params = []
            if target_course != 'all':
                sql += " AND course = ?"
                params.append(target_course)
                
            recipients = conn.execute(sql, params).fetchall()
            cursor = conn.cursor()
            for r in recipients:
                cursor.execute(
                    '''INSERT INTO notifications_log (recipient_email, recipient_name, notification_type, subject, message_preview, status)
                       VALUES (?, ?, 'announcement', ?, ?, 'Sent')''',
                    (r['email'], f"{r['first_name']} {r['last_name']}", subject, body[:250])
                )
            conn.commit()
            flash(f"Broadcast campaign successfully queued and sent to {len(recipients)} alumni!", "success")
            
    announcements = conn.execute("SELECT * FROM announcements ORDER BY created_at DESC").fetchall()
    courses = [r[0] for r in conn.execute("SELECT DISTINCT course FROM alumni_profiles").fetchall() if r[0]]
    logs = conn.execute("SELECT * FROM notifications_log ORDER BY sent_at DESC LIMIT 15").fetchall()
    conn.close()
    
    return render_template('communication/campaigns.html', announcements=announcements, courses=courses, logs=logs)

@app.route('/communication/templates', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def email_templates():
    conn = get_db_connection()
    if request.method == 'POST':
        tid = request.form.get('template_id')
        subject = request.form.get('subject_template', '').strip()
        body = request.form.get('body_template', '').strip()
        
        conn.execute(
            '''UPDATE email_templates SET subject_template = ?, body_template = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (subject, body, tid)
        )
        conn.commit()
        flash("Email template updated successfully.", "success")
        
    templates = conn.execute("SELECT * FROM email_templates ORDER BY category, template_name").fetchall()
    conn.close()
    return render_template('communication/templates.html', templates=templates)

# -------------------------------------------------------------
# Module G: Excel Import, Export & PDF Reports
# -------------------------------------------------------------
@app.route('/reports')
@login_required
def report_center():
    conn = get_db_connection()
    batches = [r[0] for r in conn.execute("SELECT DISTINCT batch FROM alumni_profiles ORDER BY batch DESC").fetchall() if r[0]]
    courses = [r[0] for r in conn.execute("SELECT DISTINCT course FROM alumni_profiles ORDER BY course").fetchall() if r[0]]
    conn.close()
    return render_template('reports/index.html', batches=batches, courses=courses)

@app.route('/reports/alumni/pdf')
@login_required
def export_alumni_pdf():
    batch = request.args.get('batch')
    course = request.args.get('course')
    
    conn = get_db_connection()
    sql = "SELECT * FROM alumni_profiles WHERE 1=1"
    params = []
    title = "Official Alumni Directory Report"
    
    if batch:
        sql += " AND (batch LIKE ? OR graduation_year = ?)"
        params.extend([f"%{batch}%", batch])
        title += f" - Batch {batch}"
    if course:
        sql += " AND course LIKE ?"
        params.append(f"%{course}%")
        title += f" - {course}"
        
    sql += " ORDER BY graduation_year DESC, first_name ASC"
    alumni = conn.execute(sql, params).fetchall()
    conn.close()
    
    filename = generate_alumni_directory_pdf(alumni, title=title)
    filepath = get_report_filepath(filename)
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/reports/calls/pdf')
@login_required
@role_required(['admin', 'staff'])
def export_calls_pdf():
    conn = get_db_connection()
    sql = '''
        SELECT c.*, a.first_name, a.last_name, a.course, a.batch
        FROM call_logs c
        JOIN alumni_profiles a ON c.alumni_id = a.id
        ORDER BY c.call_date DESC
    '''
    calls = conn.execute(sql).fetchall()
    conn.close()
    
    filename = generate_call_report_pdf(calls)
    filepath = get_report_filepath(filename)
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/reports/alumni/excel')
@login_required
def export_alumni_excel():
    conn = get_db_connection()
    alumni = conn.execute("SELECT * FROM alumni_profiles ORDER BY graduation_year DESC, first_name ASC").fetchall()
    conn.close()
    
    filename = export_alumni_to_excel(alumni)
    filepath = get_report_filepath(filename)
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/reports/template/excel')
@login_required
def download_excel_template():
    filename = generate_excel_sample_template()
    filepath = get_report_filepath(filename)
    return send_file(filepath, as_attachment=True, download_name=filename)

@app.route('/alumni/import', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def alumni_import():
    """
    Excel Import functionality:
    Validates uploaded spreadsheet, performs duplicate checks,
    and bulk inserts records.
    """
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash("No file part in request.", "warning")
            return redirect(url_for('alumni_import'))
            
        file = request.files['excel_file']
        if file.filename == '':
            flash("No file selected.", "warning")
            return redirect(url_for('alumni_import'))
            
        if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls') or file.filename.endswith('.csv')):
            flash("Only Excel (.xlsx, .xls) or CSV files are supported.", "danger")
            return redirect(url_for('alumni_import'))
            
        filename = secure_filename(file.filename)
        save_path = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(save_path)
        
        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(save_path)
            else:
                df = pd.read_excel(save_path)
                
            df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            existing_enrollments = {r[0] for r in cursor.execute("SELECT enrollment_no FROM alumni_profiles").fetchall()}
            existing_emails = {r[0].lower() for r in cursor.execute("SELECT email FROM alumni_profiles WHERE email IS NOT NULL").fetchall()}
            
            inserted = 0
            duplicates_skipped = 0
            errors = []
            
            for idx, row in df.iterrows():
                try:
                    enrollment_no = str(row.get('enrollment_no') or f"EN-IMP-{idx+1}").strip()
                    email = str(row.get('email') or '').strip().lower()
                    first_name = str(row.get('first_name') or 'Alum').strip()
                    last_name = str(row.get('last_name') or '').strip()
                    
                    if enrollment_no in existing_enrollments or email in existing_emails:
                        duplicates_skipped += 1
                        continue
                        
                    batch = str(row.get('batch') or '2020-2024')
                    course = str(row.get('course') or 'B.Tech')
                    dept = str(row.get('department') or 'Engineering')
                    grad_year = int(row.get('graduation_year') or 2024)
                    phone = str(row.get('phone') or '')
                    city = str(row.get('city') or '')
                    company = str(row.get('current_company') or '')
                    role = str(row.get('current_designation') or '')
                    dob = str(row.get('dob') or '')
                    if 'nan' in dob.lower():
                        dob = None
                        
                    cursor.execute(
                        '''INSERT INTO alumni_profiles (
                            enrollment_no, first_name, last_name, email, phone,
                            batch, course, department, graduation_year, dob,
                            city, current_company, current_designation, willing_to_mentor
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                        (enrollment_no, first_name, last_name, email, phone,
                         batch, course, dept, grad_year, dob,
                         city, company, role)
                    )
                    inserted += 1
                    existing_enrollments.add(enrollment_no)
                    existing_emails.add(email)
                except Exception as row_err:
                    errors.append(f"Row {idx+2}: {str(row_err)}")
                    
            conn.commit()
            log_audit(session['user_id'], session['user_name'], 'IMPORT_EXCEL', 'AlumniProfile', None,
                      f"Imported {inserted} records. Skipped {duplicates_skipped} duplicates.", request.remote_addr)
            conn.close()
            
            flash(f"Import complete! {inserted} new alumni records inserted. {duplicates_skipped} duplicates skipped.", "success")
            if errors:
                flash(f"Encountered {len(errors)} row warning(s): {errors[0]}", "warning")
            return redirect(url_for('alumni_list'))
            
        except Exception as e:
            flash(f"Failed to process Excel file: {str(e)}", "danger")
            return redirect(url_for('alumni_import'))
            
    return render_template('alumni/import.html')

# -------------------------------------------------------------
# Module: AI Features (Chatbot, Duplicates, Mentorship, APIs)
# -------------------------------------------------------------
@app.route('/alumni/duplicates')
@login_required
@role_required(['admin'])
def duplicate_records():
    """
    AI Duplicate Record Detection:
    Scans entire database, compares enrollment numbers, emails,
    phone numbers, and fuzzy name similarity to flag duplicates.
    """
    conn = get_db_connection()
    alumni = conn.execute("SELECT * FROM alumni_profiles ORDER BY id ASC").fetchall()
    conn.close()
    
    duplicates = AIEngine.detect_duplicates(alumni)
    return render_template('alumni/duplicates.html', duplicates=duplicates, total_scanned=len(alumni))

@app.route('/mentorship/network')
@login_required
def mentorship_network():
    """
    AI-Based Alumni Networking & Mentorship Matching:
    Ranks alumni mentors based on user course, career interests, and skills.
    """
    conn = get_db_connection()
    
    student_course = request.args.get('course', '')
    student_interest = request.args.get('interest', '')
    target_company = request.args.get('target_company', '')
    
    # If student is logged in, pull course from user account
    if not student_course and session.get('user_role') == 'student':
        student_course = 'B.Tech'
        
    mentors = conn.execute(
        "SELECT * FROM alumni_profiles WHERE willing_to_mentor = 1 ORDER BY work_experience_years DESC"
    ).fetchall()
    
    student_profile = {
        'course': student_course,
        'interest': student_interest,
        'target_company': target_company
    }
    
    ranked_mentors = AIEngine.match_mentors(student_profile, mentors)
    
    # Existing connections for current user
    my_requests = []
    if 'user_id' in session:
        my_requests = conn.execute(
            '''SELECT m.*, a.first_name, a.last_name, a.current_company, a.current_designation
               FROM mentorship_connections m
               JOIN alumni_profiles a ON m.mentor_alumni_id = a.id
               WHERE m.student_user_id = ?''',
            (session['user_id'],)
        ).fetchall()
        
    conn.close()
    return render_template(
        'mentorship/network.html',
        ranked_mentors=ranked_mentors,
        student_profile=student_profile,
        my_requests=my_requests
    )

@app.route('/mentorship/request/<int:mentor_id>', methods=['POST'])
@login_required
def request_mentorship(mentor_id):
    msg = request.form.get('message', 'I would appreciate your mentorship and guidance for my career.').strip()
    course = request.form.get('course', 'Engineering Student')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO mentorship_connections (mentor_alumni_id, student_user_id, student_name, student_course, message, status)
           VALUES (?, ?, ?, ?, ?, 'requested')''',
        (mentor_id, session['user_id'], session['user_name'], course, msg)
    )
    conn.commit()
    conn.close()
    
    flash("Mentorship request sent! The alumnus will be notified.", "success")
    return redirect(url_for('mentorship_network'))

@app.route('/mentorship/connection/<int:id>/action', methods=['POST'])
@login_required
def mentorship_connection_action(id):
    action = request.form.get('action')  # 'accepted' or 'declined'
    if action not in ['accepted', 'declined']:
        flash("Invalid action.", "warning")
        return redirect(request.referrer or url_for('index'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    conn_req = cursor.execute('''
        SELECT m.*, a.user_id as mentor_user_id, a.first_name, a.last_name
        FROM mentorship_connections m
        JOIN alumni_profiles a ON m.mentor_alumni_id = a.id
        WHERE m.id = ?
    ''', (id,)).fetchone()
    
    if not conn_req:
        conn.close()
        flash("Mentorship connection not found.", "warning")
        return redirect(request.referrer or url_for('index'))
        
    if session.get('user_role') != 'admin' and conn_req['mentor_user_id'] != session['user_id']:
        conn.close()
        flash("Unauthorized to update this mentorship request.", "danger")
        return redirect(request.referrer or url_for('index'))
        
    cursor.execute("UPDATE mentorship_connections SET status = ? WHERE id = ?", (action, id))
    conn.commit()
    conn.close()
    
    msg = "accepted! The student has been notified to connect with you." if action == 'accepted' else "declined."
    flash(f"Mentorship request has been {msg}", "success" if action == 'accepted' else "info")
    return redirect(request.referrer or url_for('index'))

@app.route('/api/ai/chatbot', methods=['POST'])
def api_chatbot():
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message cannot be empty'}), 400
        
    response = AIEngine.answer_chatbot_query(message, user_context=session)
    return jsonify(response)

@app.route('/api/ai/classify-ticket', methods=['POST'])
def api_classify_ticket():
    data = request.get_json() or {}
    subject = data.get('subject', '').strip()
    desc = data.get('description', '').strip()
    result = AIEngine.classify_ticket(subject, desc)
    return jsonify(result)

@app.route('/api/ai/draft-email', methods=['POST'])
@login_required
def api_draft_email():
    data = request.get_json() or {}
    purpose = data.get('purpose', 'announcement')
    tone = data.get('tone', 'Warm & Celebratory')
    notes = data.get('notes', '')
    
    details = {
        'institution': Config.INSTITUTION_NAME,
        'name': data.get('name', 'Distinguished Alum'),
        'notes': notes
    }
    draft = AIEngine.generate_email_draft(purpose, tone, details)
    return jsonify(draft)

# -------------------------------------------------------------
# Audit Logs
# -------------------------------------------------------------
@app.route('/audit-logs')
@login_required
@role_required(['admin'])
def audit_logs():
    conn = get_db_connection()
    logs = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100").fetchall()
    conn.close()
    return render_template('approvals/audit_logs.html', logs=logs)

# -------------------------------------------------------------
# Database setup on startup
# -------------------------------------------------------------
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='127.0.0.1', port=port, debug=debug_mode)
