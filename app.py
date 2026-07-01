import streamlit as st
from openai import OpenAI
import os
import tempfile
import json
import re
import wave
from datetime import datetime
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.set_page_config(
    page_title="CodeShift Identity Blueprint",
    layout="centered"
)

# =========================
# Corporate Mode Settings
# =========================

GOOGLE_SHEET_NAME = "CodeShift VoicePrint Database"
RESPONSES_TAB = "Responses"

CLIENTS = {
    "MAXIS2026": {
        "company": "Maxis",
        "programme": "Mission AI / CodeShift Identity Blueprint",
        "quota": 40,
    },
    "AIA2026": {
        "company": "AIA Malaysia",
        "programme": "Mission AI / CodeShift Identity Blueprint",
        "quota": 100,
    },
    "EESSENCE": {
        "company": "eEssence Consultants",
        "programme": "Internal Testing",
        "quota": 9999,
    },
}

SHEET_HEADERS = [
    "Timestamp", "Access Code", "Company", "Programme", "Name", "Email",
    "Age Range", "Occupation", "Department", "Role", "Alignment Index",
    "Alignment Status", "Growth Potential", "Primary Archetype", "Primary Score",
    "Secondary Archetype", "Secondary Score", "Shadow Archetype", "Shadow Score",
    "Protection Strategy", "Hidden Code 1", "Hidden Code 1 Score",
    "Hidden Code 2", "Hidden Code 2 Score", "Hidden Code 3", "Hidden Code 3 Score",
    "Report Generated",
]


def normalise_code(code):
    return str(code or "").strip().upper()


def get_client(access_code):
    code = normalise_code(access_code)
    if code in CLIENTS:
        return CLIENTS[code]
    return {"company": "Unassigned", "programme": "Unassigned", "quota": 0}


@st.cache_resource
def get_google_worksheet():
    """Connects to Google Sheets.

    Local testing: put service-account.json in the same folder as app.py.
    Streamlit Cloud: paste [google_service_account] into App Secrets.
    """
    if gspread is None or Credentials is None:
        return None, "Google Sheets libraries are not installed."

    try:
        if os.path.exists("service-account.json"):
            with open("service-account.json", "r") as file:
                service_account_info = json.load(file)
        else:
            service_account_info = dict(st.secrets["google_service_account"])

        if "private_key" in service_account_info:
            service_account_info["private_key"] = service_account_info["private_key"].replace("\\n", "\n")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        google_client = gspread.authorize(credentials)
        spreadsheet = google_client.open(GOOGLE_SHEET_NAME)

        try:
            worksheet = spreadsheet.worksheet(RESPONSES_TAB)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=RESPONSES_TAB, rows=2000, cols=len(SHEET_HEADERS))

        existing_headers = worksheet.row_values(1)
        if existing_headers != SHEET_HEADERS:
            worksheet.clear()
            worksheet.append_row(SHEET_HEADERS)

        return worksheet, None

    except Exception as error:
        return None, str(error)


def count_completed(access_code):
    worksheet, error = get_google_worksheet()
    if worksheet is None:
        return 0
    try:
        records = worksheet.get_all_records()
        code = normalise_code(access_code)
        return len([row for row in records if normalise_code(row.get("Access Code", "")) == code])
    except Exception:
        return 0


def save_to_google_sheet(row_dict):
    worksheet, error = get_google_worksheet()
    if worksheet is None:
        return False, error or "Google Sheet not connected."
    try:
        row = [row_dict.get(header, "") for header in SHEET_HEADERS]
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return True, "Saved"
    except Exception as error:
        return False, str(error)

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



# =========================
# Streamlit Interface
# =========================



# =========================
# Dashboard Utilities
# =========================

