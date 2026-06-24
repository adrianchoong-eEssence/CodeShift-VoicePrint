import streamlit as st
from openai import OpenAI
import tempfile
import json
import re
import wave
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(
    page_title="CodeShift Identity Blueprint",
    layout="centered"
)

ARCHETYPES = {
    "Guardian": "Security & Stability",
    "Controller": "Certainty & Control",
    "Achiever": "Results & Success",
    "Harmoniser": "Acceptance & Connection",
    "Influencer": "Recognition & Significance",
    "Explorer": "Freedom & Choice",
    "Visionary": "Purpose & Meaning",
    "Catalyst": "Growth & Transformation",
}

ARCHETYPE_KEYWORDS = {
    "Guardian": ["safe", "security", "stable", "risk", "worry", "protect", "careful", "uncertain"],
    "Controller": ["control", "responsible", "manage", "ensure", "must", "should", "plan", "check"],
    "Achiever": ["achieve", "success", "goals", "results", "performance", "win", "improve", "deliver"],
    "Harmoniser": ["people", "approval", "accepted", "support", "relationship", "disappoint", "harmony"],
    "Influencer": ["recognised", "visible", "noticed", "respected", "valued", "impact people", "influence"],
    "Explorer": ["freedom", "choice", "options", "flexible", "trapped", "independent", "space"],
    "Visionary": ["purpose", "meaning", "future", "vision", "legacy", "direction", "contribution"],
    "Catalyst": ["change", "growth", "transform", "shift", "breakthrough", "evolve", "potential"],
}

HIDDEN_CODES = {
    "Achievement Code": "My value comes from what I achieve.",
    "Approval Code": "My value comes from being accepted.",
    "Control Code": "If I stay in control, I stay safe.",
    "Safety Code": "I must avoid unnecessary risk.",
    "Recognition Code": "I matter when others notice me.",
    "Contribution Code": "I matter when I help others.",
    "Freedom Code": "I need choice to thrive.",
    "Purpose Code": "My work must mean something.",
    "Connection Code": "I thrive when I belong.",
    "Growth Code": "I am always becoming.",
}

CODE_KEYWORDS = {
    "Achievement Code": ["achieve", "success", "result", "performance", "goal", "win", "prove"],
    "Approval Code": ["approval", "accepted", "liked", "disappoint", "judged", "expectations"],
    "Control Code": ["control", "manage", "ensure", "responsible", "must", "should", "plan"],
    "Safety Code": ["safe", "security", "risk", "worry", "fear", "stable", "uncertain"],
    "Recognition Code": ["recognised", "noticed", "respected", "valued", "important", "visible"],
    "Contribution Code": ["help", "support", "serve", "contribute", "give", "others"],
    "Freedom Code": ["freedom", "choice", "flexible", "independent", "options", "space"],
    "Purpose Code": ["purpose", "meaning", "impact", "legacy", "difference", "vision"],
    "Connection Code": ["family", "team", "together", "belong", "connection", "relationship"],
    "Growth Code": ["growth", "learn", "develop", "improve", "evolve", "transform", "shift"],
}


