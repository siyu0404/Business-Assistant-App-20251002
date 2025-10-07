# main_gui.py (最終版本 v2.7)

import sys
import webbrowser
import re
from datetime import datetime, date, timedelta, time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QLineEdit, QPushButton, QMessageBox, QListWidgetItem,
    QTabWidget, QDateEdit, QLabel, QMenu, QFileDialog,
    QDialog, QDialogButtonBox, QCheckBox, QTimeEdit, QPlainTextEdit
)
from PyQt6.QtGui import QColor, QAction
from PyQt6.QtCore import Qt, QDate

# 從 googleapiclient 匯入 build，因為現在要在這裡建立 service
from googleapiclient.discovery import build

from task_logic import TaskManager
# 匯入我們重構後的函式
from google_calendar_service import get_google_credentials, create_google_meet_event, scan_potential_meeting_emails

# --- 特製的中文輸入框 Class ---
class PatchedPlainTextEdit(QPlainTextEdit):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QApplication.instance().inputMethod().reset()

# --- 彈出視窗 Class 定義 ---
class ImportPreviewDialog(QDialog):
    def __init__(self, potential_tasks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("預覽匯入任務"); self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self); self.checkboxes = []
        for task in potential_tasks:
            due_date_str = f" (截止: {task['due_date']})" if task['due_date'] else ""
            checkbox = QCheckBox(f"{task['title']}{due_date_str}"); checkbox.setChecked(True)
            self.layout.addWidget(checkbox); self.checkboxes.append((checkbox, task))
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
    def get_selected_tasks(self):
        selected_tasks = []
        for checkbox, task_data in self.checkboxes:
            if checkbox.isChecked(): selected_tasks.append(task_data)
        return selected_tasks

class QuickCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("會議速記模式"); self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(350); self.layout = QVBoxLayout(self)
        self.capture_input = QLineEdit(); self.capture_input.setPlaceholderText("輸入任務後按 Enter 新增...")
        self.info_label = QLabel("在此輸入的任務會自動加入主列表。"); self.info_label.setStyleSheet("color: gray;")
        self.layout.addWidget(self.capture_input); self.layout.addWidget(self.info_label)
        self.capture_input.returnPressed.connect(self.add_task_and_clear)
    def add_task_and_clear(self):
        title = self.capture_input.text().strip()
        if title and self.main_window:
            self.main_window.task_manager.add_task(title)
            self.capture_input.clear()
            self.main_window.refresh_all_lists()

class EmailScanResultDialog(QDialog):
    def __init__(self, potential_emails, parent=None):
        super().__init__(parent)
        self.setWindowTitle("掃描到的會議建議"); self.setMinimumSize(500, 300)
        self.layout = QVBoxLayout(self); self.email_list_widget = QListWidget()
        self.selected_email_data = None
        if not potential_emails:
            self.layout.addWidget(QLabel("在您的收件匣中找不到符合條件的未讀郵件。"))
        else:
            for email_data in potential_emails:
                subject = email_data.get("subject", "無標題"); sender = email_data.get("sender", "未知寄件人")
                display_text = f"標題: {subject}\n來自: {sender}"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, email_data)
                self.email_list_widget.addItem(item)
            self.layout.addWidget(QLabel("請選擇一封郵件，以自動帶入資訊："))
            self.layout.addWidget(self.email_list_widget)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
    def accept(self):
        selected_items = self.email_list_widget.selectedItems()
        if selected_items: self.selected_email_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        super().accept()
    def get_selected_email(self):
        return self.selected_email_data

