from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "artifacts"
OUTPUT_PATH = OUTPUT_DIR / "Marcus_Reynolds_Fictional_Clinical_Trajectory_Outline.docx"

INK = "24313A"
MUTED = "65737D"
TEAL = "377A78"
LIGHT_TEAL = "EAF3F2"
SAND = "F5F0E8"
WHITE = "FFFFFF"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=120, start=140, bottom=120, end=140):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_font(run, name="Aptos", size=None, bold=None, color=None, italic=None):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if italic is not None:
        run.italic = italic


def add_para(doc, text="", style=None, *, before=0, after=6, line=1.08, keep=False):
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = line
    p.paragraph_format.keep_with_next = keep
    if text:
        r = p.add_run(text)
        set_font(r, size=10.2, color=INK)
    return p


def add_bullet(doc, text, level=0):
    p = add_para(doc, style="List Bullet" if level == 0 else "List Bullet 2", after=3)
    r = p.add_run(text)
    set_font(r, size=10.1, color=INK)
    return p


def add_numbered(doc, text):
    p = add_para(doc, style="List Number", after=4)
    r = p.add_run(text)
    set_font(r, size=10.1, color=INK)
    return p


def add_label_value(doc, label, value):
    p = add_para(doc, after=4)
    r = p.add_run(label + " ")
    set_font(r, size=10.1, bold=True, color=TEAL)
    r = p.add_run(value)
    set_font(r, size=10.1, color=INK)
    return p


def add_callout(doc, heading, body):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.35)
    cell = table.cell(0, 0)
    set_cell_shading(cell, LIGHT_TEAL)
    set_cell_margins(cell, 150, 180, 150, 180)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(heading)
    set_font(r, size=10.2, bold=True, color=TEAL)
    p = cell.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(body)
    set_font(r, size=9.6, color=INK)
    add_para(doc, after=2)


def style_document(doc):
    section = doc.sections[0]
    section.top_margin = Inches(0.68)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)

    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.2)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Aptos")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Aptos")

    for style_name, size, color in (
        ("Title", 28, INK),
        ("Subtitle", 11, MUTED),
        ("Heading 1", 16, TEAL),
        ("Heading 2", 12, INK),
    ):
        style = doc.styles[style_name]
        style.font.name = "Aptos Display" if style_name in ("Title", "Heading 1") else "Aptos"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = style_name != "Subtitle"
        style._element.rPr.rFonts.set(qn("w:ascii"), style.font.name)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), style.font.name)

    doc.styles["Title"].paragraph_format.space_after = Pt(8)
    doc.styles["Subtitle"].paragraph_format.space_after = Pt(18)
    doc.styles["Heading 1"].paragraph_format.space_before = Pt(13)
    doc.styles["Heading 1"].paragraph_format.space_after = Pt(6)
    doc.styles["Heading 1"].paragraph_format.keep_with_next = True
    doc.styles["Heading 2"].paragraph_format.space_before = Pt(9)
    doc.styles["Heading 2"].paragraph_format.space_after = Pt(4)
    doc.styles["Heading 2"].paragraph_format.keep_with_next = True


def add_title(doc):
    p = doc.add_paragraph(style="Title")
    r = p.add_run("Marcus Reynolds")
    set_font(r, name="Aptos Display", size=28, bold=True, color=INK)
    p = doc.add_paragraph(style="Subtitle")
    r = p.add_run("Fictional client character and clinical trajectory outline")
    set_font(r, size=11, color=MUTED)

    meta = doc.add_table(rows=1, cols=3)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta.autofit = False
    widths = [2.05, 2.05, 2.05]
    values = [("AGE", "34"), ("SETTING", "Outpatient therapy"), ("ARC", "Eight sessions")]
    for i, ((label, value), width) in enumerate(zip(values, widths)):
        cell = meta.cell(0, i)
        cell.width = Inches(width)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_shading(cell, SAND)
        set_cell_margins(cell, 150, 150, 150, 150)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(label)
        set_font(r, size=8, bold=True, color=TEAL)
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(value)
        set_font(r, size=10, bold=True, color=INK)
    add_para(doc, after=4)
    add_callout(
        doc,
        "Use note",
        "This is a wholly fictional composite created for demonstration and scripted voice generation. It is not a real client record, diagnosis, risk assessment, or treatment recommendation.",
    )


