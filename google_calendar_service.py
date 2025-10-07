# google_calendar_service.py (v2 - 智慧掃描版)

import os
import datetime as dt
import base64
import email
import re # <-- 【新增】匯入正規表示式工具
from email.header import decode_header, make_header # <-- 【新增】匯入標頭解碼工具

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly"
]
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(SCRIPT_DIR, 'token.json')

def get_google_credentials():
    # (此函式不變)
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    return creds

def create_google_meet_event(service, summary, start_time, end_time, attendees=None, description=""):
    # (此函式不變)
    if attendees is None: attendees = []
    event = {
        "summary": summary, "description": description,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Taipei"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Taipei"},
        "attendees": [{"email": email} for email in attendees],
        "conferenceData": {"createRequest": {"requestId": f"meet-{dt.datetime.now().timestamp()}", "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
        "reminders": {"useDefault": True},
    }
    try:
        created_event = service.events().insert(calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all").execute()
        return created_event.get("hangoutLink")
    except HttpError as error:
        print(f"建立活動時發生錯誤: {error}"); return None

# --- 【重大升級】scan_potential_meeting_emails 函式 ---
def scan_potential_meeting_emails(creds):
    try:
        gmail_service = build("gmail", "v1", credentials=creds)
        query = 'in:inbox is:unread ("約個時間" OR "開會" OR "會議" OR "討論一下")'
        results = gmail_service.users().messages().list(userId="me", q=query, maxResults=30).execute()
        messages = results.get("messages", [])

        if not messages: return []
        
        potential_meetings = []
        for message in messages:
            msg = gmail_service.users().messages().get(userId="me", id=message["id"], format="raw").execute()
            raw_email = base64.urlsafe_b64decode(msg["raw"].encode("ASCII"))
            email_message = email.message_from_bytes(raw_email)
            
            # 【修正亂碼】使用 decode_header 來正確解碼標題
            subject_header = email_message.get("Subject", "無標題")
            decoded_subject = decode_header(subject_header)
            subject = str(make_header(decoded_subject))

            sender_header = email_message.get("From", "未知寄件人")
            decoded_sender = decode_header(sender_header)
            sender = str(make_header(decoded_sender))
            
            # 【新增功能】解析郵件內文並尋找連結
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                        break
            else:
                body = email_message.get_payload(decode=True).decode(email_message.get_content_charset() or 'utf-8', errors='ignore')

            # 使用正規表示式尋找 http, https, meet.google.com, zoom.us 的連結
            link_pattern = r'https?://[\w\./-]*'
            found_link_match = re.search(link_pattern, body)
            found_link = found_link_match.group(0) if found_link_match else ""

            potential_meetings.append({
                "subject": subject,
                "sender": sender,
                "snippet": msg.get("snippet", ""),
                "link": found_link # <-- 把找到的連結也加進去
            })
        
        return potential_meetings

    except HttpError as error:
        print(f"掃描郵件時發生錯誤: {error}"); return []