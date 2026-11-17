import unittest
import json
import os
from app import app
from database import get_db_connection, init_db
from seed_data import seed_database
from ai_engine import AIEngine
from reports import generate_alumni_directory_pdf, export_alumni_to_excel

class AlumniConnectTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_unauthenticated_redirect(self):
        resp = self.app.get('/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_02_login_and_dashboard(self):
        # Standard production login as admin
        resp = self.app.post('/login', data={
            'email': 'admin@alumniconnect.edu',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Alumni Connect', resp.data)
        self.assertIn(b'Alumni Database', resp.data)

    def test_03_alumni_directory_and_smart_search(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Dr. Rajiv Menon'

        resp = self.app.get('/alumni')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Rahul Sharma', resp.data)

        # Smart Natural Language search
        nl_url = '/alumni?nl_query=Find+alumni+from+the+2022+MCA+batch+working+in+software+companies'
        resp_nl = self.app.get(nl_url)
        self.assertEqual(resp_nl.status_code, 200)
        self.assertIn(b'Priya Patel', resp_nl.data)

    def test_04_call_management(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Dr. Rajiv Menon'

        resp = self.app.get('/calls')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Annual Grand Reunion', resp.data)

    def test_05_helpdesk_and_ai_classifier(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Dr. Rajiv Menon'

        resp = self.app.get('/helpdesk')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'TKT-2026-1001', resp.data)

        # Test API Classification
        api_resp = self.app.post('/api/ai/classify-ticket', json={
            'subject': 'Urgent requirement for official degree certificate transcript',
            'description': 'I need my transcripts for visa processing by tomorrow.'
        })
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.get_json()
        self.assertEqual(data['suggested_category'], 'Certificates')
        self.assertEqual(data['priority'], 'Urgent')

    def test_06_birthday_automation(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Dr. Rajiv Menon'

        resp = self.app.get('/communication/birthdays')
        self.assertEqual(resp.status_code, 200)

        # Trigger birthday wishes
        post_resp = self.app.post('/communication/birthdays/send-wishes', follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)
        self.assertIn(b'Automated birthday greetings delivered', post_resp.data)

    def test_07_admin_approvals(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
            sess['user_name'] = 'Dr. Rajiv Menon'

        resp = self.app.get('/approvals')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Rahul Sharma', resp.data)

    def test_08_mentorship_matcher(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 7
            sess['user_role'] = 'student'
            sess['user_name'] = 'Arjun Verma'

        resp = self.app.get('/mentorship/network?course=MCA&interest=UI/UX+Design')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Priya Patel', resp.data)

    def test_09_pdf_and_excel_generation(self):
        conn = get_db_connection()
        alumni = conn.execute("SELECT * FROM alumni_profiles LIMIT 5").fetchall()
        conn.close()

        pdf_file = generate_alumni_directory_pdf(alumni)
        self.assertTrue(pdf_file.endswith('.pdf'))

        excel_file = export_alumni_to_excel(alumni)
        self.assertTrue(excel_file.endswith('.xlsx'))

    def test_10_ai_chatbot(self):
        api_resp = self.app.post('/api/ai/chatbot', json={'message': 'How can I get my degree certificate transcript?'})
        self.assertEqual(api_resp.status_code, 200)
        data = api_resp.get_json()
        self.assertIn('Transcript', data['reply'])

if __name__ == '__main__':
    unittest.main()
