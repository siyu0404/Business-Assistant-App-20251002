# run_daily_sync.py

import json
from datetime import date
import os

# 從我們寫好的工具檔案中，匯入建立提醒的函式
from reminder_syncer import create_reminder

# --- 設定 ---
# 我們的任務數據儲存在哪裡
TASKS_FILE_PATH = "tasks.json"

def sync_tasks_for_today():
    """
    讀取 tasks.json 檔案，找出今天到期的任務，並為它們建立提醒事項。
    """
    print(f"[{date.today()}] 開始執行每日任務同步...")

    # 1. 檢查 tasks.json 檔案是否存在
    if not os.path.exists(TASKS_FILE_PATH):
        print(f"找不到任務檔案 {TASKS_FILE_PATH}。結束執行。")
        return

    # 2. 讀取並解析 JSON 檔案
    try:
        with open(TASKS_FILE_PATH, 'r', encoding='utf-8') as f:
            all_tasks = json.load(f)
    except (json.JSONDecodeError, IOError):
        print(f"讀取或解析 {TASKS_FILE_PATH} 失敗。檔案可能為空或格式錯誤。")
        return

    if not all_tasks:
        print("任務清單為空，沒有需要同步的任務。")
        return

    # 3. 找出今天到期的任務
    todays_date_str = date.today().strftime("%Y-%m-%d")
    tasks_due_today = []
    for task in all_tasks:
        # 確保任務有 due_date 且不為 None，並且等於今天的日期
        if task.get("due_date") == todays_date_str:
            tasks_due_today.append(task)

    # 4. 為找到的任務建立提醒
    if not tasks_due_today:
        print(f"檢查完畢。今天 ({todays_date_str}) 沒有到期的任務。")
    else:
        print(f"找到 {len(tasks_due_today)} 個今天到期的任務，正在同步...")
        success_count = 0
        for task in tasks_due_today:
            title = task.get("title", "無標題任務")
            due_date = task.get("due_date")
            if create_reminder(title, due_date):
                success_count += 1
        print(f"同步完成！成功建立了 {success_count} 個提醒事項。")

if __name__ == "__main__":
    sync_tasks_for_today()