def _to_float(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


def _average(values):
    values = [_to_float(v) for v in values if str(v).strip() != ""]
    if not values:
        return 0
    return round(sum(values) / len(values), 1)


def load_records_for_dashboard():
    worksheet, error = get_google_worksheet()
    if worksheet is None:
        st.error(f"Google Sheet not connected: {error}")
        return []
    try:
        return worksheet.get_all_records()
    except Exception as error:
        st.error(f"Unable to load dashboard records: {error}")
        return []


def render_distribution(title, values):
    st.subheader(title)
    clean_values = [str(v).strip() for v in values if str(v).strip()]
    if not clean_values:
        st.info("No data yet.")
        return

    counts = Counter(clean_values)
    total = sum(counts.values())

    for label, count in counts.most_common():
        pct = round((count / total) * 100)
        st.write(f"**{label}** — {count} participant(s), {pct}%")
        st.progress(pct / 100)


def records_to_csv(records):
    import csv
    import io

    if not records:
        return ""

    output = io.StringIO()
    fieldnames = list(records[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def _format_metric(value, suffix=""):
    try:
        number = float(value)
        if number.is_integer():
            return f"{int(number)}{suffix}"
        return f"{round(number, 1)}{suffix}"
    except Exception:
        return f"{value}{suffix}"


def _safe_float(value, default=0):
    try:
        if value in [None, "", "-"]:
            return default
        return float(value)
    except Exception:
        return default


def _top_label(values, fallback="-"):
    clean = [str(v).strip() for v in values if str(v).strip()]
    if not clean:
        return fallback
    return Counter(clean).most_common(1)[0][0]


def _bar_distribution(title, values, max_items=10):
    clean_values = [str(v).strip() for v in values if str(v).strip()]
    total = len(clean_values)

    st.subheader(title)

    if total == 0:
        st.info("No data available yet.")
        return

    counts = Counter(clean_values).most_common(max_items)

    for label, count in counts:
        percentage = round((count / total) * 100)
        left, right = st.columns([3, 1])
        with left:
            st.write(f"**{label}**")
            st.progress(percentage / 100)
        with right:
            st.write(f"{count} | {percentage}%")


def _department_summary(records):
    departments = {}

    for row in records:
        dept = str(row.get("Department", "Unassigned") or "Unassigned").strip()
        if not dept:
            dept = "Unassigned"

        if dept not in departments:
            departments[dept] = {
                "count": 0,
                "alignment": [],
                "growth": [],
                "primary": [],
                "hidden": [],
            }

        departments[dept]["count"] += 1
        departments[dept]["alignment"].append(_safe_float(row.get("Alignment Index", 0)))
        departments[dept]["growth"].append(_safe_float(row.get("Growth Potential", 0)))
        departments[dept]["primary"].append(row.get("Primary Archetype", ""))
        departments[dept]["hidden"].append(row.get("Hidden Code 1", ""))

    summary = []
    for dept, data in departments.items():
        summary.append({
            "Department": dept,
            "Participants": data["count"],
            "Avg Alignment": _average(data["alignment"]),
            "Avg Growth": _average(data["growth"]),
            "Top Archetype": _top_label(data["primary"]),
            "Top Hidden Code": _top_label(data["hidden"]),
        })

    return sorted(summary, key=lambda item: item["Participants"], reverse=True)


def _make_team_context(records, company_label):
    completed = len(records)
    avg_alignment = _average([r.get("Alignment Index", 0) for r in records])
    avg_growth = _average([r.get("Growth Potential", 0) for r in records])
    primary_values = [r.get("Primary Archetype", "") for r in records]
    hidden_values = [r.get("Hidden Code 1", "") for r in records]
    departments = _department_summary(records)

    archetype_counts = Counter([str(v).strip() for v in primary_values if str(v).strip()]).most_common()
    hidden_counts = Counter([str(v).strip() for v in hidden_values if str(v).strip()]).most_common()

    return {
        "company": company_label,
        "completed": completed,
        "average_alignment": avg_alignment,
        "average_growth": avg_growth,
        "archetype_distribution": archetype_counts,
        "hidden_code_distribution": hidden_counts,
        "department_summary": departments,
    }


def _generate_team_insight(records, company_label):
    context = _make_team_context(records, company_label)

    prompt = f"""
You are the CodeShift Team Intelligence Analyst.

Analyse the following corporate team data and create a concise executive dashboard narrative.
Do not sound clinical. Do not diagnose. Use corporate leadership language.
Focus on working styles, collaboration, stress response, leadership implications and workshop recommendations.

Team Data:
{json.dumps(context, indent=2)}

Generate the response using this exact structure:

# Executive Summary
A short paragraph describing the team identity pattern.

# Team Strengths
3 bullet points.

# Collaboration Risks
3 bullet points.

# Stress & Pressure Pattern
A short paragraph.

# Leadership Recommendations
3 practical recommendations.

# Recommended Workshop Focus
Recommend 2-3 workshop focus areas from: collaboration, working styles, stress management, communication, Mission AI, CodeShift Leadership, resilience, change readiness.
"""

    response = client.responses.create(
        model="gpt-4.1",
        input=prompt,
    )

    return response.output_text


def show_dashboard():
    st.title("CodeShift Team Intelligence")
    st.caption("Client dashboard for CodeShift Identity Blueprint results.")

    dashboard_code = st.text_input("Dashboard Access Code", type="password").strip().upper()

    if not dashboard_code:
        st.info("Enter dashboard access code to view results.")
        return

    company_filter = None

    if dashboard_code == "CODESHIFT-ADMIN":
        company_filter = "ALL"
    else:
        for code, info in CLIENTS.items():
            if dashboard_code == f"{code}-ADMIN" or dashboard_code == info.get("dashboard_code", ""):
                company_filter = info["company"]
                break

    if dashboard_code == "MAXIS-ADMIN":
        company_filter = "Maxis"
    if dashboard_code == "AIA-ADMIN":
        company_filter = "AIA Malaysia"
    if dashboard_code == "EESSENCE-ADMIN":
        company_filter = "eEssence Consultants"

    if company_filter is None:
        st.error("Invalid dashboard access code.")
        return

    records = load_records_for_dashboard()

    if company_filter != "ALL":
        records = [
            row for row in records
            if str(row.get("Company", "")).strip() == company_filter
        ]

    if not records:
        st.warning("No completed assessments found yet.")
        return

    company_label = company_filter if company_filter != "ALL" else "All Companies"

    completed = len(records)
    avg_alignment = _average([r.get("Alignment Index", 0) for r in records])
    avg_growth = _average([r.get("Growth Potential", 0) for r in records])

    primary_values = [r.get("Primary Archetype", "") for r in records]
    secondary_values = [r.get("Secondary Archetype", "") for r in records]
    shadow_values = [r.get("Shadow Archetype", "") for r in records]
    hidden_values = [r.get("Hidden Code 1", "") for r in records]
    departments = [r.get("Department", "") for r in records]
    roles = [r.get("Role", "") for r in records]

    top_primary_label = _top_label(primary_values)
    top_hidden_label = _top_label(hidden_values)

    st.header(f"{company_label} Team Intelligence")

    tab_overview, tab_archetypes, tab_departments, tab_people, tab_ai, tab_export = st.tabs([
        "Overview", "Archetypes", "Departments", "People", "AI Insight", "Export"
    ])

    with tab_overview:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Participants", completed)
        col2.metric("Avg Alignment", f"{avg_alignment}/100")
        col3.metric("Avg Growth", f"{avg_growth}/100")
        col4.metric("Top Archetype", top_primary_label)

        col5, col6, col7 = st.columns(3)
        col5.metric("Top Hidden Code", top_hidden_label)
        col6.metric("Departments", len(set([d for d in departments if str(d).strip()])))
        col7.metric("Roles", len(set([r for r in roles if str(r).strip()])))

        st.divider()
        st.subheader("Team Snapshot")
        st.write(
            f"This dashboard currently contains **{completed} completed assessment(s)** for **{company_label}**. "
            f"The team's average Alignment Index is **{avg_alignment}/100**, with average Growth Potential at **{avg_growth}/100**. "
            f"The most common primary archetype is **{top_primary_label}**, and the most common hidden code is **{top_hidden_label}**."
        )

        st.divider()
        left, right = st.columns(2)
        with left:
            _bar_distribution("Primary Archetype Snapshot", primary_values, max_items=6)
        with right:
            _bar_distribution("Hidden Code Snapshot", hidden_values, max_items=6)

    with tab_archetypes:
        col_a, col_b = st.columns(2)
        with col_a:
            _bar_distribution("Primary Archetype Distribution", primary_values)
            st.divider()
            _bar_distribution("Secondary Archetype Distribution", secondary_values)
        with col_b:
            _bar_distribution("Shadow Archetype Distribution", shadow_values)
            st.divider()
            _bar_distribution("Hidden Code Distribution", hidden_values)

    with tab_departments:
        st.subheader("Department Comparison")
        dept_summary = _department_summary(records)

        for item in dept_summary:
            with st.container(border=True):
                st.markdown(f"### {item['Department']}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Participants", item["Participants"])
                c2.metric("Avg Alignment", f"{item['Avg Alignment']}/100")
                c3.metric("Avg Growth", f"{item['Avg Growth']}/100")
                c4.metric("Top Archetype", item["Top Archetype"])
                st.caption(f"Top Hidden Code: {item['Top Hidden Code']}")

    with tab_people:
        st.subheader("Participant Explorer")
        names = [r.get("Name", "") for r in records if r.get("Name", "")]

        if not names:
            st.info("No participant names available.")
        else:
            selected_name = st.selectbox("Select Participant", names)
            selected_records = [r for r in records if r.get("Name", "") == selected_name]
            person = selected_records[-1] if selected_records else None

            if person:
                c1, c2, c3 = st.columns(3)
                c1.metric("Alignment", f"{person.get('Alignment Index', '-')}/100")
                c2.metric("Growth", f"{person.get('Growth Potential', '-')}/100")
                c3.metric("Primary", person.get("Primary Archetype", "-"))

                st.write(f"**Department:** {person.get('Department', '-')}")
                st.write(f"**Role:** {person.get('Role', '-')}")
                st.write(f"**Secondary:** {person.get('Secondary Archetype', '-')}")
                st.write(f"**Shadow:** {person.get('Shadow Archetype', '-')}")
                st.write(f"**Hidden Code:** {person.get('Hidden Code 1', '-')}")
                st.write(f"**Protection Strategy:** {person.get('Protection Strategy', '-')}")

        st.divider()
        st.subheader("Recent Submissions")
        for row in records[-10:][::-1]:
            st.write(
                f"**{row.get('Name', '-')}** | "
                f"{row.get('Department', '-')} | "
                f"{row.get('Primary Archetype', '-')} | "
                f"Alignment {row.get('Alignment Index', '-')}/100 | "
                f"Growth {row.get('Growth Potential', '-')}/100"
            )

    with tab_ai:
        st.subheader("AI Executive Coach")
        st.write(
            "Generate a leadership-level interpretation of the team's working style, collaboration risks, "
            "stress pattern and recommended workshop focus."
        )

        if st.button("Generate Executive Team Insight"):
            with st.spinner("Analysing team patterns..."):
                try:
                    insight = _generate_team_insight(records, company_label)
                    st.session_state["team_insight"] = insight
                except Exception as error:
                    st.error(f"Could not generate insight: {error}")

        if st.session_state.get("team_insight"):
            st.markdown(st.session_state["team_insight"])

    with tab_export:
        st.subheader("Export Data")
        csv_data = records_to_csv(records)
        st.download_button(
            label="Download Dashboard Data (CSV)",
            data=csv_data,
            file_name=f"codeshift_dashboard_{company_label.replace(' ', '_')}.csv",
            mime="text/csv",
        )

        if st.session_state.get("team_insight"):
            st.download_button(
                label="Download AI Team Insight (TXT)",
                data=st.session_state["team_insight"],
                file_name=f"codeshift_team_insight_{company_label.replace(' ', '_')}.txt",
                mime="text/plain",
            )

def participant_view():
    st.title("CodeShift Identity Blueprint")
    st.subheader("Powered by VoicePrint Analysis")

    st.info(
        "This is a leadership and coaching reflection tool. It does not diagnose trauma, "
        "medical conditions, mental health conditions or exact life events."
    )

    st.header("1. Access Details")
    access_code = st.text_input("Access Code", placeholder="Example: MAXIS2026").strip().upper()
    client_info = get_client(access_code)
    company = client_info["company"]
    programme = client_info["programme"]
    quota = int(client_info.get("quota", 0) or 0)

    if access_code:
        if access_code in CLIENTS:
            completed = count_completed(access_code)
            st.success(f"Access confirmed: {company} - {programme}")
            if quota > 0:
                st.caption(f"Completed: {completed}/{quota}")
                if completed >= quota:
                    st.error("This access code has reached its assessment limit. Please contact eEssence Consultants.")
        else:
            st.warning("Access code not recognised. This test will still run, but it will be saved as Unassigned.")

    st.header("2. Personal Details")
    name = st.text_input("Full Name")
    email = st.text_input("Email")
    age = st.selectbox("Age Range", ["18-25", "26-35", "36-45", "46-55", "56+"])
    occupation = st.text_input("Occupation / Role")
    department = st.text_input("Department")
    role = st.text_input("Job Title / Designation")

    st.header("3. Life Alignment Score")
    stress = st.slider("Stress Level", 1, 10, 5)
    confidence = st.slider("Confidence Level", 1, 10, 5)
    purpose = st.slider("Sense of Purpose", 1, 10, 5)
    relationships = st.slider("Relationship Fulfilment", 1, 10, 5)
    career = st.slider("Career Satisfaction", 1, 10, 5)
    energy = st.slider("Energy Level", 1, 10, 5)
    health = st.slider("Physical Wellbeing Reflection", 1, 10, 5)

    st.header("4. VoicePrint Leadership Script")

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

    st.header("5. Record Your Voice")
    voice_file = st.audio_input("Press record and read the script aloud")

    consent = st.checkbox("I understand this is a coaching reflection report and not a diagnosis.")

    if st.button("Generate CodeShift Identity Blueprint"):

        if not access_code or not name or not email or not occupation or voice_file is None or not consent:
            st.error("Please complete access code, all required fields, record your voice, and tick the consent box.")

        elif access_code in CLIENTS and quota > 0 and count_completed(access_code) >= quota:
            st.error("This access code has reached its assessment limit. Please contact eEssence Consultants.")

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
    Department: {department}
    Role: {role}
    Company: {company}
    Programme: {programme}

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

            row_dict = {
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Access Code": access_code,
                "Company": company,
                "Programme": programme,
                "Name": name,
                "Email": email,
                "Age Range": age,
                "Occupation": occupation,
                "Department": department,
                "Role": role,
                "Alignment Index": alignment,
                "Alignment Status": align_status,
                "Growth Potential": growth,
                "Primary Archetype": top_three[0][0],
                "Primary Score": top_three[0][1],
                "Secondary Archetype": top_three[1][0],
                "Secondary Score": top_three[1][1],
                "Shadow Archetype": top_three[2][0],
                "Shadow Score": top_three[2][1],
                "Protection Strategy": strategy[0],
                "Hidden Code 1": top_codes[0][0],
                "Hidden Code 1 Score": top_codes[0][1],
                "Hidden Code 2": top_codes[1][0],
                "Hidden Code 2 Score": top_codes[1][1],
                "Hidden Code 3": top_codes[2][0],
                "Hidden Code 3 Score": top_codes[2][1],
                "Report Generated": "Yes",
            }
            saved, save_message = save_to_google_sheet(row_dict)

            st.success("CodeShift Identity Blueprint Generated")
            if saved:
                st.success("Participant saved to Google Sheet.")
            else:
                st.warning(f"Report generated, but Google Sheet save failed: {save_message}")

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



# =========================
# App Router
# =========================

mode = st.sidebar.radio(
    "Mode",
    ["Participant Assessment", "Client Dashboard"]
)

if mode == "Participant Assessment":
    participant_view()
else:
    show_dashboard()
