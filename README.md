# WhatsApp Daily Menu Bot

A Python WhatsApp automation bot that reads customer and menu data from Google Sheets and sends daily lunch/dinner menu notifications using the Meta WhatsApp Cloud API.

## What this project does

The bot:
- Detects whether the current IST time is in the **Lunch** or **Dinner** send window.
- Reads menu + customer data from Google Sheets.
- Personalizes and sends templated WhatsApp messages.
- Sanitizes customer numbers to Indian E.164 format (`+91XXXXXXXXXX`).
- Logs delivery outcomes to a Google Sheet tab.
- Supports `TEST_MODE` so only one approved test number receives messages during development.

## Features

- **Time-window based sending**
  - Lunch window: `08:00` to `13:59` IST
  - Dinner window: `17:00` to `20:59` IST
- **Google Sheets-backed data source**
  - `Customer_database` for recipients
  - `Weekly_Menu` for day-wise menu
  - `Performance_logs` for send tracking
- **Meta Cloud API integration** using message templates
- **Retry logic** for transient WhatsApp API/network errors (up to 3 attempts)
- **Phone sanitization** for consistent destination formatting
- **Operational logging** for success/failure auditing

## High-level flow

1. Load environment variables from `.env`.
2. Determine meal type (`Lunch`/`Dinner`) based on current IST time.
3. Connect to Google Sheets using service-account JSON from env.
4. Fetch current day's menu from `Weekly_Menu`.
5. Read all customers from `Customer_database`.
6. For each customer:
   - sanitize number,
   - optionally skip if `TEST_MODE` is enabled and number is not the test number,
   - send WhatsApp template message,
   - append result to `Performance_logs`.
7. Exit.

## Project files

- `/home/runner/work/whatsapp-bot/whatsapp-bot/main.py` – primary bot script
- `/home/runner/work/whatsapp-bot/whatsapp-bot/main2.py` – alternate variant of the bot flow
- `/home/runner/work/whatsapp-bot/whatsapp-bot/requirements.txt` – Python dependencies

## Prerequisites

- Python 3.10+
- A Meta developer app with WhatsApp Cloud API enabled
- A configured WhatsApp message template
- A Google Cloud service account with Sheets access
- A Google Spreadsheet shared with the service account email

## Installation

```bash
cd /home/runner/work/whatsapp-bot/whatsapp-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables

Create a `.env` file in `/home/runner/work/whatsapp-bot/whatsapp-bot`:

```env
# Google service account JSON as a single-line JSON string
GCP_CREDENTIALS_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n","client_email":"...","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}

# Meta WhatsApp Cloud API
META_ACCESS_TOKEN=EAAG...
PHONE_NUMBER_ID=123456789012345
WHATSAPP_TEMPLATE_NAME=daily_menu_notification

# Safe testing controls
TEST_MODE=True
TEST_PHONE_NUMBER=+919999999999
```

### Variable reference

| Variable | Required | Description |
|---|---|---|
| `GCP_CREDENTIALS_JSON` | Yes | Full Google service-account JSON (as string) used by `gspread.service_account_from_dict`. |
| `META_ACCESS_TOKEN` | Yes | Meta Graph API access token. |
| `PHONE_NUMBER_ID` | Yes | WhatsApp Cloud API phone number ID. |
| `WHATSAPP_TEMPLATE_NAME` | No | Template name to send. Defaults to `daily_menu_notification`. |
| `TEST_MODE` | No | If `True` (default), only `TEST_PHONE_NUMBER` is allowed for sending. |
| `TEST_PHONE_NUMBER` | Recommended | Required for practical testing when `TEST_MODE=True`. Use E.164 format (`+91...`). |

## Google Sheet structure

Spreadsheet name expected by code: **`Customer_List`**

Create these tabs exactly:

### 1) `Customer_database`

| Name | ContactNumber |
|---|---|
| Amit | 9876543210 |
| Neha | +91 91234 56789 |

- `Name`: recipient display name
- `ContactNumber`: any reasonable Indian number format (code sanitizes to `+91XXXXXXXXXX`)

### 2) `Weekly_Menu`

| Day | Lunch | Dinner |
|---|---|---|
| Monday | Dal, Rice, Salad | Roti, Paneer, Soup |
| Tuesday | Veg Pulao, Raita | Khichdi, Curd |

- `Day` must contain weekday names (`Monday` ... `Sunday`)
- `Lunch` and `Dinner` columns are mandatory

### 3) `Performance_logs`

| Timestamp | Phone | Status | Message |
|---|---|---|---|
| 2026-05-11 13:30:00 | +919999999999 | Success | Hi Amit, here’s your Lunch menu for today... |

- Rows are appended automatically by the bot.

## WhatsApp template expectations

The payload sends a template body with **two text parameters**:
1. Customer name
2. Menu item text

Ensure your approved Meta template body matches this parameter order.

## Run the bot

```bash
cd /home/runner/work/whatsapp-bot/whatsapp-bot
source .venv/bin/activate
python main.py
```

## Scheduling (optional)

Use cron (Linux) or Task Scheduler (Windows) to run periodically. Example cron (every 30 minutes):

```cron
*/30 * * * * cd /home/runner/work/whatsapp-bot/whatsapp-bot && /usr/bin/python main.py
```

The script only sends messages during configured IST meal windows.

## Troubleshooting

- **`GCP_CREDENTIALS_JSON environment variable not found`**: set the variable in `.env`.
- **Google Sheet connection error**: verify spreadsheet/tab names and share sheet with service account email.
- **Menu not found**: ensure `Weekly_Menu` has matching day names and `Lunch`/`Dinner` columns.
- **No messages sent in test mode**: check `TEST_PHONE_NUMBER` format and value.
- **Meta API errors**: verify token validity, template name, and phone number ID.

## Security notes

- Never commit `.env` or raw service-account secrets.
- Rotate Meta/GCP credentials if exposed.
- Keep `TEST_MODE=True` until production configuration is verified.
