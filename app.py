from flask import Flask, render_template, request, make_response, session
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

import reportlab

app = Flask(__name__)
app.config['SECRET_KEY'] = 'resume-builder-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///resume.db'
).replace('postgres://', 'postgresql+psycopg2://').replace('postgresql://', 'postgresql+psycopg2://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============ ШРИФТЫ (ЖЕЛЕЗОБЕТОННО) ============
try:
    # Берем шрифты из папки reportlab
    base_path = os.path.dirname(reportlab.__file__)
    font_path = os.path.join(base_path, 'fonts', 'DejaVuSans.ttf')
    font_bold_path = os.path.join(base_path, 'fonts', 'DejaVuSans-Bold.ttf')

    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_bold_path))

    FONT_NAME = 'DejaVuSans'
    FONT_BOLD = 'DejaVuSans-Bold'
except Exception as e:
    print(f"ОШИБКА ШРИФТА: {e}")
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
        'template': request.form.get('template', 'classic')
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
        if k != 'template':
            setattr(resume, k, v)
    db.session.commit()
    session['resume_id'] = resume.id

    # Генерация PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=0, leftMargin=0, topMargin=0, bottomMargin=0)
    styles = getSampleStyleSheet()

    # Базовые стили (явно указываем FONT_NAME)
    style_name = ParagraphStyle('Name', parent=styles['Heading1'], fontName=FONT_BOLD, fontSize=22,
                                textColor=colors.HexColor('#1a1a2e'), spaceAfter=5)
    style_contact = ParagraphStyle('Contact', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10,
                                   textColor=colors.HexColor('#555555'), spaceAfter=15)

    # Заголовки с фиолетовой линией
    style_section = ParagraphStyle('Section', parent=styles['Heading2'], fontName=FONT_BOLD, fontSize=14,
                                   textColor=colors.HexColor('#1a1a2e'), spaceBefore=10, spaceAfter=8)
    style_section.borderWidth = 0
    style_section.borderPadding = 5
    style_section.borderBottom = 1.5
    style_section.borderColor = colors.HexColor('#a88cff')

    style_text = ParagraphStyle('Text', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, leading=14,
                                textColor=colors.HexColor('#333333'))

    # Подготовка текста
    skills_list = "".join([f"• {s.strip()}<br/>" for s in data['skills'].split(',')]) if data['skills'] else ""
    summary_text = data['summary'].replace('\n', '<br/>') if data['summary'] else ""
    exp_text = data['experience'].replace('\n', '<br/>') if data['experience'] else ""
    edu_text = data['education'].replace('\n', '<br/>') if data['education'] else ""

    contact_text = f"{data['email']}"
    if data['phone']:
        contact_text += f"<br/>{data['phone']}"

    # ==========================================
    # ЛОГИКА ВЫБОРА ШАБЛОНА
    # ==========================================

    if data['template'] == 'classic':
        s_name = ParagraphStyle('N', parent=style_name, textColor=colors.white)
        s_contact = ParagraphStyle('C', parent=style_contact, textColor=colors.HexColor('#cccccc'))

        # Для темной колонки заголовки без рамок, просто фиолетовый текст
        s_side_title = ParagraphStyle('ST', parent=style_section, fontSize=12, textColor=colors.HexColor('#a88cff'),
                                      spaceBefore=10)
        s_side_title.borderBottom = 0  # Убираем рамку, чтобы не глючило

        s_side_text = ParagraphStyle('STx', parent=style_text, textColor=colors.white)

        left_col = [Paragraph(data['name'], s_name), Paragraph(contact_text, s_contact)]
        if skills_list:
            left_col.append(Paragraph("НАВЫКИ", s_side_title))
            left_col.append(Paragraph(skills_list, s_side_text))

        right_col = []
        if summary_text: right_col.extend(
            [Paragraph("О СЕБЕ", style_section), Paragraph(summary_text, style_text), Spacer(1, 5 * mm)])
        if exp_text: right_col.extend(
            [Paragraph("ОПЫТ РАБОТЫ", style_section), Paragraph(exp_text, style_text), Spacer(1, 5 * mm)])
        if edu_text: right_col.extend([Paragraph("ОБРАЗОВАНИЕ", style_section), Paragraph(edu_text, style_text)])

        table = Table([[left_col, right_col]], colWidths=[70 * mm, 140 * mm])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 15 * mm),
            ('RIGHTPADDING', (0, 0), (0, 0), 10 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 30 * mm),
            ('LEFTPADDING', (1, 0), (1, 0), 10 * mm),
            ('RIGHTPADDING', (1, 0), (1, 0), 15 * mm),
        ]))

        def bg_classic(canvas, doc):
            canvas.saveState()
            canvas.setFillColor(colors.HexColor('#1a1a2e'))
            canvas.rect(0, 0, 70 * mm, 297 * mm, fill=1, stroke=0)
            canvas.restoreState()

        doc.build([table], onFirstPage=bg_classic, onLaterPages=bg_classic)

    elif data['template'] == 'light':
        elements = [Paragraph(data['name'], style_name), Paragraph(contact_text, style_contact), Spacer(1, 5 * mm)]
        if summary_text: elements.extend(
            [Paragraph("О СЕБЕ", style_section), Paragraph(summary_text, style_text), Spacer(1, 5 * mm)])
        if exp_text: elements.extend(
            [Paragraph("ОПЫТ РАБОТЫ", style_section), Paragraph(exp_text, style_text), Spacer(1, 5 * mm)])
        if edu_text: elements.extend(
            [Paragraph("ОБРАЗОВАНИЕ", style_section), Paragraph(edu_text, style_text), Spacer(1, 5 * mm)])
        if skills_list: elements.extend([Paragraph("НАВЫКИ", style_section), Paragraph(skills_list, style_text)])

        doc.leftMargin = 20 * mm
        doc.rightMargin = 20 * mm
        doc.topMargin = 20 * mm
        doc.bottomMargin = 20 * mm
        doc.build(elements)

    elif data['template'] == 'modern':
        s_modern_name = ParagraphStyle('MN', parent=style_name, textColor=colors.white, alignment=1)
        s_modern_contact = ParagraphStyle('MC', parent=style_contact, textColor=colors.white, alignment=1)

        header_table = Table([[Paragraph(data['name'], s_modern_name)], [Paragraph(contact_text, s_modern_contact)]],
                             colWidths=[210 * mm])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 20 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10 * mm),
        ]))

        content_elements = []
        if summary_text: content_elements.extend(
            [Paragraph("О СЕБЕ", style_section), Paragraph(summary_text, style_text), Spacer(1, 5 * mm)])
        if exp_text: content_elements.extend(
            [Paragraph("ОПЫТ РАБОТЫ", style_section), Paragraph(exp_text, style_text), Spacer(1, 5 * mm)])
        if edu_text: content_elements.extend(
            [Paragraph("ОБРАЗОВАНИЕ", style_section), Paragraph(edu_text, style_text), Spacer(1, 5 * mm)])
        if skills_list: content_elements.extend(
            [Paragraph("НАВЫКИ", style_section), Paragraph(skills_list, style_text)])

        content_table = Table([[content_elements]], colWidths=[210 * mm])
        content_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 20 * mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20 * mm),
            ('TOPPADDING', (0, 0), (-1, -1), 10 * mm),
        ]))

        doc.build([header_table, content_table])

    # Отдаем PDF
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