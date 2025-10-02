# reminder_syncer.py (修正後)

import subprocess
import json
from datetime import datetime, timedelta, time

def create_reminder(title, due_date_str, list_name="提醒事項"):
    """
    使用 AppleScript 在 macOS 的「提醒事項」App 中建立一個新的提醒。

    :param title: 提醒事項的標題。
    :param due_date_str: YYYY-MM-DD 格式的日期字串。
    :param list_name: 要加入到哪個提醒事項列表，預設是 "提醒事項"。
    """
    print(f"正在嘗試建立提醒：'{title}'，日期：{due_date_str}")

    try:
        # 【修改】將日期字串轉換成 date 物件
        date_part = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        # 【修改】將日期和上午 9 點的時間結合，變成一個完整的 datetime 物件
        due_datetime_obj = datetime.combine(date_part, time(9, 0))
        
        # 【修改】組裝正確的 AppleScript 命令，移除了錯誤的 "remind me time" 屬性
        applescript_command = f'''
        tell application "Reminders"
            tell list "{list_name}"
                make new reminder with properties {{name:"{title}", due date:date "{due_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")}"}}
            end tell
        end tell
        '''

        # 使用 subprocess 模組來執行 AppleScript 命令
        result = subprocess.run(
            ['osascript', '-e', applescript_command],
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"✅ 成功！提醒 '{title}' 已建立。")
        print("請檢查你 Mac 和 iPhone 上的「提醒事項」App。")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ 建立提醒失敗！")
        print(f"AppleScript 錯誤訊息: {e.stderr}")
        return False
    except ValueError:
        print(f"❌ 日期格式錯誤: '{due_date_str}'。請使用 YYYY-MM-DD 格式。")
        return False

# --- 測試區塊 ---
if __name__ == "__main__":
    print("--- 開始測試提醒事項建立功能 ---")
    
    # 獲取明天的日期作為測試日期
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 測試一個有效的任務
    create_reminder("完成專題報告的最終版", tomorrow)
    
    print("\n--- 測試結束 ---")