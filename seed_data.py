import json
from datetime import datetime, date
from werkzeug.security import generate_password_hash
from database import get_db_connection, init_db

def seed_database():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if already seeded
    user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count > 0:
        conn.close()
        return
        
    print("Seeding initial database records...")
    
    # 1. Users
    pw_admin = generate_password_hash("admin123")
    pw_staff = generate_password_hash("staff123")
    pw_alumni = generate_password_hash("alumni123")
    pw_student = generate_password_hash("student123")
    
    users = [
        ('admin', 'admin@alumniconnect.edu', pw_admin, 'Dr. Rajiv Menon (Director / Admin)', 'admin', '+91 98111 00001', '👨‍💼'),
        ('coordinator', 'staff@alumniconnect.edu', pw_staff, 'Prof. Meera Nair (Faculty Coordinator)', 'staff', '+91 98111 00002', '👩‍💼'),
        ('prof_rajesh', 'rajesh.kumar@vips.edu', pw_staff, 'Prof. Rajesh Kumar (Examination & Degree Cell)', 'staff', '+91 98111 00003', '👨‍🏫'),
        ('rahul_s', 'rahul.sharma@example.com', pw_alumni, 'Rahul Sharma', 'alumni', '+91 98765 11111', '👨‍💻'),
        ('priya_p', 'priya.patel@example.com', pw_alumni, 'Priya Patel', 'alumni', '+91 98765 22222', '👩‍💻'),
        ('ananya_d', 'ananya.deshmukh@example.com', pw_alumni, 'Ananya Deshmukh', 'alumni', '+91 98765 33333', '👩‍💼'),
        ('karthik_r', 'karthik.ram@example.com', pw_alumni, 'Karthik Raman', 'alumni', '+91 98765 44444', '👨‍🔬'),
        ('arjun_v', 'arjun.verma@alumniconnect.edu', pw_student, 'Arjun Verma', 'student', '+91 98765 55555', '🎓')
    ]
    
    cursor.executemany(
        '''INSERT INTO users (username, email, password_hash, full_name, role, phone, avatar)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        users
    )
    conn.commit()
    
    # Fetch user IDs
    user_map = {row['email']: row['id'] for row in cursor.execute("SELECT id, email FROM users").fetchall()}
    
    # 2. Alumni Profiles
    # Note: November 11 is today's date in context, so setting Rahul Sharma and Neha Gupta's DOB to 11-11
    alumni_data = [
        (
            user_map.get('rahul.sharma@example.com'),
            'EN2018CSE042', 'Rahul', 'Sharma', 'rahul.sharma@example.com', '+91 98765 11111', '+91 98765 11110',
            'Flat 402, Green Glen Layout, Bellandur', 'Bangalore', 'Karnataka', 'India', '560103',
            '2018-2022', 'B.Tech', 'Computer Science and Engineering', 2022, 9.2, '1999-11-11', # Birthday today!
            'Sunil Sharma', 'Father', '+91 94111 22334',
            'Google India', 'Software Engineer III', 'Information Technology & Software', 4.5,
            'https://linkedin.com/in/rahul-sharma-tech',
            'Passionate backend and distributed systems engineer. Love mentoring aspiring software engineers.',
            'Python, Go, Distributed Systems, Kubernetes, Cloud Architecture',
            1, 'Backend Architecture, Cloud Systems, FAANG Interview Prep', 1, 0, 0
        ),
        (
            user_map.get('priya.patel@example.com'),
            'EN2020MCA018', 'Priya', 'Patel', 'priya.patel@example.com', '+91 98765 22222', '+91 98765 22220',
            'Tower B, Cyber City Residences, HITEC City', 'Hyderabad', 'Telangana', 'India', '500081',
            '2020-2022', 'MCA', 'Computer Science & Applications', 2022, 9.4, '1998-05-18',
            'Kishore Patel', 'Father', '+91 94111 33445',
            'Microsoft', 'Senior Product Designer', 'Information Technology & Software', 4.0,
            'https://linkedin.com/in/priya-patel-design',
            'UI/UX specialist focused on enterprise SaaS usability and design systems.',
            'Product Design, Figma, User Research, Design Systems, UX Strategy',
            1, 'UI/UX Design, Product Strategy, Portfolio Review', 1, 0, 0
        ),
        (
            user_map.get('ananya.deshmukh@example.com'),
            'EN2019MBA005', 'Ananya', 'Deshmukh', 'ananya.deshmukh@example.com', '+91 98765 33333', '+91 98765 33330',
            '12A Sea View Enclave, Worli', 'Mumbai', 'Maharashtra', 'India', '400018',
            '2019-2021', 'MBA', 'Management Studies', 2021, 8.8, '1997-08-24',
            'Sanjay Deshmukh', 'Father', '+91 94111 44556',
            'Deloitte Consulting', 'Management Consultant', 'Management Consulting', 5.0,
            'https://linkedin.com/in/ananya-deshmukh-consulting',
            'Strategy consultant specializing in digital transformation and financial operations.',
            'Business Strategy, Financial Modeling, Management Consulting, Agile Leadership',
            1, 'Consulting Case Prep, MBA Admissions, Career Transition', 1, 0, 0
        ),
        (
            user_map.get('karthik.ram@example.com'),
            'EN2017ECE089', 'Karthik', 'Raman', 'karthik.ram@example.com', '+91 98765 44444', '+91 98765 44440',
            'Sector 43, Golf Course Road', 'Gurugram', 'Haryana', 'India', '122002',
            '2017-2021', 'B.Tech', 'Electronics & Communication', 2021, 8.6, '1999-03-15',
            'V. Raman', 'Father', '+91 94111 55667',
            'Amazon AWS', 'Cloud Solutions Architect', 'Cloud Computing & DevOps', 5.2,
            'https://linkedin.com/in/karthik-raman-cloud',
            'Specialist in high-throughput cloud infrastructure and serverless systems.',
            'AWS, Terraform, DevOps, Python, Docker, Microservices',
            1, 'Cloud Certifications, DevOps Roadmap, Systems Design', 1, 0, 0
        ),
        (
            None,
            'EN2021MCA031', 'Neha', 'Gupta', 'neha.gupta@example.com', '+91 98765 66666', '+91 98765 66660',
            'Baner Road, Balewadi High Street', 'Pune', 'Maharashtra', 'India', '411045',
            '2021-2023', 'MCA', 'Computer Science & Applications', 2023, 9.1, '2000-11-11', # Birthday today!
            'Ramesh Gupta', 'Father', '+91 94111 66778',
            'Infosys Technologies', 'Senior Systems Engineer', 'Information Technology & Software', 3.0,
            'https://linkedin.com/in/neha-gupta-tech',
            'Full stack developer proficient in React, Node, and Python web architectures.',
            'React, Node.js, Express, MySQL, REST APIs',
            1, 'Web Development, Placement Coding Rounds', 1, 0, 0
        ),
        (
            None,
            'EN2018MECH014', 'Rohan', 'Verma', 'rohan.verma@example.com', '+91 98765 77777', '+91 98765 77770',
            'Anna Nagar West', 'Chennai', 'Tamil Nadu', 'India', '600040',
            '2018-2022', 'B.Tech', 'Mechanical Engineering', 2022, 8.3, '1999-09-30',
            'Mahesh Verma', 'Father', '+91 94111 77889',
            'Tata Motors', 'Senior Design Engineer', 'Automotive & Manufacturing', 4.0,
            'https://linkedin.com/in/rohan-verma-auto',
            'Automotive CAD designer with expertise in EV powertrain components.',
            'SolidWorks, CATIA, ANSYS, Product Development',
            0, 'Automotive Design, EV Systems', 1, 0, 0
        ),
        (
            None,
            'EN2019CSE099', 'Aditya', 'Chopra', 'aditya.chopra@example.com', '+91 98765 88888', '+91 98765 88880',
            'Koramangala 5th Block', 'Bangalore', 'Karnataka', 'India', '560095',
            '2019-2023', 'B.Tech', 'Computer Science and Engineering', 2023, 9.5, '2001-01-20',
            'Suresh Chopra', 'Father', '+91 94111 88990',
            'Razorpay', 'Data Engineer', 'Fintech & Payments', 3.2,
            'https://linkedin.com/in/aditya-chopra-data',
            'Building real-time payment ingestion pipelines and financial analytics cubes.',
            'Apache Spark, Kafka, Snowflake, Python, SQL',
            1, 'Big Data, Data Engineering Careers, SQL Interview Prep', 1, 0, 0
        ),
        (
            None,
            'EN2017MCA009', 'Siddharth', 'Nair', 'siddharth.nair@example.com', '+91 98765 99999', '+91 98765 99990',
            'Salt Lake City, Sector V', 'Kolkata', 'West Bengal', 'India', '700091',
            '2017-2019', 'MCA', 'Computer Science & Applications', 2019, 8.7, '1996-06-14',
            'G. Nair', 'Father', '+91 94111 99001',
            'TCS Research', 'Research Scientist', 'Information Technology & Software', 7.0,
            'https://linkedin.com/in/siddharth-nair-ai',
            'Applied NLP and machine learning researcher focusing on multilingual models.',
            'NLP, PyTorch, Transformers, LLMs, Machine Learning',
            1, 'AI/ML Research, Masters/PhD Guidance, Technical Publishing', 1, 0, 0
        )
    ]
    
    cursor.executemany(
        '''INSERT INTO alumni_profiles (
            user_id, enrollment_no, first_name, last_name, email, phone, alternative_phone,
            address, city, state, country, postal_code,
            batch, course, department, graduation_year, cgpa, dob,
            emergency_contact_name, emergency_contact_relation, emergency_contact_phone,
            current_company, current_designation, industry, work_experience_years,
            linkedin_url, bio, skills, willing_to_mentor, mentor_domains, is_verified,
            privacy_hide_phone, privacy_hide_family
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        alumni_data
    )
    conn.commit()
    
    # 3. Pending Profile Updates (Admin Approval Demo)
    rahul_profile = cursor.execute("SELECT id FROM alumni_profiles WHERE email = 'rahul.sharma@example.com'").fetchone()
    if rahul_profile:
        changes = {
            "current_designation": "Staff Software Engineer",
            "current_company": "Google LLC (Mountain View / Remote)",
            "work_experience_years": 5.0,
            "phone": "+91 98765 11999"
        }
        cursor.execute(
            '''INSERT INTO pending_profile_updates (alumni_id, requested_by_user_id, changes_json, reason, status)
               VALUES (?, ?, ?, ?, 'pending')''',
            (rahul_profile['id'], user_map['rahul.sharma@example.com'], json.dumps(changes), 'Promoted to Staff SWE and updated primary phone.')
        )
        
    # 4. Alumni Call Logs
    calls_data = [
        (
            1, user_map['staff@alumniconnect.edu'], 'Meera Nair', '2026-11-05', '03:30 PM',
            'Annual Grand Reunion 2026 Invitation', 'Interested', '2026-11-20',
            'Rahul expressed excitement to attend the reunion and offered to conduct an engineering tech talk.',
            'completed'
        ),
        (
            2, user_map['staff@alumniconnect.edu'], 'Meera Nair', '2026-11-08', '11:15 AM',
            'Student Mentorship Program Drive', 'Agreed to Participate', '2026-11-18',
            'Priya agreed to mentor 3 MCA students in UI/UX and product design. Follow-up to share student profiles.',
            'follow_up_required'
        ),
        (
            3, user_map['staff@alumniconnect.edu'], 'Meera Nair', '2026-11-09', '04:00 PM',
            'Department Endowment & Scholarship Drive', 'Left Voicemail', '2026-11-15',
            'Could not reach on mobile. Sent follow-up WhatsApp message and scheduled next call attempt.',
            'unanswered'
        ),
        (
            4, user_map['staff@alumniconnect.edu'], 'Meera Nair', '2026-11-10', '02:00 PM',
            'Guest Lecture Series in Cloud Computing', 'Completed & Confirmed', None,
            'Karthik confirmed virtual lecture on AWS Cloud Patterns on Dec 5th.',
            'completed'
        )
    ]
    cursor.executemany(
        '''INSERT INTO call_logs (alumni_id, staff_id, staff_name, call_date, call_time, purpose, outcome, follow_up_date, notes, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        calls_data
    )
    
    # 5. Help Desk Tickets
    tickets_data = [
        (
            'TKT-2026-1001', user_map.get('priya.patel@example.com'), 'Priya Patel', 'priya.patel@example.com', 'alumni',
            'Certificates', 'Urgent', 'Request for Official Digital Transcripts for Higher Education Visa',
            'I need sealed official academic transcripts for my Canadian PR and higher education application. The submission deadline is Nov 25th. Kindly issue digital verified copies.',
            'In Progress', user_map.get('staff@alumniconnect.edu'), 'Meera Nair', 'Registrar & Examination Cell',
            'Certificates', 0.95
        ),
        (
            'TKT-2026-1002', user_map.get('arjun.verma@alumniconnect.edu'), 'Arjun Verma', 'arjun.verma@alumniconnect.edu', 'student',
            'Placement Support', 'High', 'Guidance for Upcoming Google Campus Placement Drive',
            'I am preparing for the upcoming campus recruitment drive. Could the alumni cell connect me with alumni currently working at Google for interview advice and coding rounds preparation?',
            'Open', None, None, 'Training & Placement Office (TPO)',
            'Placement Support', 0.92
        ),
        (
            'TKT-2026-1003', user_map.get('rahul.sharma@example.com'), 'Rahul Sharma', 'rahul.sharma@example.com', 'alumni',
            'Alumni Records', 'Medium', 'Correction in Degree Name on Institutional Record',
            'My graduation degree on the portal reflects B.Tech (General) whereas my major specialization was Computer Science and Engineering. Request correction.',
            'Resolved', user_map.get('admin@alumniconnect.edu'), 'Dr. Rajiv Menon', 'Alumni Relations Office',
            'Alumni Records', 0.88
        )
    ]
    cursor.executemany(
        '''INSERT INTO helpdesk_tickets (
            ticket_no, requester_id, requester_name, requester_email, requester_role,
            category, priority, subject, description, status, assigned_to_id, assigned_to_name,
            department, ai_suggested_category, ai_confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        tickets_data
    )
    
    # Ticket Replies
    tkt_1 = cursor.execute("SELECT id FROM helpdesk_tickets WHERE ticket_no = 'TKT-2026-1001'").fetchone()[0]
    cursor.execute(
        '''INSERT INTO ticket_replies (ticket_id, sender_id, sender_name, sender_role, message)
           VALUES (?, ?, ?, ?, ?)''',
        (tkt_1, user_map['staff@alumniconnect.edu'], 'Meera Nair', 'staff',
         'Hello Priya, we have verified your request. The examination cell is generating your cryptographically stamped digital transcript. It will be emailed to your registered address by tomorrow noon.')
    )
    
    # 6. Email Templates
    templates = [
        (
            'Personalized Birthday Greeting', 'birthday_default',
            'Warm Birthday Wishes from your Alma Mater, {institution_name}! 🎂',
            '''Dear {first_name},

On behalf of the administration, faculty, and alumni body of {institution_name}, we wish you a joyous and fulfilling Birthday!

We celebrate your ongoing success and take immense pride in having you as a distinguished member of our alumni community.

May the year ahead bring you wonderful opportunities, good health, and continued triumphs.

Warm regards,
Alumni Relations Directorate
{institution_name}''',
            'birthday'
        ),
        (
            'Alumni Grand Reunion Invitation', 'reunion_invite',
            'Invitation: Annual Grand Alumni Reunion 2026 at {institution_name}',
            '''Dear {first_name},

It is our great pleasure to invite you to the Annual Grand Alumni Reunion 2026, taking place on December 19-20 on campus!

Catch up with old friends, meet current students, and witness the growth of your alma mater.

Please RSVP through your Alumni Connect portal. We cannot wait to welcome you back home!

Sincerely,
Organizing Committee
{institution_name}''',
            'announcement'
        ),
        (
            'Call Follow-up Note', 'call_followup',
            'Thank you for speaking with {institution_name} Alumni Relations',
            '''Dear {first_name},

Thank you for your valuable time on our phone conversation today. It was wonderful connecting with you.

We have noted your feedback and preferences. Should you need any assistance with alumni services or mentorship initiatives, our desk is always here to assist.

Best regards,
Alumni Outreach Office
{institution_name}''',
            'call'
        )
    ]
    cursor.executemany(
        '''INSERT INTO email_templates (template_name, template_key, subject_template, body_template, category)
           VALUES (?, ?, ?, ?, ?)''',
        templates
    )
    
    # 7. Announcements
    announcements = [
        (
            '🎉 Annual Alumni Grand Reunion 2026 Registrations Open!',
            'We are thrilled to welcome all alumni back to campus on December 19-20, 2026. Special silver jubilee felicitations for the 2001 batch and decennial meet for the 2016 batch. RSVP today via the portal!',
            'all', user_map['admin@alumniconnect.edu'], 'Dr. Rajiv Menon', '2026-12-19', 1
        ),
        (
            '🚀 Alumni-Led Campus Mentorship Drive: Fall 2026',
            'Attention students and alumni! We are launching our 1-on-1 industry mentorship cohort connecting senior alumni working in FAANG, top consultancies, and core engineering firms with 3rd and 4th-year students.',
            'all', user_map['staff@alumniconnect.edu'], 'Meera Nair', '2026-11-25', 1
        ),
        (
            '📜 Express Digital Transcript Dispatch Launched',
            'Alumni can now request and receive tamper-proof, verifiable digital transcripts within 48 hours directly via our Help Desk portal.',
            'alumni', user_map['admin@alumniconnect.edu'], 'Dr. Rajiv Menon', '2026-11-15', 0
        )
    ]
    cursor.executemany(
        '''INSERT INTO announcements (title, content, target_audience, author_id, author_name, event_date, is_pinned)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        announcements
    )
    
    # 8. Mentorship Connections
    priya_alumni_id = cursor.execute("SELECT id FROM alumni_profiles WHERE email = 'priya.patel@example.com'").fetchone()[0]
    cursor.execute(
        '''INSERT INTO mentorship_connections (mentor_alumni_id, student_user_id, student_name, student_course, message, status)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (priya_alumni_id, user_map['arjun.verma@alumniconnect.edu'], 'Arjun Verma', 'B.Tech CSE 3rd Year',
         'Hello Priya Ma\'am, I am interested in UI/UX systems and front-end design engineering. Would love your guidance on building an industry portfolio!', 'accepted')
    )
    
    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == '__main__':
    seed_database()