# --- 主應用程式 Class ---
class TaskManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.task_manager = TaskManager()
        self.initUI()
        self.refresh_all_lists()

    def initUI(self):
        self.setWindowTitle("智慧任務排程與進度追蹤器 v2.7")
        self.setGeometry(200, 200, 700, 750)
        self.tabs = QTabWidget()
        self.tab_all = QWidget(); self.tab_todo = QWidget(); self.tab_inprogress = QWidget(); self.tab_done = QWidget()
        self.tabs.addTab(self.tab_all, "全部"); self.tabs.addTab(self.tab_todo, "待辦"); self.tabs.addTab(self.tab_inprogress, "進行中"); self.tabs.addTab(self.tab_done, "已完成")
        self.list_all = self.create_list_widget(); self.list_todo = self.create_list_widget(); self.list_inprogress = self.create_list_widget(); self.list_done = self.create_list_widget()
        self.setup_tab_layout(self.tab_all, self.list_all); self.setup_tab_layout(self.tab_todo, self.list_todo); self.setup_tab_layout(self.tab_inprogress, self.list_inprogress); self.setup_tab_layout(self.tab_done, self.list_done)
        self.task_input = QLineEdit(); self.task_input.setPlaceholderText("在這裡輸入任務標題...")
        self.link_input = QLineEdit(); self.link_input.setPlaceholderText("貼上會議連結 (或由下方自動建立)...")
        self.attendees_input = QLineEdit(); self.attendees_input.setPlaceholderText("輸入與會者 Email，用逗號分隔...")
        self.description_input = PatchedPlainTextEdit(); self.description_input.setPlaceholderText("請在此輸入會議說明或議程..."); self.description_input.setFixedHeight(80)
        self.due_date_edit = QDateEdit(calendarPopup=True); self.due_date_edit.setDate(QDate.currentDate())
        self.meet_start_time_edit = QTimeEdit(); self.meet_end_time_edit = QTimeEdit()
        self.create_meet_button = QPushButton("📅 自動建立會議"); self.add_button = QPushButton("新增任務"); self.import_button = QPushButton("從會議記錄匯入"); self.meeting_mode_button = QPushButton("會議模式"); self.scan_emails_button = QPushButton("📧 掃描郵件建議")
        main_layout = QVBoxLayout()
        input_layout_1 = QHBoxLayout(); input_layout_1.addWidget(QLabel("任務:")); input_layout_1.addWidget(self.task_input); input_layout_1.addWidget(QLabel("會議日期:")); input_layout_1.addWidget(self.due_date_edit)
        input_layout_2 = QHBoxLayout(); input_layout_2.addWidget(QLabel("會議時間:")); input_layout_2.addWidget(self.meet_start_time_edit); input_layout_2.addWidget(QLabel("到")); input_layout_2.addWidget(self.meet_end_time_edit); input_layout_2.addWidget(QLabel("連結:")); input_layout_2.addWidget(self.link_input)
        input_layout_3 = QHBoxLayout(); input_layout_3.addWidget(QLabel("邀請:")); input_layout_3.addWidget(self.attendees_input)
        description_layout = QVBoxLayout(); description_layout.addWidget(QLabel("會議說明:")); description_layout.addWidget(self.description_input)
        button_layout = QHBoxLayout(); button_layout.addWidget(self.scan_emails_button); button_layout.addWidget(self.import_button); button_layout.addStretch(1); button_layout.addWidget(self.create_meet_button); button_layout.addWidget(self.add_button)
        main_layout.addWidget(self.tabs); main_layout.addLayout(input_layout_1); main_layout.addLayout(input_layout_2); main_layout.addLayout(input_layout_3); main_layout.addLayout(description_layout); main_layout.addLayout(button_layout); main_layout.addStretch(1)
        central_widget = QWidget(); central_widget.setLayout(main_layout); self.setCentralWidget(central_widget)
        self.add_button.clicked.connect(self.handle_add_task); self.create_meet_button.clicked.connect(self.handle_create_meet); self.import_button.clicked.connect(self.handle_import_tasks); self.meeting_mode_button.clicked.connect(self.handle_meeting_mode); self.scan_emails_button.clicked.connect(self.handle_scan_emails); self.task_input.returnPressed.connect(self.handle_add_task)

    def create_list_widget(self):
        list_widget = QListWidget(); list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); list_widget.customContextMenuRequested.connect(self.show_context_menu)
        return list_widget
    def setup_tab_layout(self, tab, list_widget):
        layout = QVBoxLayout(); layout.addWidget(list_widget); tab.setLayout(layout)
    def refresh_all_lists(self):
        all_tasks = self.task_manager.list_tasks(); self.list_all.clear(); self.list_todo.clear(); self.list_inprogress.clear(); self.list_done.clear()
        for task in all_tasks:
            item = QListWidgetItem(); self.update_item_display(item, task); self.list_all.addItem(item.clone())
            if task.status == "待辦": self.list_todo.addItem(item.clone())
            elif task.status == "進行中": self.list_inprogress.addItem(item.clone())
            elif task.status == "已完成": self.list_done.addItem(item.clone())
    def update_item_display(self, item, task):
        due_date_str = f" (截止: {task.due_date})" if task.due_date else ""; meeting_icon = " 📹" if task.meeting_link else ""
        item.setText(f"[{task.status}] {task.title}{due_date_str}{meeting_icon}"); item.setData(Qt.ItemDataRole.UserRole, task.task_id)
        item.setBackground(QColor("white")); item.setForeground(QColor("black"))
        if task.status == "已完成": item.setBackground(QColor("#d4edda"))
        elif task.status == "進行中": item.setBackground(QColor("#fff3cd"))
        if task.due_date and date.fromisoformat(task.due_date) < date.today() and task.status != "已完成": item.setForeground(QColor("#dc3545"))
    def handle_add_task(self):
        title = self.task_input.text().strip()
        if not title: QMessageBox.warning(self, "輸入錯誤", "任務標題不能為空！"); return
        due_date = self.due_date_edit.date().toString("yyyy-MM-dd"); link = self.link_input.text().strip()
        self.task_manager.add_task(title, due_date=due_date, meeting_link=link)
        self.task_input.clear(); self.link_input.clear(); self.attendees_input.clear(); self.description_input.clear(); self.refresh_all_lists()

    def handle_create_meet(self):
        title = self.task_input.text().strip()
        if not title: QMessageBox.warning(self, "輸入錯誤", "請先輸入會議的標題！"); return
        selected_date = self.due_date_edit.date().toPyDate()
        start_qtime = self.meet_start_time_edit.time().toPyTime(); end_qtime = self.meet_end_time_edit.time().toPyTime()
        start_time = datetime.combine(selected_date, start_qtime); end_time = datetime.combine(selected_date, end_qtime)
        if end_time <= start_time: QMessageBox.warning(self, "時間錯誤", "結束時間必須晚於開始時間！"); return
        attendees_text = self.attendees_input.text().strip()
        attendees = [email.strip() for email in attendees_text.split(',') if email.strip()]
        description = self.description_input.toPlainText().strip()
        try:
            print("正在獲取 Google Credentials...")
            creds = get_google_credentials()
            if not creds: QMessageBox.critical(self, "錯誤", "無法獲取 Google 憑證。"); return
            
            calendar_service = build("calendar", "v3", credentials=creds)
            
            QMessageBox.information(self, "處理中", "正在為您建立 Google Meet 會議並發送邀請，請稍候...")
            meet_link = create_google_meet_event(calendar_service, title, start_time, end_time, attendees=attendees, description=description)
            
            if meet_link:
                self.link_input.setText(meet_link)
                QMessageBox.information(self, "成功", f"會議建立且邀請已發送！\n連結已自動填入，請記得按下「新增任務」來儲存。")
            else:
                QMessageBox.warning(self, "失敗", "無法建立 Google Meet 會議，請檢查終端機的錯誤訊息。")
        except Exception as e:
            QMessageBox.critical(self, "發生預期外的錯誤", f"發生錯誤: {e}")
            print(f"處理 handle_create_meet 時發生錯誤: {e}")

    def handle_scan_emails(self):
        QMessageBox.information(self, "處理中", "正在掃描您的 Gmail 收件匣，請稍候...")
        try:
            creds = get_google_credentials()
            if not creds:
                QMessageBox.critical(self, "錯誤", "無法獲取 Google 憑證。"); return

            potential_emails = scan_potential_meeting_emails(creds)
            dialog = EmailScanResultDialog(potential_emails, self)
            
            if dialog.exec():
                selected_email = dialog.get_selected_email()
                if selected_email:
                    self.task_input.setText(selected_email.get("subject", ""))
                    
                    sender_full = selected_email.get("sender", "")
                    sender_email = self._parse_email_from_sender(sender_full)
                    self.attendees_input.setText(sender_email)
                    
                    self.description_input.setPlainText(selected_email.get("snippet", ""))

                    # 【新增】如果掃描結果包含連結，就自動填入
                    found_link = selected_email.get("link", "")
                    if found_link:
                        self.link_input.setText(found_link)
                    
                    QMessageBox.information(self, "帶入成功", "郵件資訊已成功帶入，請設定會議時間。")
        except Exception as e:
            QMessageBox.critical(self, "發生預期外的錯誤", f"掃描郵件時發生錯誤: {e}")
            print(f"處理 handle_scan_emails 時發生錯誤: {e}")

    def _parse_email_from_sender(self, sender_full):
        match = re.search(r'<(.+?)>', sender_full)
        if match: return match.group(1)
        return sender_full

    def show_context_menu(self, pos):
        list_widget = self.sender(); item = list_widget.itemAt(pos)
        if not item: return
        task_id = item.data(Qt.ItemDataRole.UserRole); task = self.task_manager.get_task(task_id)
        if not task: return
        menu = QMenu()
        if task.meeting_link:
            join_action = menu.addAction("➡️ 加入會議"); join_action.triggered.connect(lambda: self.handle_join_meeting(task.meeting_link)); menu.addSeparator()
        if task.status != "待辦":
            set_todo_action = menu.addAction("設定為「待辦」"); set_todo_action.triggered.connect(lambda: self.set_task_status(task_id, "待辦"))
        if task.status != "進行中":
            set_inprogress_action = menu.addAction("設定為「進行中」"); set_inprogress_action.triggered.connect(lambda: self.set_task_status(task_id, "進行中"))
        if task.status != "已完成":
            set_done_action = menu.addAction("設定為「已完成」"); set_done_action.triggered.connect(lambda: self.set_task_status(task_id, "已完成"))
        menu.addSeparator()
        delete_action = menu.addAction("刪除任務"); delete_action.triggered.connect(lambda: self.handle_delete_task(task_id))
        menu.exec(list_widget.mapToGlobal(pos))
    def handle_join_meeting(self, link):
        if not link.startswith("http"): link = "https://" + link
        webbrowser.open(link)
    def set_task_status(self, task_id, status):
        self.task_manager.update_task_status(task_id, status); self.refresh_all_lists()
    def handle_delete_task(self, task_id):
        self.task_manager.delete_task(task_id); self.refresh_all_lists()
    def handle_import_tasks(self):
        filepath, _ = QFileDialog.getOpenFileName(self,"選擇會議記錄檔案","","Text Files (*.txt);;All Files (*)")
        if not filepath: return
        potential_tasks = self.task_manager.parse_meeting_minutes(filepath)
        if not potential_tasks: QMessageBox.information(self, "匯入完成", "在檔案中沒有找到符合格式的任務。"); return
        dialog = ImportPreviewDialog(potential_tasks, self)
        if dialog.exec():
            selected_tasks = dialog.get_selected_tasks(); tasks_added_count = 0
            for task_data in selected_tasks:
                if self.task_manager.add_task(task_data["title"], due_date=task_data["due_date"]): tasks_added_count += 1
            QMessageBox.information(self, "匯入成功", f"成功匯入了 {tasks_added_count} 項任務。")
            self.refresh_all_lists()
    def handle_meeting_mode(self):
        dialog = QuickCaptureDialog(self); dialog.show()

# --- 程式進入點 (引擎點火開關) ---
def main():
    app = QApplication(sys.argv)
    window = TaskManagerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()