def clean_text(text):
    text = str(text)
    replacements = {
        "™": "", "®": "", "©": "",
        "—": "-", "–": "-",
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "…": "...", "•": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def score_items(transcript, dictionary, base=35):
    text = transcript.lower()
    scores = {k: base for k in dictionary.keys()}

    for item, words in dictionary.items():
        for word in words:
            scores[item] += len(re.findall(r"\b" + re.escape(word.lower()) + r"\b", text)) * 8

    return {k: min(100, int(v)) for k, v in scores.items()}


def score_archetypes(transcript, stress, confidence, purpose, relationships, career, energy, health):
    scores = score_items(transcript, ARCHETYPE_KEYWORDS)

    scores["Guardian"] += stress * 2 + (11 - health)
    scores["Controller"] += stress * 2 + career
    scores["Achiever"] += career * 2 + confidence
    scores["Harmoniser"] += relationships * 2 + (11 - confidence)
    scores["Influencer"] += confidence + career
    scores["Explorer"] += purpose + (11 - stress)
    scores["Visionary"] += purpose * 3
    scores["Catalyst"] += purpose * 2 + energy + confidence

    return {k: min(100, int(v)) for k, v in scores.items()}


def score_hidden_codes(transcript, stress, confidence, purpose, relationships, career, energy, health):
    scores = score_items(transcript, CODE_KEYWORDS)

    scores["Achievement Code"] += career * 2 + confidence
    scores["Approval Code"] += relationships + (11 - confidence)
    scores["Control Code"] += stress * 2 + career
    scores["Safety Code"] += stress * 2 + (11 - health)
    scores["Recognition Code"] += confidence + career
    scores["Contribution Code"] += relationships + purpose
    scores["Freedom Code"] += purpose + (11 - stress)
    scores["Purpose Code"] += purpose * 3
    scores["Connection Code"] += relationships * 2
    scores["Growth Code"] += purpose + energy + confidence

    return {k: min(100, int(v)) for k, v in scores.items()}


def alignment_index(stress, confidence, purpose, relationships, career, energy, health):
    return int((confidence + purpose + relationships + career + energy + health + (11 - stress)) / 7 * 10)


def growth_potential_index(confidence, purpose, energy):
    return int((confidence + purpose + energy) / 3 * 10)


def alignment_status(score):
    if score >= 90:
        return "Highly Aligned"
    if score >= 75:
        return "Well Aligned"
    if score >= 60:
        return "Emerging Alignment"
    if score >= 45:
        return "Misalignment Detected"
    return "Significant Misalignment"


def protection_strategy(top_archetype, top_codes):
    top_code_names = [x[0] for x in top_codes]

    if "Control Code" in top_code_names or top_archetype == "Controller":
        return "The Architect", "Creates certainty through structure, planning and control."
    if "Approval Code" in top_code_names or top_archetype == "Harmoniser":
        return "The Harmoniser", "Creates safety by maintaining acceptance, connection and agreement."
    if "Achievement Code" in top_code_names or top_archetype == "Achiever":
        return "The Performer", "Creates value by delivering results and proving capability."
    return "The Escapist", "Creates relief by stepping back from discomfort, pressure or uncertainty."


def operating_system(primary, secondary, shadow, top_codes):
    code_names = [x[0] for x in top_codes]

    if primary in ["Controller", "Guardian"]:
        decision = "Structured Strategist"
    elif primary in ["Explorer", "Catalyst"]:
        decision = "Opportunity Seeker"
    elif primary in ["Harmoniser"]:
        decision = "Collaborative Validator"
    else:
        decision = "Independent Navigator"

    if primary in ["Catalyst", "Explorer", "Visionary"]:
        change = "Transformation Catalyst"
    elif primary in ["Guardian", "Controller"]:
        change = "Thoughtful Adaptor"
    else:
        change = "Progressive Driver"

    if "Achievement Code" in code_names:
        validation = "Achievement Validation"
    elif "Recognition Code" in code_names:
        validation = "Recognition Validation"
    elif "Contribution Code" in code_names:
        validation = "Contribution Validation"
    else:
        validation = "Purpose Validation"

    if primary in ["Controller", "Achiever"]:
        connection = "Competence Builder"
    elif primary in ["Visionary", "Catalyst"]:
        connection = "Challenge Partner"
    elif primary in ["Harmoniser", "Guardian"]:
        connection = "Relationship Builder"
    else:
        connection = "Community Builder"

    if primary in ["Catalyst", "Visionary"]:
        growth = "Transformational Learner"
    elif primary in ["Achiever", "Controller"]:
        growth = "Strategic Developer"
    elif primary in ["Guardian", "Harmoniser"]:
        growth = "Experience Integrator"
    else:
        growth = "Continuous Learner"

    return {
        "Decision Engine": decision,
        "Change Engine": change,
        "Validation Engine": validation,
        "Connection Engine": connection,
        "Growth Engine": growth,
    }


def extract_audio_features(audio_path, transcript):
    try:
        with wave.open(audio_path, "rb") as wav:
            duration = wav.getnframes() / float(wav.getframerate())
        words = len(transcript.split())
        pace = round(words / duration * 60, 1) if duration > 0 else 0
        return {
            "Duration": round(duration, 1),
            "Word Count": words,
            "Estimated Pace": pace,
        }
    except Exception:
        return {
            "Duration": "Limited",
            "Word Count": len(transcript.split()),
            "Estimated Pace": "Limited",
        }


def create_radar_chart(scores):
    labels = list(scores.keys())
    values = list(scores.values())

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig = plt.figure(figsize=(6, 6))
    ax = plt.subplot(111, polar=True)
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_title("CodeShift Identity Wheel", size=14, pad=20)

    chart_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    plt.tight_layout()
    plt.savefig(chart_path, dpi=200)
    plt.close(fig)
    return chart_path


def pdf_title(pdf, title):
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(20, 28, 45)
    pdf.cell(0, 10, clean_text(title), ln=True)
    pdf.ln(3)


def pdf_body(pdf, text, size=10):
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 6, clean_text(text))
    pdf.ln(3)


