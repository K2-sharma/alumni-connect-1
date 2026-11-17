# VIPS-TC Alumni Connect: Institutional Alumni & Query Management System
**Vivekananda Institute of Professional Studies - Technical Campus (VIPS-TC)**
*Affiliated to Guru Gobind Singh Indraprastha University (GGSIPU), Delhi*

---

## 🌟 Executive Overview
**VIPS-TC Alumni Connect** is a centralized, role-based institutional web platform designed according to academic guidelines. It replaces disparate spreadsheets and manual records with a unified, role-based platform that handles:
1. **Student Hub**: Browse alumni directory, connect via LinkedIn, and request 1-on-1 career and placement mentorship.
2. **Alumni Desk**: Raise official degree/transcript queries (duplicate degrees, WES foreign university transcripts, provisional certificates, corrections), track resolution, and guide junior students.
3. **Faculty / Teacher Desk**: Direct departmental alumni records access, 1-click complete database export in Microsoft Excel (`.xlsx`), and resolve queries assigned by the Admin.
4. **Director / Admin Hub**: Full institutional authority, pending profile update approvals, and assigning teachers/faculty to alumni tickets.
5. **AI-Based Capabilities**: Natural Language Smart Search, ticket auto-classification, and career mentorship matching.
6. **Reports & Exports**: Cryptographic PDF directory generation and Excel spreadsheet import/export with duplicate checks.

---

## 🛠️ Technology Stack
- **Backend**: Python 3.10+ / 3.12+ with Flask & WSGI
- **Database**: SQLite3 (structured relational schema with foreign key integrity)
- **Production Server**: Gunicorn (Linux/Cloud) or Waitress (Windows)
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons
- **PDF Generation**: ReportLab
- **Excel Processing**: Pandas, OpenPyXL
- **AI & NLP**: Custom NLP classification, SequenceMatcher similarity, and query parsing engines

---

## 🚀 Local Development

```bash
# 1. Install Dependencies
pip install -r requirements.txt

# 2. Run Flask App
python app.py
```
Visit: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🌐 Production Hosting & Deployment Guide

### Option 1: Cloud PaaS (Render / Railway / PythonAnywhere) - Recommended & Easiest
1. Push this repository to GitHub or GitLab.
2. Link the repository on **Render** (as a *Web Service*) or **Railway**.
3. Set the build and start commands:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app`
4. Set Environment Variables:
   - `SECRET_KEY`: Set a long random string (e.g. `openssl rand -hex 32`)
   - `FLASK_ENV`: `production`
5. Click **Deploy**. The platform automatically assigns a free SSL/HTTPS URL.

---

### Option 2: Linux VPS (Ubuntu / Debian / AWS EC2 / DigitalOcean)
On a standard Linux VPS:

```bash
# 1. Update system & install prerequisites
sudo apt update && sudo apt install -y python3-pip python3-venv nginx

# 2. Clone repository & create virtual environment
cd /var/www/alumni-connect
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Create Systemd Service (/etc/systemd/system/alumniconnect.service)
sudo tee /etc/systemd/system/alumniconnect.service > /dev/null <<EOF
[Unit]
Description=VIPS-TC Alumni Connect Gunicorn Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/alumni-connect
Environment="PATH=/var/www/alumni-connect/venv/bin"
Environment="SECRET_KEY=your-production-secret-key"
ExecStart=/var/www/alumni-connect/venv/bin/gunicorn --workers 4 --threads 2 --bind 127.0.0.1:5000 wsgi:app

[Install]
WantedBy=multi-user.target
EOF

# 4. Start & enable systemd service
sudo systemctl daemon-reload
sudo systemctl start alumniconnect
sudo systemctl enable alumniconnect

# 5. Configure Nginx Reverse Proxy (/etc/nginx/sites-available/alumniconnect)
sudo tee /etc/nginx/sites-available/alumniconnect > /dev/null <<EOF
server {
    listen 80;
    server_name alumni.vips.edu;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias /var/www/alumni-connect/static;
        expires 30d;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/alumniconnect /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# 6. Enable Free SSL with Let's Encrypt Certbot
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d alumni.vips.edu
```

---

### Option 3: Docker Container
Build and run anywhere with Docker:

```bash
# Build Docker image
docker build -t vips-alumni-connect .

# Run container
docker run -d -p 5000:5000 --name alumni-portal vips-alumni-connect
```

---

## 🧪 Automated Testing
```bash
python -m unittest test_app.py
```
*Result: 10/10 tests pass (WSGI endpoints, Role access, AI classification, Excel export, and Authentication).*
