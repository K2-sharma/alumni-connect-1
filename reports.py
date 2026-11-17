import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from config import Config

def get_report_filepath(filename):
    try:
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
    except Exception:
        pass
    return os.path.join(Config.REPORTS_FOLDER, filename)

class NumberedCanvas:
    """Helper for page numbering in ReportLab"""
    pass

def generate_alumni_directory_pdf(alumni_list, title="Official Alumni Directory", subtitle="Vivekananda Institute of Professional Studies - Technical Campus (VIPS-TC)"):
    filename = f"Alumni_Directory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = get_report_filepath(filename)
    
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    header_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        alignment=1, # Center
        fontName='Helvetica-Bold'
    )
    
    sub_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        alignment=1,
        fontName='Helvetica'
    )
    
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#64748B'),
        alignment=2 # Right
    )
    
    cell_head_style = ParagraphStyle(
        'CellHead',
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )
    
    cell_body_style = ParagraphStyle(
        'CellBody',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica'
    )
    
    story = []
    
    # Header Banner
    story.append(Paragraph(title, header_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(subtitle, sub_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')} | Total Records: {len(alumni_list)}", meta_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#8B1E28'), spaceAfter=12))
    
    # Table Data
    table_data = [[
        Paragraph("<b>Enrollment</b>", cell_head_style),
        Paragraph("<b>Full Name</b>", cell_head_style),
        Paragraph("<b>Course / Batch</b>", cell_head_style),
        Paragraph("<b>Email / Contact</b>", cell_head_style),
        Paragraph("<b>Current Organization</b>", cell_head_style),
        Paragraph("<b>Designation / Role</b>", cell_head_style),
        Paragraph("<b>Location</b>", cell_head_style)
    ]]
    
    for raw_a in alumni_list:
        a = dict(raw_a) if hasattr(raw_a, 'keys') else raw_a
        full_name = f"{a['first_name']} {a['last_name']}"
        course_batch = f"{a['course']} ({a['graduation_year']})<br/><font color='#64748b' size='7'>{a['department']}</font>"
        contact = f"{a['email']}<br/><font color='#64748b' size='7'>{a.get('phone') or 'N/A'}</font>"
        company = a.get('current_company') or 'Self-Employed / Other'
        role = a.get('current_designation') or 'Professional'
        location = f"{a.get('city') or 'India'}"
        
        table_data.append([
            Paragraph(a['enrollment_no'], cell_body_style),
            Paragraph(f"<b>{full_name}</b>", cell_body_style),
            Paragraph(course_batch, cell_body_style),
            Paragraph(contact, cell_body_style),
            Paragraph(company, cell_body_style),
            Paragraph(role, cell_body_style),
            Paragraph(location, cell_body_style)
        ])
        
    col_widths = [75, 95, 85, 110, 85, 75, 45]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8B1E28')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    story.append(t)
    
    doc.build(story)
    return filename

def generate_call_report_pdf(calls_list):
    filename = f"Call_Activity_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = get_report_filepath(filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0F172A'), alignment=1)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#475569'), alignment=1)
    cell_head = ParagraphStyle('CH', fontSize=8, textColor=colors.white, fontName='Helvetica-Bold')
    cell_body = ParagraphStyle('CB', fontSize=7.5, leading=9, textColor=colors.HexColor('#1E293B'))
    
    story = [
        Paragraph("Alumni Call & Outreach Activity Report", title_style),
        Spacer(1, 4),
        Paragraph(f"Generated on {datetime.now().strftime('%d %B %Y')} | Total Calls: {len(calls_list)}", sub_style),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0284C7'), spaceAfter=10)
    ]
    
    table_data = [[
        Paragraph("<b>Date / Time</b>", cell_head),
        Paragraph("<b>Alumnus Name</b>", cell_head),
        Paragraph("<b>Course / Batch</b>", cell_head),
        Paragraph("<b>Staff Caller</b>", cell_head),
        Paragraph("<b>Purpose</b>", cell_head),
        Paragraph("<b>Outcome</b>", cell_head),
        Paragraph("<b>Status</b>", cell_head),
        Paragraph("<b>Follow-up</b>", cell_head)
    ]]
    
    for raw_c in calls_list:
        c = dict(raw_c) if hasattr(raw_c, 'keys') else raw_c
        alum_name = f"{c.get('first_name', '')} {c.get('last_name', '')}"
        course_batch = f"{c.get('course', '')} ({c.get('batch', '')})"
        fup = c.get('follow_up_date') or '-'
        table_data.append([
            Paragraph(f"{c['call_date']}<br/>{c.get('call_time') or ''}", cell_body),
            Paragraph(f"<b>{alum_name}</b>", cell_body),
            Paragraph(course_batch, cell_body),
            Paragraph(c.get('staff_name', 'Coordinator'), cell_body),
            Paragraph(c.get('purpose', ''), cell_body),
            Paragraph(c.get('outcome', ''), cell_body),
            Paragraph(c.get('status', '').replace('_', ' ').title(), cell_body),
            Paragraph(fup, cell_body)
        ])
        
    col_widths = [65, 85, 75, 75, 80, 80, 60, 50]
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0369A1')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#BAE6FD')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F9FF')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    doc.build(story)
    return filename

