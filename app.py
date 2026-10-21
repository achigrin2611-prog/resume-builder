from flask import Flask, render_template, request, make_response, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
app.config['SECRET_KEY'] = 'resume-builder-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///resume.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============ ШРИФТЫ ДЛЯ РУССКОГО ЯЗЫКА ============
try:
    pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
    FONT_NAME = 'Arial'
    FONT_BOLD = 'Arial-Bold'
except:
    FONT_NAME = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'


# ============ МОДЕЛЬ ============
class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    summary = db.Column(db.Text)
    experience = db.Column(db.Text)
    education = db.Column(db.Text)
    skills = db.Column(db.Text)


# ============ РОУТЫ ============
@app.route('/')
def index():
    resume_id = session.get('resume_id')
    resume_data = None
    if resume_id:
        resume = Resume.query.get(resume_id)
        if resume:
            resume_data = {k: getattr(resume, k) for k in
                           ['name', 'email', 'phone', 'summary', 'experience', 'education', 'skills']}
    return render_template('index.html', data=resume_data)


@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    data = {
        'name': request.form.get('name', ''),
        'email': request.form.get('email', ''),
        'phone': request.form.get('phone', ''),
        'summary': request.form.get('summary', ''),
        'experience': request.form.get('experience', ''),
        'education': request.form.get('education', ''),
        'skills': request.form.get('skills', ''),
    }

    # Сохранение в БД (сессии)
    resume_id = session.get('resume_id')
    if resume_id:
        resume = Resume.query.get(resume_id) or Resume()
        db.session.add(resume)
    else:
        resume = Resume()
        db.session.add(resume)

    for k, v in data.items():
        setattr(resume, k, v)
    db.session.commit()
    session['resume_id'] = resume.id

    # Генерация PDF
    pdf_buffer = io.BytesIO()

    # Отступы страницы (0, чтобы темная полоса была впритык к краю)
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=0,
        leftMargin=0,
        topMargin=0,
        bottomMargin=0
    )

    # Стили
    styles = getSampleStyleSheet()

    # Стили для левой (темной) колонки
    style_name = ParagraphStyle('Name', parent=styles['Heading1'], fontName=FONT_BOLD, fontSize=18,
                                textColor=colors.white, spaceAfter=5, leading=22)
    style_contact = ParagraphStyle('Contact', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10,
                                   textColor=colors.HexColor('#cccccc'), spaceAfter=15)
    style_sidebar_title = ParagraphStyle('SidebarTitle', parent=styles['Heading2'], fontName=FONT_BOLD, fontSize=12,
                                         textColor=colors.HexColor('#a88cff'), spaceBefore=10, spaceAfter=5)
    style_sidebar_text = ParagraphStyle('SidebarText', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10,
                                        textColor=colors.white, leading=14)

    # Стили для правой (белой) колонки
    style_section = ParagraphStyle('Section', parent=styles['Heading2'], fontName=FONT_BOLD, fontSize=14,
                                   textColor=colors.HexColor('#1a1a2e'), spaceBefore=10, spaceAfter=5)
    style_text = ParagraphStyle('Text', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, leading=14,
                                textColor=colors.HexColor('#444444'))

    # --- Контент ЛЕВОЙ колонки ---
    left_col = []
    left_col.append(Paragraph(data['name'], style_name))

    contact_text = f"{data['email']}"
    if data['phone']:
        contact_text += f"<br/>{data['phone']}"
    left_col.append(Paragraph(contact_text, style_contact))

    if data['skills']:
        left_col.append(Paragraph("НАВЫКИ", style_sidebar_title))
        skills_list = [f"• {s.strip()}" for s in data['skills'].split(',')]
        left_col.append(Paragraph("<br/>".join(skills_list), style_sidebar_text))

    # --- Контент ПРАВОЙ колонки ---
    right_col = []
    if data['summary']:
        right_col.append(Paragraph("О СЕБЕ", style_section))
        right_col.append(Paragraph(data['summary'].replace('\n', '<br/>'), style_text))
        right_col.append(Spacer(1, 5 * mm))

    if data['experience']:
        right_col.append(Paragraph("ОПЫТ РАБОТЫ", style_section))
        right_col.append(Paragraph(data['experience'].replace('\n', '<br/>'), style_text))
        right_col.append(Spacer(1, 5 * mm))

    if data['education']:
        right_col.append(Paragraph("ОБРАЗОВАНИЕ", style_section))
        right_col.append(Paragraph(data['education'].replace('\n', '<br/>'), style_text))

    # --- Таблица, которая держит колонки (без жесткой высоты) ---
    data_table = [[left_col, right_col]]
    table = Table(data_table, colWidths=[70 * mm, 140 * mm])

    # Стили таблицы (цвета и отступы)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1a1a2e')),  # Темный фон слева
        ('BACKGROUND', (1, 0), (1, 0), colors.white),  # Белый фон справа
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        # Отступы для левой колонки
        ('LEFTPADDING', (0, 0), (0, 0), 15),
        ('RIGHTPADDING', (0, 0), (0, 0), 15),
        ('TOPPADDING', (0, 0), (0, 0), 30),
        # Отступы для правой колонки
        ('LEFTPADDING', (1, 0), (1, 0), 15),
        ('RIGHTPADDING', (1, 0), (1, 0), 15),
        ('TOPPADDING', (1, 0), (1, 0), 30),
    ]))

    # Функция для рисования фона на весь лист
    def draw_background(canvas, doc):
        canvas.saveState()
        # Рисуем темную полосу слева на всю высоту
        canvas.setFillColor(colors.HexColor('#1a1a2e'))
        canvas.rect(0, 0, 70 * mm, 297 * mm, fill=1, stroke=0)
        canvas.restoreState()

    # Собираем PDF с фоновым рисунком
    doc.build([table], onFirstPage=draw_background)

    pdf = pdf_buffer.getvalue()
    pdf_buffer.close()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=resume.pdf'
    return response


# ============ ЗАПУСК ============
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)