def pdf_card(pdf, title, body):
    pdf.set_fill_color(240, 242, 245)
    pdf.set_text_color(20, 28, 45)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, clean_text(title), ln=True, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, clean_text(body))
    pdf.ln(4)


def create_pdf(name, age, occupation, alignment, growth, align_status, scores, top_three, top_codes, strategy, os_profile, report, chart_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)

    navy = (18, 24, 38)
    gold = (196, 154, 74)
    light = (244, 246, 248)
    mid = (90, 96, 110)
    dark = (35, 39, 48)

    def safe(text):
        return clean_text(text)

    def footer():
        pdf.set_y(282)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 6, "CodeShift Identity Blueprint | Coaching reflection tool | Not a diagnostic assessment", align="C")

    def page_title(title, subtitle=""):
        pdf.set_text_color(*navy)
        pdf.set_font("Helvetica", "B", 19)
        pdf.set_xy(14, 18)
        pdf.cell(0, 10, safe(title), ln=True)
        pdf.set_draw_color(*gold)
        pdf.set_line_width(0.8)
        pdf.line(14, 32, 196, 32)
        if subtitle:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*mid)
            pdf.set_xy(14, 36)
            pdf.multi_cell(182, 5, safe(subtitle))

    def dashboard_card(x, y, w, h, label, value, note=""):
        pdf.set_fill_color(*light)
        pdf.set_draw_color(225, 225, 225)
        pdf.rect(x, y, w, h, "DF")
        pdf.set_xy(x + 5, y + 5)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*mid)
        pdf.cell(w - 10, 5, safe(label.upper()), ln=True)
        pdf.set_xy(x + 5, y + 14)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(*navy)
        pdf.multi_cell(w - 10, 8, safe(value))
        if note:
            pdf.set_xy(x + 5, y + h - 12)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(95, 95, 95)
            pdf.multi_cell(w - 10, 4, safe(note[:75]))

    def text_box(x, y, w, h, title, body):
        pdf.set_fill_color(250, 250, 250)
        pdf.set_draw_color(230, 230, 230)
        pdf.rect(x, y, w, h, "DF")
        pdf.set_xy(x + 5, y + 5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*navy)
        pdf.multi_cell(w - 10, 5, safe(title))
        pdf.set_xy(x + 5, y + 18)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(w - 10, 5, safe(body))

    def bar(x, y, label, score, w=105):
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*dark)
        pdf.cell(50, 6, safe(label))
        pdf.set_fill_color(225, 225, 225)
        pdf.rect(x + 56, y + 1.5, w, 4, "F")
        pdf.set_fill_color(*gold)
        pdf.rect(x + 56, y + 1.5, max(2, w * score / 100), 4, "F")
        pdf.set_xy(x + 56 + w + 5, y)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*navy)
        pdf.cell(20, 6, f"{score}/100")

    primary, secondary, shadow = top_three[0], top_three[1], top_three[2]

    # PAGE 1 - COVER
    pdf.add_page()
    pdf.set_fill_color(*navy)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.set_text_color(*gold)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_xy(0, 58)
    pdf.cell(0, 13, "CodeShift", ln=True, align="C")
    pdf.cell(0, 13, "Identity Blueprint", ln=True, align="C")
    pdf.set_text_color(245, 245, 245)
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 10, "Powered by VoicePrint Analysis", ln=True, align="C")
    pdf.set_draw_color(*gold)
    pdf.set_line_width(0.7)
    pdf.line(55, 105, 155, 105)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_xy(0, 125)
    pdf.cell(0, 8, f"Prepared for: {safe(name)}", ln=True, align="C")
    pdf.cell(0, 8, f"Occupation: {safe(occupation) if str(occupation).strip() else 'Not specified'}", ln=True, align="C")
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%d %B %Y')}", ln=True, align="C")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_xy(28, 220)
    pdf.multi_cell(154, 5, safe("A confidential coaching and leadership development report based on identity patterns, hidden codes and the CodeShift Operating System. This is not a medical, psychological, trauma or diagnostic assessment."), align="C")

    # PAGE 2 - EXECUTIVE DASHBOARD
    pdf.add_page()
    page_title("Executive Dashboard", "A quick snapshot of the participant's current identity alignment and growth potential.")
    dashboard_card(15, 55, 85, 45, "Alignment Index", f"{alignment}/100", align_status)
    dashboard_card(110, 55, 85, 45, "Growth Potential", f"{growth}/100", "Capacity for development")
    dashboard_card(15, 112, 85, 45, "Primary Archetype", primary[0], ARCHETYPES[primary[0]])
    dashboard_card(110, 112, 85, 45, "Protection Strategy", strategy[0], strategy[1])
    text_box(15, 178, 180, 55, "Executive Summary", f"The current profile indicates a {primary[0]} primary identity pattern, supported by {secondary[0]} and influenced by a {shadow[0]} shadow pattern. The Alignment Index of {alignment}/100 suggests {align_status.lower()}, while the Growth Potential score of {growth}/100 indicates the available capacity for future development.")
    footer()

    # PAGE 3 - IDENTITY STACK
    pdf.add_page()
    page_title("Identity Stack", "The dominant, supporting and shadow identity patterns currently shaping behaviour.")
    text_box(15, 55, 180, 40, "Primary Archetype", f"{primary[0]}\nCore Driver: {ARCHETYPES[primary[0]]}. Score: {primary[1]}/100. This is the most visible operating pattern.")
    text_box(15, 105, 180, 40, "Secondary Archetype", f"{secondary[0]}\nCore Driver: {ARCHETYPES[secondary[0]]}. Score: {secondary[1]}/100. This supports how the primary archetype is expressed.")
    text_box(15, 155, 180, 40, "Shadow Archetype", f"{shadow[0]}\nCore Driver: {ARCHETYPES[shadow[0]]}. Score: {shadow[1]}/100. This may be less obvious but still influences decisions and pressure response.")
    pdf.set_xy(15, 213)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*navy)
    pdf.cell(0, 8, "Identity Scores", ln=True)
    y = 226
    for label, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        bar(15, y, label, score, 95)
        y += 7
    footer()

    # PAGE 4 - OPERATING SYSTEM
    pdf.add_page()
    page_title("Leadership Operating System", "How the participant appears to decide, change, validate, connect and grow.")
    y = 55
    for engine, value in os_profile.items():
        text_box(15, y, 180, 30, engine, value)
        y += 39
    footer()

    # PAGE 5 - HIDDEN CODES
    pdf.add_page()
    page_title("Hidden Code Dashboard", "The deeper codes that may be influencing motivation, pressure response and leadership behaviour.")
    y = 58
    for code, score in top_codes[:5]:
        bar(15, y, code, score, 95)
        y += 12
    y = 130
    for code, score in top_codes[:3]:
        text_box(15, y, 180, 35, f"{code} | {score}/100", f"{HIDDEN_CODES[code]}\nStrength, risk and growth opportunity are explored in the Executive Insight section.")
        y += 45
    footer()

    # PAGE 6 - EXECUTIVE INSIGHT
    pdf.add_page()
    page_title("CodeShift Insight", "Pattern, tension, blind spot and shift for senior leadership reflection.")
    cleaned_report = safe(report).replace("#", "").replace("**", "")
    cleaned_report = cleaned_report.replace("The CodeShift Pattern", "THE CODESHIFT PATTERN")
    cleaned_report = cleaned_report.replace("The Tension", "THE TENSION")
    cleaned_report = cleaned_report.replace("The Blind Spot", "THE BLIND SPOT")
    cleaned_report = cleaned_report.replace("The Shift", "THE SHIFT")
    cleaned_report = cleaned_report.replace("Alignment Recommendation", "ALIGNMENT RECOMMENDATION")
    # Keep the insight page clean and avoid footer collision. Full text remains on-screen in Streamlit.
    pdf.set_xy(15, 55)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(45, 45, 45)
    pdf.multi_cell(180, 4.55, cleaned_report[:3300])
    footer()

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    return bytes(pdf_bytes)