def export_alumni_to_excel(alumni_list):
    filename = f"Alumni_Records_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = get_report_filepath(filename)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Alumni Database"
    
    # Styling definitions - Official VIPS Crimson Header
    header_fill = PatternFill(start_color="982929", end_color="982929", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    border_thin = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )
    
    headers = [
        "ID", "Enrollment No", "First Name", "Last Name", "Email", "Phone",
        "Alternative Phone", "Batch", "Course", "Department", "Graduation Year",
        "CGPA", "DOB (YYYY-MM-DD)", "City", "State", "Country",
        "Current Company", "Current Designation", "Industry", "Experience (Years)",
        "LinkedIn URL", "Willing To Mentor", "Mentor Domains", "Emergency Contact Name",
        "Emergency Contact Phone"
    ]
    
    ws.append(headers)
    
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    for raw_a in alumni_list:
        a = dict(raw_a) if hasattr(raw_a, 'keys') else raw_a
        row = [
            a.get('id'),
            a.get('enrollment_no'),
            a.get('first_name'),
            a.get('last_name'),
            a.get('email'),
            a.get('phone'),
            a.get('alternative_phone'),
            a.get('batch'),
            a.get('course'),
            a.get('department'),
            a.get('graduation_year'),
            a.get('cgpa'),
            a.get('dob'),
            a.get('city'),
            a.get('state'),
            a.get('country'),
            a.get('current_company'),
            a.get('current_designation'),
            a.get('industry'),
            a.get('work_experience_years'),
            a.get('linkedin_url'),
            "Yes" if a.get('willing_to_mentor') else "No",
            a.get('mentor_domains'),
            a.get('emergency_contact_name'),
            a.get('emergency_contact_phone')
        ]
        ws.append(row)
        
    # Auto-adjust column width
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        for cell in col[1:]:
            cell.font = data_font
            cell.border = border_thin
            
    wb.save(filepath)
    return filename

def generate_excel_sample_template():
    filename = "Alumni_Import_Template.xlsx"
    filepath = get_report_filepath(filename)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Import Template"
    
    header_fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    headers = [
        "enrollment_no", "first_name", "last_name", "email", "phone",
        "batch", "course", "department", "graduation_year", "cgpa", "dob",
        "city", "state", "country", "current_company", "current_designation",
        "industry", "work_experience_years", "linkedin_url", "willing_to_mentor",
        "emergency_contact_name", "emergency_contact_phone"
    ]
    
    ws.append(headers)
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        
    # Sample Row
    sample_row = [
        "EN2022MCA015", "Vikram", "Singhania", "vikram.singhania@example.com", "+91 98765 43210",
        "2020-2022", "MCA", "Computer Science", 2022, 8.9, "1999-04-12",
        "Bangalore", "Karnataka", "India", "Google India", "Software Engineer III",
        "Information Technology & Software", 4, "https://linkedin.com/in/vikram", "Yes",
        "Rajesh Singhania", "+91 98765 11223"
    ]
    ws.append(sample_row)
    
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)
        
    wb.save(filepath)
    return filename
