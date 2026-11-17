import re
from datetime import datetime
from difflib import SequenceMatcher

class AIEngine:
    @staticmethod
    def classify_ticket(subject: str, description: str):
        """
        AI Ticket Classification: Analyzes subject and message,
        suggests category, priority, confidence score, and department.
        """
        text = f"{subject} {description}".lower()
        
        categories = {
            'Certificates': {
                'keywords': ['transcript', 'degree', 'certificate', 'mark sheet', 'marksheet', 'provisional', 'migration', 'bonafide', 'attestation', 'diploma'],
                'dept': 'Registrar & Examination Cell'
            },
            'Placement Support': {
                'keywords': ['placement', 'job', 'referral', 'career', 'interview', 'internship', 'resume', 'hiring', 'recruitment', 'offer letter'],
                'dept': 'Training & Placement Office (TPO)'
            },
            'Alumni Records': {
                'keywords': ['profile', 'update email', 'change phone', 'enrollment', 'batch correction', 'record', 'address change', 'id card', 'portal login'],
                'dept': 'Alumni Relations Office'
            },
            'Mentorship': {
                'keywords': ['mentor', 'guidance', 'career advice', 'project guide', 'higher studies', 'gre', 'gate', 'cat', 'networking'],
                'dept': 'Student Mentorship Cell'
            },
            'Academic Assistance': {
                'keywords': ['syllabus', 'course material', 'recommendation letter', 'lor', 'faculty', 'research', 'phd', 'academic verification'],
                'dept': 'Academic Affairs'
            },
            'General Inquiries': {
                'keywords': ['reunion', 'event', 'guest lecture', 'donation', 'campus visit', 'hostel', 'membership', 'fees', 'contact'],
                'dept': 'Alumni Help Desk'
            }
        }
        
        best_category = 'General Inquiries'
        max_score = 0
        best_dept = 'Alumni Help Desk'
        
        for cat, data in categories.items():
            score = sum(text.count(kw) for kw in data['keywords'])
            # Subject has higher weight
            sub_score = sum(subject.lower().count(kw) * 2 for kw in data['keywords'])
            total_score = score + sub_score
            if total_score > max_score:
                max_score = total_score
                best_category = cat
                best_dept = data['dept']
                
        # Confidence calculation
        confidence = min(0.98, max(0.55, 0.50 + (max_score * 0.12))) if max_score > 0 else 0.50
        
        # Priority classification
        urgent_keywords = ['urgent', 'emergency', 'asap', 'immediately', 'critical', 'deadline today', 'tomorrow', 'visa', 'joining']
        high_keywords = ['important', 'soon', 'offer letter', 'interview date', 'application deadline', 'loss', 'expired']
        
        priority = 'Medium'
        if any(w in text for w in urgent_keywords):
            priority = 'Urgent'
        elif any(w in text for w in high_keywords):
            priority = 'High'
        elif len(text) < 40 and max_score <= 1:
            priority = 'Low'
            
        return {
            'suggested_category': best_category,
            'department': best_dept,
            'priority': priority,
            'confidence': round(confidence, 2),
            'matched_signals': max_score
        }

    @staticmethod
    def parse_natural_language_query(query: str):
        """
        Interprets natural language queries like:
        'Find alumni from the 2022 MCA batch working in software companies'
        or 'B.Tech CSE alumni in Bangalore working at Microsoft'
        or 'Rahul Sharma' or 'Data Engineer' or 'Mentors in Machine Learning'
        """
        raw = (query or '').strip()
        tokens = raw.lower()
        extracted = {
            'batch_year': None,
            'course': None,
            'department': None,
            'company': None,
            'location': None,
            'industry': None,
            'role': None,
            'mentor_only': False,
            'keywords': [],
            'raw_query': raw
        }
        
        # 1. Mentorship intent
        if re.search(r'\b(mentor|mentors|mentoring|mentorship|guidance|guide)\b', tokens):
            extracted['mentor_only'] = True
            tokens = re.sub(r'\b(mentor|mentors|mentoring|mentorship|guidance|guide)\b', ' ', tokens)

        # 2. Batch / Graduation year regex
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', tokens)
        if year_match:
            extracted['batch_year'] = year_match.group(1)
            tokens = re.sub(rf'\b{year_match.group(1)}\b', ' ', tokens)
            
        # 3. Courses normalization
        course_map = [
            (r'\b(b\.?\s*tech|btech|b\.?\s*e|be)\b', 'B.Tech'),
            (r'\b(m\.?\s*c\.?\s*a|mca)\b', 'MCA'),
            (r'\b(m\.?\s*b\.?\s*a|mba)\b', 'MBA'),
            (r'\b(m\.?\s*tech|mtech|m\.?\s*e|me)\b', 'M.Tech'),
            (r'\b(b\.?\s*c\.?\s*a|bca)\b', 'BCA'),
            (r'\b(b\.?\s*b\.?\s*a|bba)\b', 'BBA'),
            (r'\b(ph\.?\s*d|phd|doctorate)\b', 'Ph.D'),
            (r'\b(b\.?\s*sc|bsc)\b', 'B.Sc'),
            (r'\b(m\.?\s*sc|msc)\b', 'M.Sc')
        ]
        for pattern, canon in course_map:
            if re.search(pattern, tokens):
                extracted['course'] = canon
                tokens = re.sub(pattern, ' ', tokens)
                break
                
        # 4. Department / Major
        dept_map = [
            (r'\b(computer\s*science(\s*and\s*engineering)?|cse|cs)\b', 'Computer Science'),
            (r'\b(electronics(\s*(&|and)\s*communication)?|ece)\b', 'Electronics'),
            (r'\b(mechanical(\s*engineering)?|mech)\b', 'Mechanical'),
            (r'\b(civil(\s*engineering)?)\b', 'Civil'),
            (r'\b(management(\s*studies)?|business)\b', 'Management')
        ]
        for pattern, canon in dept_map:
            if re.search(pattern, tokens):
                extracted['department'] = canon
                tokens = re.sub(pattern, ' ', tokens)
                break

        # 5. Companies
        known_companies = [
            ('google', 'Google'),
            ('microsoft', 'Microsoft'),
            ('amazon', 'Amazon'),
            ('infosys', 'Infosys'),
            ('tcs', 'TCS'),
            ('tata motors', 'Tata Motors'),
            ('tata', 'Tata'),
            ('deloitte', 'Deloitte'),
            ('razorpay', 'Razorpay'),
            ('flipkart', 'Flipkart'),
            ('wipro', 'Wipro'),
            ('meta', 'Meta'),
            ('apple', 'Apple'),
            ('ibm', 'IBM'),
            ('accenture', 'Accenture'),
            ('adobe', 'Adobe'),
            ('oracle', 'Oracle')
        ]
        for comp_key, comp_canon in known_companies:
            if re.search(rf'\b{re.escape(comp_key)}\b', tokens):
                extracted['company'] = comp_canon
                tokens = re.sub(rf'\b{re.escape(comp_key)}\b', ' ', tokens)
                break

        # 6. Locations / Cities
        known_cities = [
            ('bangalore', 'Bangalore'),
            ('bengaluru', 'Bangalore'),
            ('hyderabad', 'Hyderabad'),
            ('pune', 'Pune'),
            ('mumbai', 'Mumbai'),
            ('delhi', 'Delhi'),
            ('noida', 'Noida'),
            ('gurugram', 'Gurugram'),
            ('gurgaon', 'Gurugram'),
            ('chennai', 'Chennai'),
            ('kolkata', 'Kolkata'),
            ('san francisco', 'San Francisco'),
            ('london', 'London'),
            ('seattle', 'Seattle')
        ]
        for city_key, city_canon in known_cities:
            if re.search(rf'\b{re.escape(city_key)}\b', tokens):
                extracted['location'] = city_canon
                tokens = re.sub(rf'\b{re.escape(city_key)}\b', ' ', tokens)
                break

        # 7. Explicit Roles / Designations
        roles = [
            (r'\b(software\s*engineers?|software\s*developers?|swe)\b', 'Software Engineer'),
            (r'\b(data\s*engineers?)\b', 'Data Engineer'),
            (r'\b(product\s*designers?|ui/ux\s*designers?|ux\s*designers?)\b', 'Product Designer'),
            (r'\b(management\s*consultants?|consultants?)\b', 'Management Consultant'),
            (r'\b(cloud\s*(solutions\s*)?architects?|solutions\s*architects?)\b', 'Cloud Solutions Architect'),
            (r'\b(systems\s*engineers?|senior\s*systems\s*engineers?)\b', 'Systems Engineer'),
            (r'\b(research\s*scientists?|researchers?)\b', 'Research Scientist')
        ]
        for pattern, role_name in roles:
            if re.search(pattern, tokens):
                extracted['role'] = role_name
                tokens = re.sub(pattern, ' ', tokens)
                break

        # 8. Industry (only if user explicitly mentions industry/sector)
        industries = [
            (r'\b(software(\s*companies|\s*firms|\s*industry)?|it\s*(companies|firms|sector|industry)?)\b', 'Information Technology & Software'),
            (r'\b(fintech|payments)\b', 'Fintech & Payments'),
            (r'\b(consulting(\s*firms|\s*companies)?)\b', 'Management Consulting'),
            (r'\b(cloud(\s*computing)?|devops)\b', 'Cloud Computing & DevOps'),
            (r'\b(data\s*science|artificial\s*intelligence|ai/ml|machine\s*learning)\b', 'Data Science & AI'),
            (r'\b(automotive|manufacturing|ev)\b', 'Automotive & Manufacturing'),
            (r'\b(banking|finance|investment)\b', 'Banking & Financial Services')
        ]
        for pattern, ind_name in industries:
            if re.search(pattern, tokens):
                extracted['industry'] = ind_name
                tokens = re.sub(pattern, ' ', tokens)
                break

        # 9. Clean remaining tokens
        stopwords = {
            'find', 'alumni', 'alum', 'from', 'batch', 'working', 'in', 'at', 'the',
            'companies', 'company', 'with', 'who', 'are', 'and', 'for', 'of',
            'year', 'years', 'graduates', 'graduated', 'students', 'student', 'firm', 'firms',
            'based', 'living', 'show', 'get', 'search', 'list', 'all', 'me', 'profiles',
            'person', 'people', 'having', 'whose', 'located', 'call', 'works'
        }
        raw_words = [w.strip() for w in re.split(r'[^a-zA-Z0-9\+\#\.]+', tokens) if len(w.strip()) > 1]
        remaining = [w for w in raw_words if w.lower() not in stopwords]
        extracted['keywords'] = remaining
        
        return extracted

    @staticmethod
    def detect_duplicates(records):
        """
        Detects duplicate alumni records by enrollment_no, email, phone,
        or fuzzy similarity in First Name + Last Name + Batch.
        records: list of dicts/Rows
        """
        duplicates = []
        n = len(records)
        seen_pairs = set()

        for i in range(n):
            for j in range(i + 1, n):
                r1 = dict(records[i]) if hasattr(records[i], 'keys') else records[i]
                r2 = dict(records[j]) if hasattr(records[j], 'keys') else records[j]
                
                reasons = []
                score = 0.0
                
                # Check 1: Enrollment Number match
                if r1['enrollment_no'] and r2['enrollment_no'] and (r1['enrollment_no'].strip().upper() == r2['enrollment_no'].strip().upper()):
                    reasons.append(f"Identical Enrollment Number ({r1['enrollment_no']})")
                    score += 0.95
                    
                # Check 2: Email match
                if r1['email'] and r2['email'] and (r1['email'].strip().lower() == r2['email'].strip().lower()):
                    reasons.append(f"Matching Email ({r1['email']})")
                    score += 0.85
                    
                # Check 3: Phone match
                if r1['phone'] and r2['phone'] and (r1['phone'].strip() == r2['phone'].strip()):
                    reasons.append(f"Matching Phone Number ({r1['phone']})")
                    score += 0.70
                    
                # Check 4: Fuzzy Name match
                name1 = f"{r1['first_name']} {r1['last_name']}".strip().lower()
                name2 = f"{r2['first_name']} {r2['last_name']}".strip().lower()
                name_sim = SequenceMatcher(None, name1, name2).ratio()
                
                if name_sim >= 0.85:
                    if r1.get('batch') and r2.get('batch') and (r1['batch'] == r2['batch']):
                        reasons.append(f"High name similarity ({int(name_sim*100)}%) in same batch ({r1['batch']})")
                        score += 0.60
                    elif name_sim >= 0.92:
                        reasons.append(f"Very high name similarity ({int(name_sim*100)}%)")
                        score += 0.40
                        
                final_score = min(1.0, score)
                if final_score >= 0.60:
                    pair_key = tuple(sorted([r1['id'], r2['id']]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        duplicates.append({
                            'record_a': dict(r1),
                            'record_b': dict(r2),
                            'score': round(final_score * 100, 1),
                            'reasons': reasons
                        })
                        
        duplicates.sort(key=lambda x: x['score'], reverse=True)
        return duplicates

    @staticmethod
    def match_mentors(student_profile, alumni_mentors):
        """
        AI Mentor Recommendation:
        Ranks alumni mentors based on course alignment, target industry,
        skills, and mentorship experience.
        """
        scored_mentors = []
        target_course = (student_profile.get('course') or '').lower()
        target_interest = (student_profile.get('interest') or student_profile.get('skills') or '').lower()
        target_company = (student_profile.get('target_company') or '').lower()
        
        interest_tokens = [t.strip() for t in re.split(r'[,; ]+', target_interest) if t.strip()]
        
        for raw_mentor in alumni_mentors:
            mentor = dict(raw_mentor) if hasattr(raw_mentor, 'keys') else raw_mentor
            score = 20  # Base score for willing mentors
            reasons = []
            
            # Course alignment
            m_course = (mentor.get('course') or '').lower()
            if target_course and (target_course in m_course or m_course in target_course):
                score += 30
                reasons.append(f"Same academic background ({mentor['course']})")
                
            # Company alignment
            m_comp = (mentor.get('current_company') or '').lower()
            if target_company and target_company in m_comp:
                score += 25
                reasons.append(f"Works at target company ({mentor['current_company']})")
                
            # Skills & Domains alignment
            m_skills = f"{mentor.get('skills', '')} {mentor.get('mentor_domains', '')} {mentor.get('industry', '')}".lower()
            matched_skills = [tok for tok in interest_tokens if tok in m_skills]
            if matched_skills:
                skill_boost = min(35, len(matched_skills) * 12)
                score += skill_boost
                reasons.append(f"Aligned domain expertise: {', '.join(matched_skills[:3])}")
                
            # Experience seniority boost
            exp = mentor.get('work_experience_years', 0) or 0
            if exp >= 5:
                score += 15
                reasons.append(f"Experienced professional ({exp}+ years)")
            elif exp >= 2:
                score += 10
                reasons.append(f"Active practitioner ({exp} years)")
                
            final_match = min(99, score)
            scored_mentors.append({
                'mentor': dict(mentor),
                'match_percentage': int(final_match),
                'reasons': reasons or ["Alumni Mentor in Tech Community"]
            })
            
        scored_mentors.sort(key=lambda x: x['match_percentage'], reverse=True)
        return scored_mentors

    @staticmethod
    def generate_email_draft(purpose: str, tone: str, details: dict):
        """
        AI Email Drafter: Generates professional email drafts for announcements,
        reunions, birthdays, and call follow-ups with tone customization.
        """
        inst_name = details.get('institution', 'Vivekananda Institute of Professional Studies - Technical Campus (VIPS-TC)')
        alumni_name = details.get('name', 'Dear Alum')
        custom_notes = details.get('notes', '')
        
        subject = ""
        body = ""
        
        if purpose == 'birthday':
            subject = f"Warm Birthday Wishes from your Alma Mater, {inst_name}! 🎂"
            if tone == 'Warm & Celebratory':
                body = (
                    f"Dear {alumni_name},\n\n"
                    f"On behalf of the entire faculty, leadership, and alumni association at {inst_name}, "
                    f"we wish you a very Joyful and Happy Birthday!\n\n"
                    f"We take immense pride in your accomplishments and celebrate another wonderful year of your personal and professional journey. "
                    f"May this upcoming year be filled with success, good health, and memorable milestones.\n\n"
                    f"Stay connected with your alma mater!\n\n"
                    f"Warmest regards,\n"
                    f"Alumni Relations Office\n{inst_name}"
                )
            else:
                body = (
                    f"Dear {alumni_name},\n\n"
                    f"The Alumni Association of {inst_name} extends its sincere congratulations and best wishes on the occasion of your Birthday.\n\n"
                    f"We value your relationship with the institution and wish you continued excellence in your career.\n\n"
                    f"Sincerely,\n"
                    f"Director of Alumni Affairs\n{inst_name}"
                )
                
        elif purpose == 'reunion':
            subject = f"Annual Alumni Grand Reunion 2026 – Welcome Home to {inst_name}!"
            body = (
                f"Dear Alumni,\n\n"
                f"The halls, memories, and cherished connections of {inst_name} await your return!\n\n"
                f"We are thrilled to announce the Annual Alumni Grand Reunion scheduled for December 19-20, 2026. "
                f"Reunite with your batchmates, interact with inspiring faculty, explore the upgraded campus research centers, "
                f"and relive your college days.\n\n"
                f"Agenda Highlights:\n"
                f"• Keynote by distinguished alumni leaders\n"
                f"• Departmental breakout sessions & networking lunch\n"
                f"• Cultural night & Gala Dinner\n"
                f"• Student-Alumni Mentorship roundtables\n\n"
                f"{custom_notes}\n\n"
                f"Please confirm your attendance via the Alumni Portal by clicking the RSVP link.\n\n"
                f"With fond regards,\n"
                f"Organizing Committee, Alumni Association\n{inst_name}"
            )
            
        elif purpose == 'call_followup':
            subject = f"Follow-up: Connecting with {inst_name} Alumni Relations"
            body = (
                f"Dear {alumni_name},\n\n"
                f"Thank you for speaking with our alumni coordinator today. We greatly appreciated your insights and your continued interest in supporting {inst_name}.\n\n"
                f"As discussed during our conversation:\n"
                f"{custom_notes if custom_notes else '• We have recorded your updated contact preferences.\n• We look forward to your participation in our upcoming alumni initiatives.'}\n\n"
                f"If you require any assistance, transcripts, or institutional support, please feel free to reach out to us directly or through our Alumni Help Desk.\n\n"
                f"Best regards,\n"
                f"Alumni Engagement Team\n{inst_name}"
            )
            
        else: # general announcement
            subject = f"Important Announcement from {inst_name} Alumni Network"
            body = (
                f"Dear Alumni Community,\n\n"
                f"We are pleased to share an important update regarding {inst_name}:\n\n"
                f"{custom_notes if custom_notes else 'Our institution has recently achieved new milestones in academic rankings and student placement excellence.'}\n\n"
                f"We invite you to participate, share your mentorship expertise, and stay actively engaged with fellow alumni.\n\n"
                f"Warm regards,\n"
                f"Alumni Relations Office\n{inst_name}"
            )
            
        return {
            'subject': subject,
            'body': body
        }

    @staticmethod
    def answer_chatbot_query(message: str, user_context=None):
        """
        AI Alumni Help Desk Chatbot:
        Provides instant, intelligent responses to alumni services, certificates,
        events, profile update requests, and help desk procedures.
        """
        msg = message.lower().strip()
        
        # Knowledge Base of FAQ responses
        faqs = [
            {
                'triggers': ['transcript', 'degree', 'certificate', 'mark sheet', 'marksheet', 'provisional', 'bonafide'],
                'reply': "📜 **Transcript & Degree Certificates**:\n\nYou can request official transcripts and duplicate degree certificates directly via our **Help Desk**! Choose the category **'Certificates'**, upload your roll number/details, and the Registrar Office will process it within 3-5 business days. Both digital verified copies and hard-copy courier options are available.",
                'action': '/helpdesk/new?category=Certificates'
            },
            {
                'triggers': ['update profile', 'change phone', 'change email', 'edit details', 'update record', 'address'],
                'reply': "✏️ **Updating Your Alumni Profile**:\n\nTo ensure record accuracy and institutional security, all profile changes follow the **Admin Approval Workflow**.\n1. Go to **My Profile** -> Click **'Request Profile Update'**\n2. Modify your phone, address, or employment information\n3. Submit your request. Our administrator will verify and approve the changes within 24 hours!",
                'action': '/alumni/my-profile'
            },
            {
                'triggers': ['birthday', 'birthday wish', 'wishes', 'automated birthday'],
                'reply': "🎂 **Automated Birthday Notifications**:\n\nThe Alumni Connect system runs an automated birthday engine every morning at 08:00 AM. It identifies alumni celebrating their birthday today and delivers personalized greetings via email with official institutional regards!",
                'action': '/communication/birthdays'
            },
            {
                'triggers': ['reunion', 'event', 'alumni meet', 'gathering'],
                'reply': "🎉 **Alumni Reunions & Events**:\n\nOur Annual Grand Reunion is scheduled for December 2026. Check the **Announcements & Campaigns** module to view upcoming campus meets, batch-wise jubilee celebrations, and RSVP directly.",
                'action': '/communication/campaigns'
            },
            {
                'triggers': ['mentor', 'mentorship', 'guide student', 'become mentor', 'internship'],
                'reply': "🤝 **AI-Assisted Mentorship Network**:\n\nAlumni can offer career guidance, resume reviews, and internship referrals to current students. Visit the **Mentorship Network** tab to view student mentorship requests or toggle your 'Willing to Mentor' status in your profile!",
                'action': '/mentorship/network'
            },
            {
                'triggers': ['call', 'call log', 'follow-up', 'phone call'],
                'reply': "📞 **Alumni Call Management**:\n\nStaff and coordinators can record call interactions, log conversation outcomes (Interested, Follow-up Required, Completed), and schedule follow-up reminders in the **Alumni Call Management** module.",
                'action': '/calls'
            },
            {
                'triggers': ['export', 'excel', 'pdf', 'report', 'download'],
                'reply': "📊 **Excel & PDF Reports**:\n\nAuthorized administrators and staff can generate downloadable **PDF Alumni Directories, Call Logs, and Help Desk Reports** as well as export filtered alumni lists to Excel (.xlsx) from the **Report Center**.",
                'action': '/reports'
            },
            {
                'triggers': ['contact', 'help desk', 'ticket', 'support', 'query'],
                'reply': "🎫 **Help Desk Support**:\n\nYou can submit a support ticket anytime! Our AI automatically categorizes your request and routes it to the designated department. You can track ticket progress in real-time from your dashboard.",
                'action': '/helpdesk/new'
            }
        ]
        
        for item in faqs:
            for trigger in item['triggers']:
                if re.search(rf'\b{re.escape(trigger)}\b', msg):
                    return {
                        'reply': item['reply'],
                        'action_url': item.get('action'),
                        'suggested_questions': [
                            "How do I request an official transcript?",
                            "How does the profile update approval work?",
                            "How can I connect with alumni mentors?",
                            "Where can I download PDF reports?"
                        ]
                    }
                    
        # Default intelligent response
        return {
            'reply': f"Hello! I am your **AI Alumni Assistant** 🤖. I can assist you with:\n"
                     f"• Requesting academic transcripts and degree certificates\n"
                     f"• Updating your contact and employment records\n"
                     f"• Finding alumni mentors in your industry\n"
                     f"• Submitting and tracking help desk support tickets\n"
                     f"• Exploring upcoming reunion events and batch directories\n\n"
                     f"How may I help you today?",
            'action_url': '/helpdesk/new',
            'suggested_questions': [
                "How do I request an official transcript?",
                "How do I update my profile details?",
                "Show me alumni mentors in Software & Tech",
                "How do automated birthday emails work?"
            ]
        }
