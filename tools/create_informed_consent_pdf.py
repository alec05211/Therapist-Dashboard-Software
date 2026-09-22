"""Generate the demonstration informed-consent document shown in Documents."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "informed-consent-therapy-recording-ai-documentation.pdf"
GREEN = colors.HexColor("#2f4937")
TEXT = colors.HexColor("#44403c")
BORDER = colors.HexColor("#c9c4bc")
PALE = colors.HexColor("#f1f0ed")


def page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(0.72 * inch, 0.49 * inch, 7.78 * inch, 0.49 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#78716c"))
    canvas.drawString(0.72 * inch, 0.31 * inch, "Demonstration draft - requires clinical and legal review before use")
    canvas.drawRightString(7.78 * inch, 0.31 * inch, f"Page {document.page}")
    canvas.restoreState()


def signature_table(rows):
    return Table(rows, colWidths=[5.15 * inch, 1.75 * inch],
                 rowHeights=[0.22 * inch, 0.38 * inch] * (len(rows) // 2),
                 style=TableStyle([
                     ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                     ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                     ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                     ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#57534e")),
                     ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                 ]))


def build() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18,
                           leading=22, textColor=GREEN, alignment=TA_CENTER, spaceAfter=7)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
                              leading=11, textColor=colors.HexColor("#6b665f"), alignment=TA_CENTER,
                              spaceAfter=17)
    heading = ParagraphStyle("Heading", parent=styles["Heading2"], fontName="Helvetica-Bold",
                             fontSize=10.5, leading=13, textColor=colors.HexColor("#292524"),
                             spaceBefore=9, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9,
                          leading=12.8, textColor=TEXT, spaceAfter=5.5)
    small = ParagraphStyle("Small", parent=body, fontSize=7.8, leading=10.5,
                           textColor=colors.HexColor("#78716c"))

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=LETTER, rightMargin=0.72 * inch,
                            leftMargin=0.72 * inch, topMargin=0.58 * inch, bottomMargin=0.65 * inch,
                            title="Informed Consent for Therapy, Session Recording, Transcription, and AI-Assisted Documentation",
                            author="Therapist Dashboard")

    client_fields = Table([
        ["Client name", "________________________________________"],
        ["Date of birth", "________________________________________"],
        ["Therapist / practice", "________________________________________"],
        ["Effective date", "________________________________________"],
    ], colWidths=[1.45 * inch, 5.45 * inch], rowHeights=[0.3 * inch] * 4,
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("BACKGROUND", (0, 0), (0, -1), PALE), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (-1, -1), TEXT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))

    choices = Table([
        ["Initial", "Permission"],
        ["______", "I consent to audio recording of sessions that the therapist and I agree to record."],
        ["______", "I consent to transcription of those agreed recordings."],
        ["______", "I consent to clinician-reviewed, AI-assisted drafting based on agreed session materials."],
        ["______", "I decline one or more permissions above and have identified my choices with the therapist."],
    ], colWidths=[0.72 * inch, 6.18 * inch], rowHeights=[0.26 * inch] + [0.38 * inch] * 4,
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER), ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.3), ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))

    story = [
        Paragraph("Informed Consent for Therapy, Session Recording,<br/>Transcription, and AI-Assisted Documentation", title),
        Paragraph("DEMONSTRATION DRAFT - REVIEW AND ADAPT BEFORE CLINICAL USE", subtitle),
        client_fields,
        Paragraph("1. Therapy services and voluntary participation", heading),
        Paragraph("Therapy is a collaborative professional service intended to support personal, emotional, behavioral, or relational goals. Outcomes cannot be guaranteed. Participation is voluntary. I may ask questions, discuss alternatives, decline a proposed activity, or end services, subject to applicable clinical, payment, and notice policies.", body),
        Paragraph("2. Potential benefits and risks", heading),
        Paragraph("Possible benefits include increased understanding, improved coping, and progress toward agreed goals. Therapy can also involve discomfort, strong emotions, difficult memories, or changes in relationships. I agree to discuss concerns with my therapist so the plan of care can be reviewed.", body),
        Paragraph("3. Confidentiality and its limits", heading),
        Paragraph("The practice will protect my information according to its privacy notice and applicable law. Confidentiality may have exceptions, including situations involving suspected abuse or neglect, serious safety concerns, a valid court order, required health-care operations, or other disclosures allowed or required by law. The therapist will explain applicable limits and consultation practices.", body),
        Paragraph("4. Communication, scheduling, and emergencies", heading),
        Paragraph("Routine portal, email, or telephone messages may not be reviewed immediately and may have privacy limitations. The practice will explain scheduling, cancellation, after-hours, and emergency procedures. This service is not an emergency response system. In an emergency, I should contact local emergency services or an appropriate crisis resource.", body),
        Paragraph("5. Clinical documentation and access", heading),
        Paragraph("The therapist may create clinical records to support treatment, continuity of care, operations, and legal obligations. Access, amendment, release, retention, and deletion requests are handled under practice policy and applicable law. Client-facing access to recordings, transcripts, summaries, or other documents is controlled separately.", body),
        PageBreak(),
        Paragraph("Informed Consent - Recording, Transcription, and Documentation", title),
        Paragraph("DEMONSTRATION DRAFT - CONTINUED", subtitle),
        Paragraph("6. Optional recording, transcription, and AI-assisted documentation", heading),
        Paragraph("These activities are optional and require the choices below. A decision to decline will not, by itself, end access to therapy. AI-assisted output is a draft for clinician review; it does not replace the therapist's judgment, determine a diagnosis, or make treatment decisions.", body),
        choices,
        Paragraph("7. How agreed session materials are handled", heading),
        Paragraph("Agreed recordings and related files may be stored in encrypted systems used by the practice. Access should be limited to authorized people with a care or operational need. The practice should document its service providers, retention periods, backup practices, and deletion process before using this form with clients.", body),
        Paragraph("8. External processing and model training", heading),
        Paragraph("If an external transcription or AI provider processes session material, the practice should disclose the approved data flow and applicable privacy terms. Session material will not be authorized for model training or unrelated product development through this form. Any such use requires a separate, specific consent process.", body),
        Paragraph("9. Additional participants", heading),
        Paragraph("If a partner, parent, caregiver, interpreter, supervising clinician, or other person attends a session, the therapist will explain their role and any additional confidentiality or recording expectations. Each participant may need to acknowledge recording or information-sharing choices.", body),
        PageBreak(),
        Paragraph("Acknowledgment and Signatures", title),
        Paragraph("DEMONSTRATION DRAFT - CONTINUED", subtitle),
        Paragraph("10. Revoking an optional permission", heading),
        Paragraph("I may revoke a recording, transcription, or AI-assisted documentation permission for future activity by notifying the practice in writing or through an approved account control. Revocation does not undo processing that lawfully occurred before the practice received it, and some records may need to be retained under policy or law.", body),
        Paragraph("11. Questions and acknowledgment", heading),
        Paragraph("I have had an opportunity to ask questions. I understand the purpose, possible benefits and risks, confidentiality limits, communication procedures, documentation practices, and the optional choices I marked. I understand that this document does not replace the practice's privacy notice, service agreement, or jurisdiction-specific disclosures.", body),
        Spacer(1, 0.08 * inch),
        signature_table([
            ["Client or authorized representative", "Date"],
            ["________________________________________", "__________________"],
            ["Printed name and relationship, if applicable", ""],
            ["________________________________________", ""],
            ["Therapist or practice representative", "Date"],
            ["________________________________________", "__________________"],
        ]),
        Spacer(1, 0.12 * inch),
        Paragraph("Practice-specific notes or limitations", heading),
        Table([[""], [""], [""]], colWidths=[6.9 * inch], rowHeights=[0.36 * inch] * 3,
              style=TableStyle([("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER)])),
        Spacer(1, 0.14 * inch),
        Paragraph("This document is a product demonstration draft, not approved legal or clinical language. A qualified clinical, privacy, and legal reviewer must adapt it to the practice, jurisdiction, client population, technology, and intended workflow before use.", small),
    ]
    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)


if __name__ == "__main__":
    build()
