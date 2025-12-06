#!/usr/bin/env python3
"""
Simple AI Task Assistant (CLI)
- Add / list / complete / delete tasks
- Save & load tasks from JSON
- Due dates + priority
- Simple "smart suggestions" (overdue, due soon)
- Productivity score (points for completed tasks)
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from typing import List, Optional

DB = Path("tasks.json")
DATE_FORMAT = "%Y-%m-%d"  # simple ISO-like date format

# ---------- Data model ----------
@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    due: Optional[str] = None   # stored as "YYYY-MM-DD" string or None
    priority: int = 3           # 1 (high) .. 5 (low)
    done: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None

    def is_overdue(self) -> bool:
        if self.done or not self.due:
            return False
        try:
            due_dt = datetime.strptime(self.due, DATE_FORMAT).date()
            return datetime.utcnow().date() > due_dt
        except ValueError:
            return False

    def due_in_days(self) -> Optional[int]:
        if not self.due:
            return None
        try:
            due_dt = datetime.strptime(self.due, DATE_FORMAT).date()
            delta = (due_dt - datetime.utcnow().date()).days
            return delta
        except ValueError:
            return None

# ---------- Storage ----------
def load_tasks() -> List[Task]:
    if not DB.exists():
        return []
    try:
        raw = json.loads(DB.read_text())
        tasks = [Task(**t) for t in raw]
        return tasks
    except Exception:
        return []

def save_tasks(tasks: List[Task]):
    DB.write_text(json.dumps([asdict(t) for t in tasks], indent=2))

# ---------- Utilities ----------
def next_id(tasks: List[Task]) -> int:
    if not tasks:
        return 1
    return max(t.id for t in tasks) + 1

def print_task(t: Task):
    status = "✅" if t.done else "❗" if t.is_overdue() else "⏳"
    due = t.due if t.due else "No due date"
    print(f"[{t.id}] {status} {t.title} (priority {t.priority})")
    print(f"     Due: {due} | Created: {t.created_at.split('T')[0]}")
    if t.description:
        print(f"     {t.description}")
    if t.done:
        print(f"     Completed at: {t.completed_at}")
    print()

# ---------- Core features ----------
def add_task(tasks: List[Task]):
    title = input("Title: ").strip()
    if not title:
        print("Title cannot be empty.")
        return
    desc = input("Description (optional): ").strip()
    due_raw = input(f"Due date ({DATE_FORMAT}) (optional): ").strip()
    due = None
    if due_raw:
        try:
            # validate
            datetime.strptime(due_raw, DATE_FORMAT)
            due = due_raw
        except ValueError:
            print("Invalid date format. Task will have no due date.")
            due = None
    pr = input("Priority 1-5 (1=high, 5=low) [3]: ").strip()
    try:
        pr_i = int(pr) if pr else 3
        pr_i = max(1, min(5, pr_i))
    except ValueError:
        pr_i = 3

    t = Task(id=next_id(tasks), title=title, description=desc, due=due, priority=pr_i)
    tasks.append(t)
    save_tasks(tasks)
    print("Task added.")

def list_tasks(tasks: List[Task], show_all=False):
    if not tasks:
        print("No tasks found.")
        return
    # sort: not done first by priority, then due date
    pending = [t for t in tasks if not t.done]
    done = [t for t in tasks if t.done]

    def sort_key(t):
        due_days = t.due_in_days()
        # tasks with due sooner come first (smaller days), None treated as large
        return (t.priority, (due_days if due_days is not None else 9999))

    pending.sort(key=sort_key)
    print("--- Pending ---")
    for t in pending:
        print_task(t)

    if show_all:
        print("--- Done ---")
        for t in done:
            print_task(t)
    else:
        print(f"Completed tasks: {len(done)} (use 'list all' to show them)")

def complete_task(tasks: List[Task]):
    try:
        tid = int(input("Task ID to mark complete: ").strip())
    except ValueError:
        print("Invalid ID.")
        return
    for t in tasks:
        if t.id == tid:
            if t.done:
                print("Task already completed.")
                return
            t.done = True
            t.completed_at = datetime.utcnow().isoformat()
            save_tasks(tasks)
            print("Task marked complete.")
            return
    print("Task ID not found.")

def delete_task(tasks: List[Task]):
    try:
        tid = int(input("Task ID to delete: ").strip())
    except ValueError:
        print("Invalid ID.")
        return
    for i, t in enumerate(tasks):
        if t.id == tid:
            confirm = input(f"Delete '{t.title}'? (y/N): ").strip().lower()
            if confirm == "y":
                tasks.pop(i)
                save_tasks(tasks)
                print("Deleted.")
            else:
                print("Cancelled.")
            return
    print("Task ID not found.")

# ---------- Smart suggestions & scoring ----------
def suggestions(tasks: List[Task]):
    overdue = [t for t in tasks if t.is_overdue()]
    due_soon = [t for t in tasks if not t.done and t.due_in_days() is not None and 0 <= t.due_in_days() <= 2]
    high_priority = [t for t in tasks if not t.done and t.priority == 1]

    print("=== Suggestions ===")
    if overdue:
        print(f"You have {len(overdue)} overdue task(s):")
        for t in overdue[:5]:
            print(f" - [{t.id}] {t.title} (was due {t.due})")
    else:
        print("No overdue tasks. Good job!")

    if due_soon:
        print(f"\nTasks due soon (within 2 days):")
        for t in due_soon[:5]:
            print(f" - [{t.id}] {t.title} (in {t.due_in_days()} day(s))")

    if high_priority:
        print(f"\nHigh priority tasks:")
        for t in high_priority[:5]:
            print(f" - [{t.id}] {t.title} (priority {t.priority})")
    print()

def productivity_score(tasks: List[Task]):
    # basic scoring: +10 per completed task, +1 per pending high priority (as motivation)
    completed = [t for t in tasks if t.done]
    score = len(completed) * 10
    pending_high = [t for t in tasks if not t.done and t.priority == 1]
    score += len(pending_high) * 1
    print(f"Productivity score: {score}")
    print(f"Completed tasks: {len(completed)} | Pending high-priority: {len(pending_high)}")

# ---------- CLI ----------
def help_text():
    print("""
Commands:
 add        -> Add a new task
 list       -> List pending tasks
 list all   -> List pending and completed tasks
 complete   -> Mark a task complete
 delete     -> Delete a task
 suggest    -> Show smart suggestions
 score      -> Show productivity score
 exit / quit-> Exit the assistant
 help       -> Show this help
""")

def main():
    tasks = load_tasks()
    print("Welcome to AI Task Assistant (simple). Type 'help' for commands.")
    while True:
        cmd = input(">> ").strip().lower()
        if cmd in ("add",):
            add_task(tasks)
        elif cmd == "list":
            list_tasks(tasks, show_all=False)
        elif cmd == "list all":
            list_tasks(tasks, show_all=True)
        elif cmd == "complete":
            complete_task(tasks)
        elif cmd == "delete":
            delete_task(tasks)
        elif cmd == "suggest":
            suggestions(tasks)
        elif cmd == "score":
            productivity_score(tasks)
        elif cmd in ("exit", "quit"):
            print("Goodbye — keep building!")
            break
        elif cmd in ("help", "?"):
            help_text()
        else:
            print("Unknown command. Type 'help'.")

if __name__ == "__main__":
    main()