st.title("CodeShift Identity Blueprint")
st.subheader("Powered by VoicePrint Analysis")

st.info(
    "This is a leadership and coaching reflection tool. It does not diagnose trauma, "
    "medical conditions, mental health conditions or exact life events."
)

st.header("1. Personal Details")
name = st.text_input("Full Name")
email = st.text_input("Email")
age = st.selectbox("Age Range", ["18-25", "26-35", "36-45", "46-55", "56+"])
occupation = st.text_input("Occupation / Role")

st.header("2. Life Alignment Score")
stress = st.slider("Stress Level", 1, 10, 5)
confidence = st.slider("Confidence Level", 1, 10, 5)
purpose = st.slider("Sense of Purpose", 1, 10, 5)
relationships = st.slider("Relationship Fulfilment", 1, 10, 5)
career = st.slider("Career Satisfaction", 1, 10, 5)
energy = st.slider("Energy Level", 1, 10, 5)
health = st.slider("Physical Wellbeing Reflection", 1, 10, 5)

st.header("3. VoicePrint Leadership Script")

with st.expander("Click here to view the script"):
    st.markdown("""
Please read aloud and complete each sentence naturally.

1. A recent situation where I felt under pressure was ________.

2. When working with others, I become most frustrated when ________.

3. People often misunderstand me because ________.

4. When I make important decisions, I usually rely on ________.

5. I know I am successful when ________.

6. The kind of leader or person I am becoming is ________.

7. The pattern I most want to shift is ________.

8. If I fully stepped into my potential, I would ________.
""")

