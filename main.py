from fastapi import FastAPI, HTTPException
from models import Task
from typing import List
from notion_client import Client
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
notion = Client(auth=NOTION_TOKEN)


def notion_to_task(page) -> dict:
    props = page["properties"]
    # For a checkbox property:
    # past_due = props["Past due"]["checkbox"] if "Past due" in props else None

    # For a formula property that returns a boolean:
    past_due = None
    if "Past due" in props:
        if props["Past due"]["type"] == "formula":
            # If your formula returns a boolean:
            past_due = props["Past due"]["formula"].get("boolean")
            # If your formula returns a string like "Yes"/"No" or "⏰ Past Due", convert to bool:
            # past_due = props["Past due"]["formula"].get("string") == "⏰ Past Due"
        elif "checkbox" in props["Past due"]:
            past_due = props["Past due"]["checkbox"]
    return {
        "task_id": props["Task id"].get("number") if props["Task id"].get("number") is not None else 0,
        "task_name": props["Task name"]["title"][0]["plain_text"] if props["Task name"]["title"] else "",
        "status": props["Status"].get("select", {}).get("name") if props["Status"].get("select") else None,
        "assignee": props["Assignee"]["people"][0]["name"] if props["Assignee"]["people"] else None,
        "due_date": props["Due date"]["date"]["start"] if props["Due date"]["date"] else None,
        "priority": props["Priority"]["select"]["name"] if props["Priority"]["select"] else None,
        "task_type": props["Task type"]["select"]["name"] if props["Task type"].get("select") else None,
        "description": props["Description"]["rich_text"][0]["plain_text"] if props["Description"]["rich_text"] else None,
        "attach_file": props["Attach file"]["files"][0]["file"]["url"] if props["Attach file"]["files"] else None,
        "past_due": past_due,
        "updated_at": page.get("last_edited_time"),
        "effort_level": props["Effort level"]["select"]["name"] if props["Effort level"]["select"] else None,
        "summary": props["Summary"]["rich_text"][0]["plain_text"] if props["Summary"]["rich_text"] else None,
    }


def get_all_tasks() -> List[dict]:
    results = notion.databases.query(database_id=NOTION_DATABASE_ID)["results"]
    return [notion_to_task(page) for page in results]


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "To-Do Task Tracker API"}


# About page route
@app.get("/about")
def about() -> dict[str, str]:
    return {"message": "This is the about page."}


@app.get("/tasks", response_model=List[Task])
def api_get_all_tasks():
    return get_all_tasks()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            return t
    raise HTTPException(status_code=404, detail="Task not found")


@app.get("/tasks/active", response_model=List[Task])
def get_active_tasks():
    tasks = load_tasks()
    return [t for t in tasks if t["status"] == "active"]


@app.post("/tasks", response_model=Task)
def add_task(task: Task):
    new_page = notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Task id": {"number": task.task_id if task.task_id is not None else 0},
            "Task name": {"title": [{"text": {"content": task.task_name}}]},
            "Status": {"select": {"name": task.status}} if task.status else {},
            "Assignee": {"people": [{"id": "6aaf53e2-c3b4-4fc6-93b3-c5d41e3f65a0"}]},  # <-- Set Jeeva as assignee
            "Due date": {"date": {"start": task.due_date}} if task.due_date else {},
            "Priority": {"select": {"name": task.priority}} if task.priority else {},
            "Task type": {"select": {"name": task.task_type}} if task.task_type else {"select": None},
            "Description": {"rich_text": [{"text": {"content": task.description}}]} if task.description else {},
            "Attach file": {"files": [{"name": "file", "external": {"url": task.attach_file}}]} if task.attach_file else {},
            "Past due": {"checkbox": task.past_due} if task.past_due is not None else {"checkbox": False},
            "Effort level": {"select": {"name": task.effort_level}} if task.effort_level else {},
            "Summary": {"rich_text": [{"text": {"content": task.summary}}]} if task.summary else {},
        }
    )
    return notion_to_task(new_page)


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task: Task):
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            tasks[i] = task.dict()
            save_tasks(tasks)
            return task
    raise HTTPException(status_code=404, detail="Task not found")


@app.patch("/tasks/{task_id}/status")
def mark_task_status(task_id: int, status: str):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = status
            save_tasks(tasks)
            return t
    raise HTTPException(status_code=404, detail="Task not found")


@app.patch("/tasks/{task_id}/comment")
def add_comment(task_id: int, comment: str):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["comments"].append(comment)
            save_tasks(tasks)
            return t
    raise HTTPException(status_code=404, detail="Task not found")


@app.patch("/tasks/{task_id}/link")
def add_link(task_id: int, link: str):
    tasks = load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            t["links"].append(link)
            save_tasks(tasks)
            return t
    raise HTTPException(status_code=404, detail="Task not found")
