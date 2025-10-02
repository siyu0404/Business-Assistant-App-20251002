# task_logic.py (修正路徑問題)

import uuid
import json
import os
from datetime import datetime, date

# --- 【新增】自動計算 tasks.json 的絕對路徑 ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_FILENAME = os.path.join(SCRIPT_DIR, 'tasks.json')
# --------------------------------

class Task:
    # ... (Task Class 的內容完全不變，請保留你原本的) ...
    def __init__(self, title, description="", status="待辦", due_date=None, meeting_link=None, task_id=None, created_at=None):
        self.task_id = task_id if task_id else str(uuid.uuid4())
        self.title = title
        self.description = description
        self.status = status
        self.created_at = created_at if created_at else datetime.now().isoformat()
        self.due_date = due_date
        self.meeting_link = meeting_link
    def to_dict(self):
        return {
            "task_id": self.task_id, "title": self.title, "description": self.description,
            "status": self.status, "created_at": self.created_at, "due_date": self.due_date,
            "meeting_link": self.meeting_link
        }
    @classmethod
    def from_dict(cls, data_dict):
        return cls(
            title=data_dict["title"], description=data_dict.get("description", ""),
            status=data_dict["status"], task_id=data_dict["task_id"],
            created_at=data_dict["created_at"], due_date=data_dict.get("due_date"),
            meeting_link=data_dict.get("meeting_link")
        )
    def __str__(self):
        due_date_str = f" (截止: {self.due_date})" if self.due_date else ""
        meeting_str = " [會議]" if self.meeting_link else ""
        return f"ID: {self.task_id[:8]:<10} 狀態: {self.status:<5} 標題: {self.title}{due_date_str}{meeting_str}"

class TaskManager:
    # 【修改】讓初始化方法使用我們計算好的絕對路徑
    def __init__(self, filename=DEFAULT_FILENAME):
        self.filename = filename
        self.tasks = self._load_tasks()

    def _load_tasks(self):
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
                return [Task.from_dict(data) for data in tasks_data]
        except (json.JSONDecodeError, IOError):
            return []

    # ... (其他所有函式，例如 _save_tasks, add_task, list_tasks 等，都維持不變) ...
    def _save_tasks(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            tasks_data = [task.to_dict() for task in self.tasks]
            json.dump(tasks_data, f, ensure_ascii=False, indent=4)
    def add_task(self, title, description="", due_date=None, meeting_link=None):
        if not title: return False
        new_task = Task(title, description, due_date=due_date, meeting_link=meeting_link)
        self.tasks.append(new_task)
        self._save_tasks()
        return True
    def list_tasks(self):
        if not self.tasks: return []
        sorted_tasks = sorted(self.tasks, key=lambda t: (t.due_date or '9999-12-31', t.created_at))
        return sorted_tasks
    def get_task(self, task_id):
        return next((task for task in self.tasks if task.task_id == task_id), None)
    def update_task_status(self, task_id, new_status):
        task = self.get_task(task_id)
        if task:
            valid_statuses = ["待辦", "進行中", "已完成"]
            if new_status in valid_statuses:
                task.status = new_status
                self._save_tasks()
                return True
        return False
    def delete_task(self, task_id):
        task = self.get_task(task_id)
        if task:
            self.tasks.remove(task)
            self._save_tasks()
            return True
        return False
    def parse_meeting_minutes(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            return []
        import re
        potential_tasks = []
        task_blocks = re.findall(r'\* \*\*任務:\*\*(.*?)(?=\* \*\*任務:\*\*|\Z)', content, re.DOTALL)
        for block in task_blocks:
            title_match = re.search(r'(.*?)\n', block.strip())
            owner_match = re.search(r'\*\*負責人:\*\*\s*(.*?)\n', block)
            due_date_match = re.search(r'\*\*截止日期:\*\*\s*(.*?)\n', block)
            title = title_match.group(1).strip() if title_match else "標題未找到"
            owner = owner_match.group(1).strip() if owner_match and owner_match.group(1).strip() else ""
            if owner:
                title = f"{title} ({owner})"
            due_date = due_date_match.group(1).strip() if due_date_match and due_date_match.group(1).strip() else None
            potential_tasks.append({"title": title, "due_date": due_date})
        return potential_tasks