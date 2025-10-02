# google_calendar_service.py (修正路徑問題)

import os
import datetime as dt

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- 【新增】自動計算絕對路徑 ---
# 獲取這個 .py 檔案所在的資料夾的絕對路徑
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
# 組合出 credentials.json 和 token.json 的絕對路徑
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(SCRIPT_DIR, 'token.json')
# --------------------------------

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    creds = None
    # 【修改】使用絕對路徑來讀取 token.json
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # 【修改】使用絕對路徑來讀取 credentials.json
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 【修改】使用絕對路徑來寫入 token.json
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    
    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        print(f"建立 service 時發生錯誤: {error}")
        return None

def create_google_meet_event(service, summary, start_time, end_time, attendees=None, description=""):
        """
        在 Google 日曆上建立一個新的活動，並自動生成 Google Meet 連結。
        【修改】現在可以接收與會者 email 列表和會議說明。
        """
        if attendees is None:
            attendees = []

        event = {
            "summary": summary,
            "description": description, # <-- 【新增】將傳入的 description 加到活動中
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "Asia/Taipei",
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "Asia/Taipei",
            },
            "attendees": [{"email": email} for email in attendees],
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meet-{dt.datetime.now().timestamp()}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {
                "useDefault": True,
            },
        }

        try:
            created_event = service.events().insert(
                calendarId="primary", 
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all" 
            ).execute()
            
            meet_link = created_event.get("hangoutLink")
            print(f"✅ 活動建立成功！會議連結: {meet_link}")
            return meet_link
        except HttpError as error:
            print(f"建立活動時發生錯誤: {error}")
            return None
if __name__ == "__main__":
    print("--- 開始測試 Google Calendar API 功能 ---")
    service = get_calendar_service()
    if service:
        now = dt.datetime.now(dt.timezone.utc)
        start = now + dt.timedelta(hours=1)
        end = start + dt.timedelta(hours=1)
        create_google_meet_event(service, "Python 自動化測試會議", start, end)
    print("--- 測試結束 ---")