# main_gui.py (整合會議連結功能)

import sys
import webbrowser # 【新匯入】用來打開瀏覽器
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QLineEdit, QPushButton, QMessageBox, QListWidgetItem,
    QTabWidget, QDateEdit, QLabel, QMenu, QFileDialog,
    QDialog, QDialogButtonBox, QCheckBox, QTimeEdit, QPlainTextEdit
)
from PyQt6.QtGui import QColor, QAction
from PyQt6.QtCore import Qt, QDate

from task_logic import TaskManager
from google_calendar_service import get_calendar_service, create_google_meet_event # <--- 新增這行
from datetime import datetime, timedelta, time 

class PatchedPlainTextEdit(QPlainTextEdit):
    """
    一個修補過的 QPlainTextEdit，專門用來解決 macOS 上的中文輸入法問題。
    它會在使用者點擊這個輸入框時，強制重設輸入法狀態。
    """
    def focusInEvent(self, event):
        # 在繼承原始行為的基礎上，增加我們的修正
        super().focusInEvent(event)
        QApplication.instance().inputMethod().reset()# <--- 新增這行，確保我們有時間工具
# ... (ImportPreviewDialog 和 QuickCaptureDialog Class 維持不變) ...
class ImportPreviewDialog(QDialog):
    def __init__(self, potential_tasks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("預覽匯入任務")
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)
        self.checkboxes = []
        for task in potential_tasks:
            due_date_str = f" (截止: {task['due_date']})" if task['due_date'] else ""
            checkbox = QCheckBox(f"{task['title']}{due_date_str}")
            checkbox.setChecked(True)
            self.layout.addWidget(checkbox)
            self.checkboxes.append((checkbox, task))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
    def get_selected_tasks(self):
        selected_tasks = []
        for checkbox, task_data in self.checkboxes:
            if checkbox.isChecked():
                selected_tasks.append(task_data)
        return selected_tasks
class QuickCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("會議速記模式")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(350)
        self.layout = QVBoxLayout(self)
        self.capture_input = QLineEdit()
        self.capture_input.setPlaceholderText("輸入任務後按 Enter 新增...")
        self.info_label = QLabel("在此輸入的任務會自動加入主列表。")
        self.info_label.setStyleSheet("color: gray;")
        self.layout.addWidget(self.capture_input)
        self.layout.addWidget(self.info_label)
        self.capture_input.returnPressed.connect(self.add_task_and_clear)
    def add_task_and_clear(self):
        title = self.capture_input.text().strip()
        if title and self.main_window:
            self.main_window.task_manager.add_task(title)
            self.capture_input.clear()
            self.main_window.refresh_all_lists()

class TaskManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.task_manager = TaskManager()
        self.initUI()
        self.refresh_all_lists()

    def initUI(self):
        self.setWindowTitle("智慧任務排程與進度追蹤器 v2.4")
        self.setGeometry(200, 200, 700, 750)

        # --- 1. 建立分頁元件 ---
        # (此處完全不變)
        self.tabs = QTabWidget()
        self.tab_all = QWidget()
        self.tab_todo = QWidget()
        self.tab_inprogress = QWidget()
        self.tab_done = QWidget()
        self.tabs.addTab(self.tab_all, "全部")
        self.tabs.addTab(self.tab_todo, "待辦")
        self.tabs.addTab(self.tab_inprogress, "進行中")
        self.tabs.addTab(self.tab_done, "已完成")
        self.list_all = self.create_list_widget()
        self.list_todo = self.create_list_widget()
        self.list_inprogress = self.create_list_widget()
        self.list_done = self.create_list_widget()
        self.setup_tab_layout(self.tab_all, self.list_all)
        self.setup_tab_layout(self.tab_todo, self.list_todo)
        self.setup_tab_layout(self.tab_inprogress, self.list_inprogress)
        self.setup_tab_layout(self.tab_done, self.list_done)
        
        # --- 2. 建立輸入區元件 ---
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("在這裡輸入任務標題...")
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("貼上會議連結 (或由下方自動建立)...")
        self.attendees_input = QLineEdit()
        self.attendees_input.setPlaceholderText("輸入與會者 Email，用逗號分隔...")
        self.description_input = PatchedPlainTextEdit()
        self.description_input.setPlaceholderText("請在此輸入會議說明或議程...")
        self.description_input.setFixedHeight(80)
        self.due_date_edit = QDateEdit(calendarPopup=True)
        self.due_date_edit.setDate(QDate.currentDate())
        
        # 【修改】建立「開始時間」和「結束時間」兩個選擇器
        self.meet_start_time_edit = QTimeEdit()
        self.meet_end_time_edit = QTimeEdit()
        
        self.create_meet_button = QPushButton("📅 自動建立會議")
        self.add_button = QPushButton("新增任務")
        self.import_button = QPushButton("從會議記錄匯入")
        self.meeting_mode_button = QPushButton("會議模式")
        
        # --- 3. 設定整體佈局 ---
        main_layout = QVBoxLayout()
        
        input_layout_1 = QHBoxLayout()
        input_layout_1.addWidget(QLabel("任務:"))
        input_layout_1.addWidget(self.task_input)
        input_layout_1.addWidget(QLabel("會議日期:"))
        input_layout_1.addWidget(self.due_date_edit)

        # 【修改】第二行佈局，現在用來放時間區間
        input_layout_2 = QHBoxLayout()
        input_layout_2.addWidget(QLabel("會議時間:"))
        input_layout_2.addWidget(self.meet_start_time_edit) # 開始時間
        input_layout_2.addWidget(QLabel("到"))
        input_layout_2.addWidget(self.meet_end_time_edit)   # 結束時間
        input_layout_2.addWidget(QLabel("連結:"))
        input_layout_2.addWidget(self.link_input)
        
        input_layout_3 = QHBoxLayout()
        input_layout_3.addWidget(QLabel("邀請:"))
        input_layout_3.addWidget(self.attendees_input)

        description_layout = QVBoxLayout()
        description_layout.addWidget(QLabel("會議說明:"))
        description_layout.addWidget(self.description_input)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.create_meet_button)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.meeting_mode_button)

        main_layout.addWidget(self.tabs)
        main_layout.addLayout(input_layout_1)
        main_layout.addLayout(input_layout_2)
        main_layout.addLayout(input_layout_3)
        main_layout.addLayout(description_layout)
        main_layout.addLayout(button_layout)
        main_layout.addStretch(1)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # --- 4. 連接訊號與槽 ---
        # (此處暫時不變)
        self.add_button.clicked.connect(self.handle_add_task)
        self.create_meet_button.clicked.connect(self.handle_create_meet)
        self.import_button.clicked.connect(self.handle_import_tasks)
        self.meeting_mode_button.clicked.connect(self.handle_meeting_mode)
        self.task_input.returnPressed.connect(self.handle_add_task)
    # --- 6. 輔助與功能函式 ---
    def create_list_widget(self):
        list_widget = QListWidget()
        list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        list_widget.customContextMenuRequested.connect(self.show_context_menu)
        return list_widget
    def setup_tab_layout(self, tab, list_widget):
        layout = QVBoxLayout()
        layout.addWidget(list_widget)
        tab.setLayout(layout)
    def refresh_all_lists(self):
        all_tasks = self.task_manager.list_tasks()
        self.list_all.clear()
        self.list_todo.clear()
        self.list_inprogress.clear()
        self.list_done.clear()
        for task in all_tasks:
            item = QListWidgetItem()
            self.update_item_display(item, task)
            self.list_all.addItem(item.clone())
            if task.status == "待辦":
                self.list_todo.addItem(item.clone())
            elif task.status == "進行中":
                self.list_inprogress.addItem(item.clone())
            elif task.status == "已完成":
                self.list_done.addItem(item.clone())
    def update_item_display(self, item, task):
        """【修改】在任務標題後方加上會議圖示"""
        due_date_str = f" (截止: {task.due_date})" if task.due_date else ""
        meeting_icon = " 📹" if task.meeting_link else "" # 如果有連結，就加上攝影機圖示
        item.setText(f"[{task.status}] {task.title}{due_date_str}{meeting_icon}")
        item.setData(Qt.ItemDataRole.UserRole, task.task_id)
        item.setBackground(QColor("white"))
        item.setForeground(QColor("black"))
        if task.status == "已完成":
            item.setBackground(QColor("#d4edda"))
        elif task.status == "進行中":
            item.setBackground(QColor("#fff3cd"))
        if task.due_date and date.fromisoformat(task.due_date) < date.today() and task.status != "已完成":
            item.setForeground(QColor("#dc3545"))

    def handle_add_task(self):
        """【修改】新增任務時，也把連結加進去"""
        title = self.task_input.text().strip()
        if not title:
            QMessageBox.warning(self, "輸入錯誤", "任務標題不能為空！")
            return
        
        due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        link = self.link_input.text().strip() # 獲取連結輸入框的文字
        
        # 呼叫後端邏輯時，把 link 傳進去
        self.task_manager.add_task(title, due_date=due_date, meeting_link=link)
        
        self.task_input.clear()
        self.link_input.clear() # 清空連結輸入框
        self.refresh_all_lists()

    def handle_create_meet(self):
        """
        處理點擊「自動建立會議」按鈕的邏輯。
        【修改】現在會讀取開始與結束時間來建立精確的時間區間。
        """
        # 1. 獲取使用者輸入的標題
        title = self.task_input.text().strip()
        if not title:
            QMessageBox.warning(self, "輸入錯誤", "請先輸入會議的標題！")
            return

        # 2. 【修改】組合日期和「開始/結束」時間
        selected_date = self.due_date_edit.date().toPyDate()
        start_qtime = self.meet_start_time_edit.time().toPyTime()
        end_qtime = self.meet_end_time_edit.time().toPyTime()
        
        start_time = datetime.combine(selected_date, start_qtime)
        end_time = datetime.combine(selected_date, end_qtime)

        # 新增一個檢查，確保結束時間晚於開始時間
        if end_time <= start_time:
            QMessageBox.warning(self, "時間錯誤", "結束時間必須晚於開始時間！")
            return
        
        # 3. 讀取與會者 Email 和會議說明 (這部分不變)
        attendees_text = self.attendees_input.text().strip()
        attendees = [email.strip() for email in attendees_text.split(',') if email.strip()]
        description = self.description_input.toPlainText().strip()
        
        # 4. 呼叫 Google Calendar 服務 (這部分不變)
        try:
            print("正在獲取 Google Calendar service...")
            service = get_calendar_service()
            if not service:
                QMessageBox.critical(self, "錯誤", "無法連接到 Google 日曆服務。")
                return
            
            print(f"正在建立 Google Meet 活動，邀請: {attendees}")
            QMessageBox.information(self, "處理中", "正在為您建立 Google Meet 會議並發送邀請，請稍候...")

            meet_link = create_google_meet_event(
                service, 
                title, 
                start_time, 
                end_time, 
                attendees=attendees, 
                description=description
            )
            
            # 5. 處理結果 (這部分不變)
            if meet_link:
                self.link_input.setText(meet_link)
                QMessageBox.information(self, "成功", f"會議建立且邀請已發送！\n連結已自動填入，請記得按下「新增任務」來儲存。")
            else:
                QMessageBox.warning(self, "失敗", "無法建立 Google Meet 會議，請檢查終端機的錯誤訊息。")

        except Exception as e:
            QMessageBox.critical(self, "發生預期外的錯誤", f"發生錯誤: {e}")
            print(f"處理 handle_create_meet 時發生錯誤: {e}")
    

    def show_context_menu(self, pos):
        """【修改】在右鍵選單中，動態加入「加入會議」的選項"""
        list_widget = self.sender()
        item = list_widget.itemAt(pos)
        if not item:
            return
        task_id = item.data(Qt.ItemDataRole.UserRole)
        task = self.task_manager.get_task(task_id)
        if not task:
            return

        menu = QMenu()
        
        # 如果這個任務有會議連結，就在選單最上方加入「加入會議」的選項
        if task.meeting_link:
            join_action = menu.addAction("➡️ 加入會議")
            join_action.triggered.connect(lambda: self.handle_join_meeting(task.meeting_link))
            menu.addSeparator()

        # ... (下方修改狀態和刪除的選項維持不變) ...
        if task.status != "待辦":
            set_todo_action = menu.addAction("設定為「待辦」")
            set_todo_action.triggered.connect(lambda: self.set_task_status(task_id, "待辦"))
        if task.status != "進行中":
            set_inprogress_action = menu.addAction("設定為「進行中」")
            set_inprogress_action.triggered.connect(lambda: self.set_task_status(task_id, "進行中"))
        if task.status != "已完成":
            set_done_action = menu.addAction("設定為「已完成」")
            set_done_action.triggered.connect(lambda: self.set_task_status(task_id, "已完成"))
        menu.addSeparator()
        delete_action = menu.addAction("刪除任務")
        delete_action.triggered.connect(lambda: self.handle_delete_task(task_id))
        
        menu.exec(list_widget.mapToGlobal(pos))

    # 【新增】一個專門用來打開瀏覽器的函式
    def handle_join_meeting(self, link):
        """使用 webbrowser 模組在預設瀏覽器中打開連結"""
        if not link.startswith("http"):
            link = "https://" + link # 簡單的處理，確保是有效連結
        webbrowser.open(link)

    def set_task_status(self, task_id, status):
        self.task_manager.update_task_status(task_id, status)
        self.refresh_all_lists()
    def handle_delete_task(self, task_id):
        self.task_manager.delete_task(task_id)
        self.refresh_all_lists()
    def handle_import_tasks(self):
        filepath, _ = QFileDialog.getOpenFileName(self,"選擇會議記錄檔案","","Text Files (*.txt);;All Files (*)")
        if not filepath:
            return
        potential_tasks = self.task_manager.parse_meeting_minutes(filepath)
        if not potential_tasks:
            QMessageBox.information(self, "匯入完成", "在檔案中沒有找到符合格式的任務。")
            return
        dialog = ImportPreviewDialog(potential_tasks, self)
        if dialog.exec():
            selected_tasks = dialog.get_selected_tasks()
            tasks_added_count = 0
            for task_data in selected_tasks:
                if self.task_manager.add_task(task_data["title"], due_date=task_data["due_date"]):
                    tasks_added_count += 1
            QMessageBox.information(self, "匯入成功", f"成功匯入了 {tasks_added_count} 項任務。")
            self.refresh_all_lists()
    def handle_meeting_mode(self):
        dialog = QuickCaptureDialog(self)
        dialog.show()

def main():
    app = QApplication(sys.argv)
    window = TaskManagerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()