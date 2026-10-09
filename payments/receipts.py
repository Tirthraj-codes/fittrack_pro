from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PURPLE = colors.HexColor('#7B2FF7')
ORANGE = colors.HexColor('#FF6B35')
PINK = colors.HexColor('#F72585')
TEAL = colors.HexColor('#00A98C')
DARK = colors.HexColor('#2B2D42')
GREY = colors.HexColor('#6C6F85')


def build_receipt(payment):
    """Returns the receipt for a paid payment as PDF bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    paid_on = timezone.localtime(payment.paid_on)

    # ----- Header band -----
    pdf.setFillColor(PURPLE)
    pdf.rect(0, height - 42 * mm, width, 42 * mm, stroke=0, fill=1)
    pdf.setFillColor(ORANGE)
    pdf.rect(0, height - 45 * mm, width, 3 * mm, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 28)
    pdf.drawString(20 * mm, height - 22 * mm, 'FitTrack Pro')
    pdf.setFont('Helvetica', 12)
    pdf.drawString(20 * mm, height - 31 * mm, 'Payment Receipt')
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawRightString(width - 20 * mm, height - 22 * mm, payment.receipt_no)
    pdf.setFont('Helvetica', 11)
    pdf.drawRightString(width - 20 * mm, height - 31 * mm, paid_on.strftime('%d %b %Y, %I:%M %p'))

    # ----- Details -----
    rows = [
        ('Received from', payment.member.display_name),
        ('Username', payment.member.username),
        ('Email', payment.member.email or '-'),
        ('Description', payment.description),
    ]
    if payment.membership:
        period = f"{payment.membership.start_date:%d %b %Y} to {payment.membership.end_date:%d %b %Y}"
        rows.append(('Membership period', period))
    rows += [
        ('Payment method', payment.get_method_display()),
        ('Transaction ID', payment.transaction_id),
    ]

    y = height - 62 * mm
    for label, value in rows:
        pdf.setFillColor(GREY)
        pdf.setFont('Helvetica', 10)
        pdf.drawString(20 * mm, y, label.upper())
        pdf.setFillColor(DARK)
        pdf.setFont('Helvetica-Bold', 12)
        pdf.drawString(70 * mm, y, str(value))
        y -= 11 * mm

    # ----- Amount box -----
    y -= 4 * mm
    pdf.setFillColor(PINK)
    pdf.roundRect(20 * mm, y - 14 * mm, width - 40 * mm, 22 * mm, 4 * mm, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica', 11)
    pdf.drawString(28 * mm, y - 4 * mm, 'AMOUNT PAID')
    pdf.setFont('Helvetica-Bold', 22)
    pdf.drawRightString(width - 28 * mm, y - 6 * mm, f"Rs. {payment.amount:,.2f}")

    # ----- PAID stamp -----
    pdf.saveState()
    pdf.translate(width - 60 * mm, y - 45 * mm)
    pdf.rotate(15)
    pdf.setStrokeColor(TEAL)
    pdf.setFillColor(TEAL)
    pdf.setLineWidth(3)
    pdf.roundRect(-25 * mm, -8 * mm, 50 * mm, 16 * mm, 3 * mm, stroke=1, fill=0)
    pdf.setFont('Helvetica-Bold', 24)
    pdf.drawCentredString(0, -3 * mm, 'PAID')
    pdf.restoreState()

    # ----- Footer -----
    pdf.setFillColor(GREY)
    pdf.setFont('Helvetica', 9)
    pdf.drawCentredString(width / 2, 22 * mm, 'This is a computer-generated receipt and does not need a signature.')
    pdf.drawCentredString(width / 2, 17 * mm, 'Thank you for training with FitTrack Pro!')

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()