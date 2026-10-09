from io import BytesIO

from django.utils import timezone
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PURPLE = colors.HexColor('#7B2FF7')
ORANGE = colors.HexColor('#FF6B35')
PINK = colors.HexColor('#F72585')
GREY = colors.HexColor('#6C6F85')
LIGHT = colors.HexColor('#F6F1FF')


def _money(value):
    return f"Rs. {value:,.2f}"


def _table(rows, widths=None, right=()):
    """A styled table. rows[0] is the header row."""
    if len(rows) == 1:                                         # nothing to show
        rows = rows + [['No data for this period'] + [''] * (len(rows[0]) - 1)]
    table = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#E3DEF5')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    style += [('ALIGN', (col, 0), (col, -1), 'RIGHT') for col in right]
    table.setStyle(TableStyle(style))
    return table


def _bar_chart(labels, values):
    drawing = Drawing(174 * mm, 62 * mm)
    chart = VerticalBarChart()
    chart.x, chart.y = 16 * mm, 9 * mm
    chart.width, chart.height = 154 * mm, 46 * mm
    chart.data = [values or [0]]
    chart.categoryAxis.categoryNames = labels or ['']
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(max(values or [0]) * 1.15, 1)
    chart.bars[0].fillColor = PINK
    chart.bars.strokeColor = None
    drawing.add(chart)
    return drawing


def build_summary_pdf(start, end, data):
    revenue, memberships = data['revenue'], data['memberships']
    attendance, summary = data['attendance'], data['summary']

    def draw_page(canvas, document):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(PURPLE)
        canvas.rect(0, height - 32 * mm, width, 32 * mm, stroke=0, fill=1)
        canvas.setFillColor(ORANGE)
        canvas.rect(0, height - 35 * mm, width, 3 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 22)
        canvas.drawString(18 * mm, height - 16 * mm, 'FitTrack Pro')
        canvas.setFont('Helvetica', 11)
        canvas.drawString(18 * mm, height - 24 * mm, f'Club report: {start:%d %b %Y} to {end:%d %b %Y}')
        canvas.setFillColor(GREY)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(18 * mm, 10 * mm, f'Generated {timezone.localtime():%d %b %Y, %I:%M %p}')
        canvas.drawRightString(width - 18 * mm, 10 * mm, f'Page {document.page}')
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=42 * mm, bottomMargin=20 * mm, title='FitTrack Pro club report',
    )
    styles = getSampleStyleSheet()
    heading = ParagraphStyle('heading', parent=styles['Heading2'], textColor=PURPLE, spaceBefore=12, spaceAfter=6)
    body = styles['BodyText']
    story = []

    # ----- Summary -----
    story.append(Paragraph('Summary', heading))
    story.append(_table([
        ['Measure', 'Value'],
        ['Revenue collected', _money(summary['revenue_total'])],
        ['Unpaid dues (as of today)', _money(summary['outstanding_total'])],
        ['Memberships sold', str(summary['sold'])],
        ['Members with a running membership (today)', str(summary['active_members'])],
        ['New member sign-ups', str(summary['signups'])],
        ['Gym visits', str(summary['visits'])],
    ], widths=[110 * mm, 64 * mm], right=(1,)))

    # ----- Revenue -----
    story.append(Paragraph('Revenue', heading))
    story.append(_bar_chart([r['label'] for r in revenue['monthly']],
                            [float(r['total']) for r in revenue['monthly']]))
    story.append(_table([['Month', 'Revenue']] + [[r['label'], _money(r['total'])] for r in revenue['monthly']],
                        widths=[110 * mm, 64 * mm], right=(1,)))
    story.append(Spacer(1, 6 * mm))
    story.append(_table([['Payment method', 'Payments', 'Revenue']] +
                        [[r['name'], str(r['count']), _money(r['total'])] for r in revenue['by_method']],
                        widths=[90 * mm, 30 * mm, 54 * mm], right=(1, 2)))
    story.append(Spacer(1, 6 * mm))
    story.append(_table([['Plan', 'Payments', 'Revenue']] +
                        [[r['name'], str(r['count']), _money(r['total'])] for r in revenue['by_plan']],
                        widths=[90 * mm, 30 * mm, 54 * mm], right=(1, 2)))

    # ----- Memberships -----
    story.append(Paragraph('Membership growth', heading))
    story.append(_table([['Month', 'New', 'Renewals', 'Upgrades', 'Sign-ups']] +
                        [[r['label'], str(r['new']), str(r['renewal']), str(r['upgrade']), str(r['signups'])]
                         for r in memberships['monthly']],
                        widths=[54 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm], right=(1, 2, 3, 4)))
    story.append(Spacer(1, 6 * mm))
    story.append(_table([['Membership status today', 'Count']] +
                        [[r['label'], str(r['count'])] for r in memberships['status_counts']],
                        widths=[110 * mm, 64 * mm], right=(1,)))

    # ----- Attendance -----
    story.append(Paragraph('Attendance', heading))
    story.append(Paragraph(
        f"{attendance['total_visits']} visits by {attendance['unique_members']} different members, "
        f"about {attendance['avg_per_day']} visits per day.", body))
    story.append(Spacer(1, 3 * mm))
    story.append(_table([['Weekday', 'Visits']] + [[r['label'], str(r['visits'])] for r in attendance['by_weekday']],
                        widths=[110 * mm, 64 * mm], right=(1,)))
    story.append(Spacer(1, 6 * mm))
    story.append(_table([['Most regular members', 'Days attended']] +
                        [[r['name'], str(r['days'])] for r in attendance['top_members']],
                        widths=[110 * mm, 64 * mm], right=(1,)))

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return buffer.getvalue()