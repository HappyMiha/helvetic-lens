"""Generate deterministic PDF fixtures independently of the production parser."""

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.pdfgen.canvas import Canvas


def make_pdf(pages, *, title="Synthetic test document", password=None):
    output = BytesIO()
    canvas = Canvas(
        output,
        pagesize=A4,
        invariant=1,
        pageCompression=1,
        encrypt=StandardEncryption(password) if password is not None else None,
    )
    canvas.setTitle(title)
    for page in pages:
        blocks = [(72, A4[1] - 72, page)] if isinstance(page, str) else page
        for x, y, content in blocks:
            text = canvas.beginText(x, y)
            text.setFont("Helvetica", 11)
            text.setLeading(13)
            for line in content.split("\n"):
                text.textLine(line)
            canvas.drawText(text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()
