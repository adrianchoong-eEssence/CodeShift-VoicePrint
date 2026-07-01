# ==========================================
# CodeShift Enterprise Database
# Version 1.3A
# Google Sheets Backend
# ==========================================

import streamlit as st
import gspread

from datetime import datetime
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_NAME


# ----------------------------
# Connect to Google Sheets
# ----------------------------

@st.cache_resource
def get_database():

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )

    client = gspread.authorize(credentials)

    try:
        spreadsheet = client.open(GOOGLE_SHEET_NAME)

    except:

        spreadsheet = client.create(GOOGLE_SHEET_NAME)

    try:

        worksheet = spreadsheet.worksheet("Participants")

    except:

        worksheet = spreadsheet.add_worksheet(
            title="Participants",
            rows=5000,
            cols=30
        )

        worksheet.append_row([
            "Timestamp",
            "Company",
            "Programme",
            "Access Code",
            "Name",
            "Email",
            "Age",
            "Occupation",
            "Department",
            "Role",
            "Alignment",
            "Growth",
            "Primary",
            "Secondary",
            "Shadow",
            "Hidden Code",
            "Protection Strategy"
        ])

    return worksheet


# ----------------------------
# Save Participant
# ----------------------------

def save_participant(

    company,
    programme,
    access_code,
    name,
    email,
    age,
    occupation,
    department,
    role,
    alignment,
    growth,
    primary,
    secondary,
    shadow,
    hidden_code,
    protection_strategy

):

    sheet = get_database()

    sheet.append_row([

        datetime.now().strftime("%Y-%m-%d %H:%M"),

        company,
        programme,
        access_code,

        name,
        email,
        age,
        occupation,
        department,
        role,

        alignment,
        growth,

        primary,
        secondary,
        shadow,

        hidden_code,
        protection_strategy

    ])


# ----------------------------
# Read All Participants
# ----------------------------

def load_participants():

    sheet = get_database()

    return sheet.get_all_records()


# ----------------------------
# Count Participants
# ----------------------------

def participant_count():

    data = load_participants()

    return len(data)


# ----------------------------
# Filter by Company
# ----------------------------

def company_participants(company):

    data = load_participants()

    return [

        row

        for row in data

        if row["Company"] == company

    ]