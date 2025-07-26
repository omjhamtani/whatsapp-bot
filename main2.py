import os
import json
import re
import time
import traceback
from datetime import datetime

import gspread
import pandas as pd
import pytz
import requests
from dotenv import load_dotenv

# --- CONFIGURATION & SETUP ---
load_dotenv()

# Load credentials and settings from environment variables
GCP_CREDENTIALS_JSON_STRING = os.getenv('GCP_CREDENTIALS_JSON')
META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
WHATSAPP_TEMPLATE_NAME = os.getenv('WHATSAPP_TEMPLATE_NAME', 'daily_menu_notification')
TEST_MODE = os.getenv('TEST_MODE', 'True').lower() == 'true'
TEST_PHONE_NUMBER = os.getenv('TEST_PHONE_NUMBER')

# Google Sheets configuration
GOOGLE_SHEET_NAME = 'Customer_List'
CUSTOMER_SHEET_NAME = 'Customer_database'
MENU_SHEET_NAME = 'Weekly_Menu'
LOG_SHEET_NAME = 'Performance_logs'

# Time-based configuration
TIMEZONE = pytz.timezone('Asia/Kolkata')
LUNCH_WINDOW = (8, 14)  # 8:00 AM to 1:59 PM
DINNER_WINDOW = (17, 21) # 5:00 PM to 8:59 PM
# --- HELPER FUNCTIONS ---

def get_gspread_client():
    """Authenticates with Google Sheets using credentials from env vars."""
    if not GCP_CREDENTIALS_JSON_STRING:
        raise ValueError("GCP_CREDENTIALS_JSON secret not found.")
    creds_dict = json.loads(GCP_CREDENTIALS_JSON_STRING)
    return gspread.service_account_from_dict(creds_dict)

def sanitize_phone_number(phone_str):
    """Validates and sanitizes phone number to E.164 format for India."""
    if not phone_str or not isinstance(phone_str, (str, int)): return None
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) < 10: return None
    return f"+91{digits[-10:]}"

def log_to_sheet(log_sheet, phone, status, message=""):
    """Appends a log entry to the specified Google Sheet tab."""
    try:
        timestamp = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
        log_sheet.append_row([timestamp, phone, status, message])
    except Exception as e:
        print(f"Failed to log to Google Sheet: {e}")

# --- CORE LOGIC ---

def get_current_meal_info():
    """Determines the current meal type and day based on predefined time windows."""
    now = datetime.now(TIMEZONE)
    current_hour = now.hour
    day_of_week = now.strftime('%A')
    if LUNCH_WINDOW[0] <= current_hour < LUNCH_WINDOW[1]: return 'Lunch', day_of_week
    if DINNER_WINDOW[0] <= current_hour < DINNER_WINDOW[1]: return 'Dinner', day_of_week
    return None, None

def fetch_menu(menu_sheet, day, meal_type):
    """Fetches the menu from a sheet with 'Day', 'Lunch', 'Dinner' columns."""
    try:
        df = pd.DataFrame(menu_sheet.get_all_records())
        if df.empty: return None
        menu_row = df[df['Day'].str.lower() == day.lower()]
        if not menu_row.empty: return menu_row.iloc[0][meal_type]
    except KeyError:
        print(f"Error fetching menu: Column '{meal_type}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred while fetching menu: {e}")
    return None

# --- UPDATED: Function to send message and report status ---
def send_whatsapp_message(phone_number, name, menu_item):
    """Sends a templated WhatsApp message and returns a status tuple."""
    api_url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {META_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp", "to": phone_number, "type": "template",
        "template": { "name": WHATSAPP_TEMPLATE_NAME, "language": {"code": "en_US"},
            "components": [{ "type": "body",
                "parameters": [
                    {"type": "text", "text": name},
                    {"type": "text", "text": menu_item}
                ]
            }]
        }
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=10)
        response_data = response.json()
        if "error" in response_data:
            error_message = response_data['error']['message']
            print(f"⚠️  Meta API Error for {phone_number}: {error_message}")
            return False, error_message
        else:
            print(f"✔️  Successfully sent message to {name}.")
            return True, f"Sent menu: {menu_item}"
    except requests.exceptions.RequestException as e:
        error_message = f"Network error: {e}"
        print(f"❌ {error_message}")
        return False, error_message

# --- MAIN ORCHESTRATOR ---
def main():
    print("🤖 Bot starting...")
    meal_type, day = get_current_meal_info()
    if not meal_type:
        print("Outside of Lunch/Dinner window. Exiting.")
        return

    print(f"Running for {day} {meal_type}.")
    try:
        gc = get_gspread_client()
        spreadsheet = gc.open(GOOGLE_SHEET_NAME)
        customer_sheet = spreadsheet.worksheet(CUSTOMER_SHEET_NAME)
        menu_sheet = spreadsheet.worksheet(MENU_SHEET_NAME)
        log_sheet = spreadsheet.worksheet(LOG_SHEET_NAME)
    except Exception:
        print("❌ Critical error connecting to Google Sheets."); traceback.print_exc(); return

    menu_item = fetch_menu(menu_sheet, day, meal_type)
    if not menu_item:
        print(f"❌ Menu not found for {day} {meal_type}. Exiting."); return

    customers = customer_sheet.get_all_records()
    print(f"👥 Found {len(customers)} customers to process.")

    for customer in customers:
        name = customer.get('Name')
        original_phone = customer.get('ContactNumber')
        sanitized_phone = sanitize_phone_number(original_phone)

        if not sanitized_phone:
            log_to_sheet(log_sheet, str(original_phone), "Failed", "Invalid phone number format."); continue

        if TEST_MODE and sanitized_phone != TEST_PHONE_NUMBER:
            print(f"Skipping {name} (TEST_MODE is on)."); continue
        
        success, response_message = send_whatsapp_message(sanitized_phone, name, menu_item)
        status = "Success" if success else "Failed"
        log_to_sheet(log_sheet, sanitized_phone, status, response_message)
    
    print("✅ Bot finished.")

if __name__ == "__main__":
    if not all([META_ACCESS_TOKEN, PHONE_NUMBER_ID, GCP_CREDENTIALS_JSON_STRING]):
        print("❌ One or more secrets are missing. Check repository secrets.")
    else:
        main()