st.header("4. Record Your Voice")
voice_file = st.audio_input("Press record and read the script aloud")

consent = st.checkbox("I understand this is a coaching reflection report and not a diagnosis.")

if st.button("Generate CodeShift Identity Blueprint"):

    if not name or not email or not occupation or voice_file is None or not consent:
        st.error("Please complete all fields, record your voice, and tick the consent box.")

    else:
        with st.spinner("Transcribing voice..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(voice_file.getvalue())
                audio_path = tmp.name

            with open(audio_path, "rb") as audio:
                transcript = client.audio.transcriptions.create(
                    model="gpt-4o-mini-transcribe",
                    file=audio
                )

            transcript_text = transcript.text

        archetype_scores = score_archetypes(
            transcript_text, stress, confidence, purpose, relationships, career, energy, health
        )

        code_scores = score_hidden_codes(
            transcript_text, stress, confidence, purpose, relationships, career, energy, health
        )

        top_three = sorted(archetype_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        top_codes = sorted(code_scores.items(), key=lambda x: x[1], reverse=True)[:5]

        alignment = alignment_index(stress, confidence, purpose, relationships, career, energy, health)
        growth = growth_potential_index(confidence, purpose, energy)
        align_status = alignment_status(alignment)

        strategy = protection_strategy(top_three[0][0], top_codes)
        os_profile = operating_system(top_three[0][0], top_three[1][0], top_three[2][0], top_codes)

        audio_features = extract_audio_features(audio_path, transcript_text)
        chart_path = create_radar_chart(archetype_scores)

        prompt = f"""
You are a senior CodeShift Identity Blueprint Analyst.

Your role is not to summarise the participant.
Your role is to reveal the repeating CodeShift pattern behind how the participant currently leads, decides, responds to pressure and grows.

Important rules:
- Do not diagnose medical conditions.
- Do not diagnose mental health conditions.
- Do not claim trauma or exact trauma ages.
- Do not make clinical claims.
- Do not use generic AI consulting language.
- Do not include a disclaimer in the generated report.
- Use CodeShift language: Pattern, Tension, Blind Spot, Shift, Alignment.
- Be concise, direct, reflective and suitable for senior leaders.

Participant:
Name: {name}
Age Range: {age}
Occupation: {occupation}

Executive Scores:
Alignment Index: {alignment}/100
Alignment Status: {align_status}
Growth Potential: {growth}/100

Identity Stack:
Primary Archetype: {top_three[0][0]} - {ARCHETYPES[top_three[0][0]]}
Secondary Archetype: {top_three[1][0]} - {ARCHETYPES[top_three[1][0]]}
Shadow Archetype: {top_three[2][0]} - {ARCHETYPES[top_three[2][0]]}

Protection Strategy:
{strategy[0]} - {strategy[1]}

Leadership Operating System:
{json.dumps(os_profile, indent=2)}

Hidden Codes:
{json.dumps(dict(top_codes), indent=2)}

Voice Delivery Snapshot:
{json.dumps(audio_features, indent=2)}

Transcript:
{transcript_text}

Generate the report using this exact structure:

# The CodeShift Pattern
Explain the dominant repeating pattern driving this person right now. Do not repeat the scores. Make it feel like a mirror.

# The Tension
Explain the internal tension between the Primary, Secondary and Shadow Archetypes. Use simple language. Example: Catalyst wants movement, Guardian wants stability.

# The Blind Spot
Identify the pattern this person may not fully see in themselves. This should be the strongest insight.

# The Shift
Describe the shift that would unlock the next level of alignment and leadership effectiveness.

# Alignment Recommendation
Give exactly 3 concise recommendations for the next 30-90 days.

Tone:
- Premium
- Human
- CodeShift-branded
- No fluff
- No diagnosis
- No clinical language
- No disclaimer
"""

        with st.spinner("Generating Identity Blueprint..."):
            response = client.responses.create(
                model="gpt-4.1",
                input=prompt
            )
            report = response.output_text

        pdf_bytes = create_pdf(
            name,
            age,
            occupation,
            alignment,
            growth,
            align_status,
            archetype_scores,
            top_three,
            top_codes,
            strategy,
            os_profile,
            report,
            chart_path
        )

        st.success("CodeShift Identity Blueprint Generated")

        st.metric("Alignment Index", f"{alignment}/100")
        st.metric("Growth Potential", f"{growth}/100")

        st.subheader("Identity Stack")
        st.write(f"Primary: **{top_three[0][0]}** — {ARCHETYPES[top_three[0][0]]}")
        st.write(f"Secondary: **{top_three[1][0]}** — {ARCHETYPES[top_three[1][0]]}")
        st.write(f"Shadow: **{top_three[2][0]}** — {ARCHETYPES[top_three[2][0]]}")

        st.subheader("Protection Strategy")
        st.write(f"**{strategy[0]}** — {strategy[1]}")

        st.image(chart_path)

        st.header("Executive Insight Report")
        st.write(report)

        st.download_button(
            label="Download CodeShift Identity Blueprint PDF",
            data=pdf_bytes,
            file_name=f"{name.replace(' ', '_')}_CodeShift_Identity_Blueprint.pdf",
            mime="application/pdf"
        )