def build_document():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    style_document(doc)
    add_title(doc)

    doc.add_heading("Character snapshot", level=1)
    add_label_value(doc, "Full name:", "Marcus Elijah Reynolds")
    add_label_value(doc, "Age / identity:", "34; Black man; he/him; heterosexual; raised in a close-knit, working-class family in Baltimore.")
    add_label_value(doc, "Current life:", "Lives alone outside Philadelphia and works as a high-school guidance counselor. He is capable, warm, quick-witted, and widely relied upon by students, colleagues, and family.")
    add_label_value(doc, "Reason for beginning therapy:", "Persistent sleep disruption, irritability, emotional exhaustion, and difficulty concentrating after his mother's death eleven months earlier and a demanding year of family caregiving.")
    add_label_value(doc, "Core tension:", "Marcus has built his identity around being dependable and composed. Asking for help feels both unfamiliar and faintly dangerous, as though one unmet responsibility could cause everything around him to unravel.")
    add_label_value(doc, "Strengths:", "Reflective, relationally attuned, loyal, articulate, observant, humorous, motivated, and able to translate insight into small practical experiments.")

    doc.add_heading("Backstory", level=1)
    add_para(doc, "Marcus grew up as the eldest of three siblings. His father drove a city bus and his mother worked in a public library. In a family that valued steadiness and privacy, Marcus became the person who remembered appointments, anticipated problems, and softened conflict. Praise often followed usefulness: he was the responsible one, the calm one, the son who did not need much.")
    add_para(doc, "At twenty-seven, Marcus moved to Philadelphia for graduate school and later became a counselor. The work suits his genuine care for young people, but it also rewards his oldest pattern: noticing everyone else's needs before his own. He has maintained close friendships, yet often edits what he shares so he will not feel exposed or burdensome. He learned early that being calm and useful was a safer way to receive care than openly asking for it.")
    add_para(doc, "Two years ago, Marcus's mother developed complications from an autoimmune illness. Marcus coordinated much of the care while continuing full-time work and making frequent trips home. His mother died unexpectedly after a brief hospitalization. Marcus handled arrangements, supported his father and siblings, and returned to work quickly. The acute crisis ended, but his body never seemed to receive that message.")
    add_para(doc, "In the months before therapy, Marcus began waking around 3:00 a.m., replaying decisions from the hospitalization and mentally rehearsing the next day's obligations. He became short with colleagues, withdrew from friends, and felt guilty whenever he rested. A minor panic-like episode in a grocery store - racing heart, narrowed attention, and an urge to escape - prompted him to seek support.")

    doc.add_heading("Presenting themes for the script", level=1)
    for item in (
        "Grief that appears indirectly through fatigue, irritability, overwork, and sudden sensory memories.",
        "A belief that love is demonstrated through competence and availability.",
        "Hyper-responsibility and difficulty distinguishing care from control.",
        "Guilt about relief, pleasure, rest, and moments when he is not actively grieving.",
        "A growing wish to be known without performing strength or steadiness.",
        "Tension between professional fluency about emotions and personal difficulty inhabiting them.",
    ):
        add_bullet(doc, item)

    doc.add_page_break()
    doc.add_heading("Clinical framing", level=1)
    add_callout(
        doc,
        "Non-diagnostic framing",
        "The story should show a therapist exploring possibilities with Marcus rather than announcing conclusions. Grief, anxiety, sleep disruption, and caregiver strain are narrative themes, not definitive labels. The therapist checks understanding, leaves room for correction, and keeps Marcus's agency visible.",
    )
    add_label_value(doc, "Working formulation:", "Marcus's current distress may be maintained by a cycle of vigilance, over-functioning, depleted sleep, avoidance of vulnerable support, and self-criticism when normal grief responses interrupt performance.")
    add_label_value(doc, "Protective factors:", "Meaningful work, stable housing, two close friends, affection for his siblings, spiritual connection through music, good reflective capacity, and willingness to try therapy despite ambivalence.")
    add_label_value(doc, "Relational pattern in therapy:", "He is initially polished and agreeable, often saying what he thinks a therapist expects. He intellectualizes emotion and uses humor when attention lingers on him. Progress becomes visible when he disagrees, slows down, allows silence, and names needs without apologizing.")
    add_label_value(doc, "Therapeutic stance:", "Warm, collaborative, paced, and gently curious. The therapist reflects patterns tentatively, validates context, avoids rescuing, and turns insight into manageable experiments selected with Marcus.")

    doc.add_heading("Overarching clinical trajectory", level=1)
    table = doc.add_table(rows=1, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    widths = [0.8, 1.35, 2.25, 1.75]
    headers = ["Phase", "Sessions", "Narrative movement", "Observable shift"]
    for i, (header, width) in enumerate(zip(headers, widths)):
        cell = table.rows[0].cells[i]
        cell.width = Inches(width)
        set_cell_shading(cell, TEAL)
        set_cell_margins(cell)
        r = cell.paragraphs[0].add_run(header)
        set_font(r, size=8.7, bold=True, color=WHITE)
    set_repeat_table_header(table.rows[0])

    trajectory_rows = [
        ("1", "1-2", "Build safety; map sleep, overload, grief, and the cost of appearing fine.", "Marcus notices the gap between 'functioning' and feeling well."),
        ("2", "3-4", "Identify the responsibility loop and approach grief in tolerable doses.", "She asks a sibling for one specific form of help and tolerates the discomfort."),
        ("3", "5-6", "Practice boundaries, self-compassion, and receiving support; address a setback.", "She recognizes exhaustion earlier and repairs after snapping at a colleague."),
        ("4", "7-8", "Integrate grief into an ongoing life; consolidate choices and plan for recurrence.", "He can rest without earning it and speak of his mother with sadness and warmth."),
    ]
    for idx, row in enumerate(trajectory_rows):
        cells = table.add_row().cells
        for i, (text_value, width) in enumerate(zip(row, widths)):
            cells[i].width = Inches(width)
            set_cell_margins(cells[i], 110, 120, 110, 120)
            if idx % 2 == 1:
                set_cell_shading(cells[i], "F7FAF9")
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(text_value)
            set_font(r, size=8.6, bold=(i == 0), color=INK)

    doc.add_heading("Session-by-session beats", level=1)
    sessions = [
        ("Session 1 - The capable version", "Marcus minimizes distress while describing a tightly scheduled life. A silence follows the question, 'Who takes care of you?' He laughs, then admits he does not know."),
        ("Session 2 - The body keeps the schedule", "They map the 3:00 a.m. waking cycle and connect nighttime vigilance to months of caregiving. Marcus selects a small wind-down experiment and asks that it not become another performance metric."),
        ("Session 3 - Responsibility as protection", "A family request triggers resentment and immediate guilt. The therapist tentatively wonders whether being indispensable protects Marcus from the risk of needing others. Marcus pushes back, then becomes curious."),
        ("Session 4 - A memory allowed to remain", "A song evokes his mother's kitchen. Marcus stays with the memory rather than redirecting to logistics. He experiences grief and affection together, then asks his brother to handle an upcoming family task."),
        ("Session 5 - Boundary backlash", "After declining extra work, Marcus ruminates and sends an apologetic email. The session distinguishes a boundary from rejection and rehearses a brief repair that does not erase the limit."),
        ("Session 6 - Setback without collapse", "Poor sleep and an anniversary reaction leave Marcus depleted. He fears he is 'back at the beginning.' The therapist helps him identify what is different now: earlier recognition, less isolation, and more choice."),
        ("Session 7 - Receiving", "Marcus tells a friend directly that he wants company, not advice. He describes the relief and embarrassment of being cared for. The therapist notices that Marcus can now remain present when attention turns toward him."),
        ("Session 8 - Carrying forward", "They review the arc without claiming completion. Marcus names warning signs, supports, and a continuing grief ritual. The closing note is grounded hope: his life has widened around the loss, not moved beyond it."),
    ]
    for title, body in sessions:
        p = add_para(doc, after=2, keep=True)
        r = p.add_run(title)
        set_font(r, size=10.2, bold=True, color=TEAL)
        add_para(doc, body, after=6)

    doc.add_page_break()
    doc.add_heading("Dialogue and voice direction", level=1)
    doc.add_heading("Marcus's voice", level=2)
    for item in (
        "Warm baritone; articulate and measured; speech quickens when he is managing anxiety.",
        "Uses dry humor to create distance, then sometimes surprises himself with direct honesty.",
        "Often begins with qualifiers such as 'I know this sounds...' or 'It's not a big deal, but...'. These decrease across the arc.",
        "Emotion is conveyed through pauses, breath, and unfinished sentences rather than melodrama.",
    ):
        add_bullet(doc, item)

    doc.add_heading("Therapist voice", level=2)
    for item in (
        "Calm, grounded adult voice; unhurried pace; attentive but not overly soothing.",
        "Uses concise reflections and genuine questions. Avoids speeches, clinical jargon, and perfect interpretations.",
        "Allows silence after emotionally significant lines; checks whether an observation fits.",
        "Does not diagnose, promise outcomes, or imply that a single insight resolves the pattern.",
    ):
        add_bullet(doc, item)

    doc.add_heading("Continuity guardrails", level=2)
    for item in (
        "Marcus remains competent throughout; distress does not erase his humor, judgment, or professional identity.",
        "Progress is nonlinear. Later sessions may contain grief, poor sleep, avoidance, or irritation without treating these as failure.",
        "No fabricated trauma reveal is needed. The central story is about grief, role identity, and learning to receive care.",
        "Avoid sensational crisis content. If a script introduces safety concerns, the therapist should assess them explicitly and responsibly rather than infer them from mood alone.",
        "Keep therapist interventions collaborative: 'Would it fit if...?', 'What do you notice?', and 'Could we try...?' rather than declarations about Marcus.",
        "Use natural conversational overlap sparingly; for reliable TTS, preserve one named speaker per turn.",
    ):
        add_bullet(doc, item)

    doc.add_heading("Recommended thirty minute script format", level=1)
    add_para(doc, "Each scripted session should target approximately 30 minutes of finished audio. Aim for 2,800-3,200 spoken words across roughly 90-130 turns, delivered at an unhurried conversational pace. The time estimate should include 3-5 minutes of accumulated silence, breathing, hesitation, and nonverbal space rather than filling the entire session with dialogue.")
    add_para(doc, "Generate the session as six consecutive parts of about five minutes each. Each part should continue the same emotional thread and should not restart the session, summarize earlier dialogue, or introduce a new greeting. Keep the speaker labels identical in every part so the same two voices can be reused consistently.")
    doc.add_heading("Pacing and silence guidance", level=2)
    for item in (
        "Use frequent micro-pauses of 1-3 seconds when a speaker searches for words, changes direction, or regulates emotion.",
        "Include several reflective silences of 5-10 seconds after emotionally significant questions or disclosures.",
        "Include one or two uncomfortable silences of 15-20 seconds in which neither person speaks and no new action occurs.",
        "Do not make the therapist rescue every pause. The therapist may wait, breathe, or briefly acknowledge the difficulty without immediately reframing it.",
        "Allow false starts, incomplete sentences, corrections, filler words, repetition, and ordinary logistical moments. Not every exchange should produce insight.",
        "Mark silence as a non-spoken production cue, such as [SILENCE - 8 SECONDS - DO NOT SPEAK]. If the voice model does not preserve the requested duration, insert the silence during audio assembly rather than having a voice read the cue aloud.",
    ):
        add_bullet(doc, item)
    add_para(doc, "Keep stage directions short and place them before the relevant spoken line. Use exactly the same two speaker names on every dialogue turn:")
    add_callout(
        doc,
        "Turn format",
        "THERAPIST: [gently] What happened inside when your brother said he could take it from here?\n\n[SILENCE - 8 SECONDS - DO NOT SPEAK]\n\nMARCUS: [small exhale] Relief. And then, almost immediately, I wanted to take it back.",
    )

    doc.add_heading("Prompt to generate the dialogue script", level=1)
    prompt_text = (
        "Using the attached fictional character outline, write one continuous 30-minute therapy session focused on [SESSION / BEAT]. "
        "Produce approximately 2,800-3,200 spoken words and 90-130 dialogue turns, divided into six labeled parts of about five "
        "minutes each for separate audio generation. The parts must form one uninterrupted session: do not repeat greetings, "
        "summarize earlier parts, or reset the emotional tone. Use only the speaker names THERAPIST and MARCUS for spoken lines. "
        "Keep the dialogue natural, restrained, and clinically plausible. Include false starts, self-corrections, filler words, "
        "mundane transitions, and moments that do not produce insight. Add frequent 1-3 second pauses, several 5-10 second "
        "reflective silences, and one or two 15-20 second uncomfortable silences where neither person speaks and nothing changes. "
        "Mark each silent interval on its own line as [SILENCE - X SECONDS - DO NOT SPEAK]. The therapist should tolerate silence "
        "rather than filling every gap. The therapist must remain collaborative and tentative and must not diagnose, determine "
        "risk, or present interpretations as facts. Preserve Marcus's humor, competence, ambivalence, and agency. End with a small, "
        "believable shift, an agreed next step, or an open question rather than a tidy resolution. Output the six-part script only."
    )
    add_callout(doc, "Copy/paste prompt", prompt_text)

    doc.add_heading("Voice assignment workflow", level=1)
    for step in (
        "Generate and revise the complete six-part text script first using a general Gemini model in Google AI Studio.",
        "Open the speech or TTS experience and configure two speakers using the exact names THERAPIST and MARCUS.",
        "Assign one distinct voice to each speaker; use restrained style directions and test a short excerpt before rendering the full session.",
        "Synthesize the six parts separately while reusing the same voice assignments and delivery instructions. Include the final two or three turns from the preceding part as continuity context when helpful, but do not render those turns twice.",
        "If the TTS model shortens, ignores, or reads a silence cue aloud, remove the spoken cue and insert the specified silent duration during audio assembly.",
        "Listen for skipped turns, unwanted emotional exaggeration, pronunciation issues, or voice drift; revise the transcript or style cues and regenerate.",
        "Join the approved parts with consistent room tone and no audible restart between segments. Retain the approved script alongside the audio so every spoken line remains reviewable.",
    ):
        add_numbered(doc, step)

    # Minimal metadata; avoid embedding a personal author name.
    props = doc.core_properties
    props.title = "Marcus Reynolds - Fictional Clinical Trajectory Outline"
    props.subject = "Fictional character outline for scripted therapy dialogue and voice generation"
    props.author = ""
    props.keywords = "fictional character, therapy dialogue, clinical trajectory, voice generation"

    doc.save(OUTPUT_PATH)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    build_document()
