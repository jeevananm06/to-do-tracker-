from fastapi import FastAPI, HTTPException, Request, Depends
from models import Task
from typing import List
from notion_client import Client
import os
import json
import logging
from dotenv import load_dotenv

# --- add near the top ---
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import traceback


app = FastAPI()
# CORS is harmless for this public read endpoint and helps generic clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # if you test locally
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.getenv("PUBLIC_WRITE_KEY") 


def require_key(request: Request):
    if not API_KEY or request.headers.get("x-api-key") != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

# Convert any uncaught exception into structured JSON (no opaque 500s)
@app.exception_handler(Exception)
async def _unhandled(_, exc: Exception):
    # Log full traceback to Render logs
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc)[:500]},
        headers={"Content-Type": "application/json; charset=utf-8"}
    )

# Health/echo endpoints for quick diagnostics
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/echo")
def echo(request: Request):
    return {"headers": dict(request.headers), "url": str(request.url), "method": request.method}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.warning(f"Incoming request path: {request.url.path}")
    
    # Process the request and get the response
    original_response = await call_next(request)
    
    # Create a custom response logger using a simple wrapper
    class ResponseLoggerMiddleware:
        def __init__(self, response):
            self.response = response
        
        async def __call__(self, scope, receive, send):
            # Store the original send function
            original_send = send
            response_body = []
            
            # Create a new send function that captures the response body
            async def custom_send(message):
                if message["type"] == "http.response.body":
                    # Capture the body
                    body = message.get("body", b"")
                    if body:
                        response_body.append(body)
                    
                    # If this is the last chunk, log the complete response
                    if not message.get("more_body", False) and response_body:
                        try:
                            full_body = b"".join(response_body)
                            body_str = full_body.decode("utf-8")
                            # Limit the log size to avoid huge logs
                            if len(body_str) > 1000:
                                log_body = body_str[:1000] + "... [truncated]"
                            else:
                                log_body = body_str
                            
                            logger.warning(f"Response for {request.url.path}: Status={original_response.status_code}, Body={log_body}")
                        except Exception as e:
                            logger.warning(f"Failed to log response body: {e}")
                
                # Forward the message to the original send function
                await original_send(message)
            
            # Call the original response with our custom send function
            await self.response(scope, receive, custom_send)
    
    # Wrap the original response with our logger
    return ResponseLoggerMiddleware(original_response)

# Configure logging with line numbers
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()



NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Initialize Notion client only if credentials are provided
notion = None
if NOTION_TOKEN and NOTION_DATABASE_ID:
    try:
        notion = Client(auth=NOTION_TOKEN)
    except Exception as e:
        print(f"Failed to initialize Notion client: {e}")
        notion = None

# File-based task storage functions
TASKS_FILE = "tasks.json"

def load_tasks() -> List[dict]:
    """Load tasks from JSON file, return empty list if file doesn't exist"""
    try:
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def save_tasks(tasks: List[dict]) -> None:
    """Save tasks to JSON file"""
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)


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
    # Handle Task id - can be either number or unique_id type
    task_id = 0
    if "Task id" in props:
        if props["Task id"].get("number") is not None:
            task_id = props["Task id"]["number"]
        elif props["Task id"].get("unique_id"):
            task_id = props["Task id"]["unique_id"]["number"]
    
    # Handle Status - can be either select or status type
    status = None
    if "Status" in props:
        if props["Status"].get("select"):
            status = props["Status"]["select"]["name"]
        elif props["Status"].get("status"):
            status = props["Status"]["status"]["name"]
    
    # Handle Task type - can be select or multi_select
    task_type = None
    if "Task type" in props:
        if props["Task type"].get("select"):
            task_type = props["Task type"]["select"]["name"]
        elif props["Task type"].get("multi_select") and props["Task type"]["multi_select"]:
            task_type = props["Task type"]["multi_select"][0]["name"]
    
    # Handle file attachment safely
    attach_file = None
    if "Attach file" in props and props["Attach file"]["files"]:
        file_obj = props["Attach file"]["files"][0]
        if "file" in file_obj:
            attach_file = file_obj["file"]["url"]
        elif "external" in file_obj:
            attach_file = file_obj["external"]["url"]

    return {
        "task_id": task_id,
        "task_name": props["Task name"]["title"][0]["plain_text"] if props["Task name"]["title"] else "",
        "status": status,
        "assignee": props["Assignee"]["people"][0]["name"] if "Assignee" in props and props["Assignee"]["people"] else None,
        "due_date": props["Due date"]["date"]["start"] if "Due date" in props and props["Due date"]["date"] else None,
        "priority": props["Priority"]["select"]["name"] if "Priority" in props and props["Priority"]["select"] else None,
        "task_type": task_type,
        "description": props["Description"]["rich_text"][0]["plain_text"] if "Description" in props and props["Description"]["rich_text"] else None,
        "attach_file": attach_file,
        "past_due": past_due,
        "updated_at": page.get("last_edited_time"),
        "effort_level": props["Effort level"]["select"]["name"] if "Effort level" in props and props["Effort level"]["select"] else None,
        "summary": props["Summary"]["rich_text"][0]["plain_text"] if "Summary" in props and props["Summary"]["rich_text"] else None,
    }


def get_all_tasks() -> List[dict]:
    try:
        results = notion.databases.query(database_id=NOTION_DATABASE_ID)["results"]
        return [notion_to_task(page) for page in results]
    except Exception as e:
        logger.error(f"Failed to fetch tasks from Notion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tasks from Notion: {str(e)}")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "To-Do Task Tracker API"}


# About page route
@app.get("/about")
def about() -> dict[str, str]:
    return {"message": "This is the about page."}


@app.get("/tasks", response_model=List[Task])
def api_get_all_tasks(request: Request):
    if request.headers.get("x-vercel-internal-bot-category") == "ai_assistant":
        logger.warning(f"Bot access detected: UA={request.headers.get('user-agent')}")
        return get_all_tasks()  # Fallback for bots
    return get_all_tasks()


@app.get("/tasks/active", response_model=List[Task])
def get_active_tasks():
    tasks = get_all_tasks()
    active_tasks = [t for t in tasks if t["status"] != "Done"]
    return active_tasks


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    tasks = get_all_tasks()
    for t in tasks:
        if t["task_id"] == task_id:
            return t
    raise HTTPException(status_code=404, detail="Task not found")


@app.post("/tasks", response_model=Task)
def add_task(task: Task, _: None = Depends(require_key)):
    if not notion or not NOTION_DATABASE_ID:
        raise HTTPException(status_code=503, detail="Notion integration not configured. Please set NOTION_TOKEN and NOTION_DATABASE_ID environment variables.")
    
    # Notion integration (with corrected property types)
    try:
        # Build properties dict with proper validation
        properties = {
            "Task name": {"title": [{"text": {"content": task.task_name}}]},
        }
        
        # Add optional properties only if they have values
        if task.task_id is not None:
            properties["Task id"] = {"number": task.task_id}
            
        if task.status:
            properties["Status"] = {"status": {"name": task.status}}
            
        if task.assignee:
            # Use the user ID from your test output for Jeevanantham Govindaraju
            properties["Assignee"] = {"people": [{"id": "6aaf53e2-c3b4-4fc6-93b3-c5d41e3f65a0"}]}
            
        if task.due_date:
            properties["Due date"] = {"date": {"start": task.due_date}}
            
        if task.priority:
            properties["Priority"] = {"select": {"name": task.priority}}
            
        if task.task_type:
            properties["Task type"] = {"multi_select": [{"name": task.task_type}]}
            
        if task.description:
            properties["Description"] = {"rich_text": [{"text": {"content": task.description}}]}
            
        if task.attach_file:
            properties["Attach file"] = {"files": [{"type": "external", "name": "attachment", "external": {"url": task.attach_file}}]}
            
        if task.past_due is not None:
            properties["Past due"] = {"checkbox": task.past_due}
            
        if task.effort_level:
            properties["Effort level"] = {"select": {"name": task.effort_level}}
            
        if task.summary:
            properties["Summary"] = {"rich_text": [{"text": {"content": task.summary}}]}

        # Debug logging - what we're sending to Notion
        request_payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": properties
        }
        # logger.debug(f"Sending to Notion API: {json.dumps(request_payload, indent=2)}")

        new_page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )
        
        # Debug logging - what we got back from Notion
        # logger.debug(f"Notion API Response: {json.dumps(new_page, indent=2, default=str)}")
        
        # Convert Notion response to our Task format
        result = notion_to_task(new_page)
        # logger.debug(f"Converted task result: {json.dumps(result, indent=2, default=str)}")
        
        return result
    except Exception as e:
        logger.error(f"Exception in add_task: {type(e).__name__}: {str(e)}")
        logger.error(f"Exception details: {repr(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create task in Notion: {str(e)}")


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task: Task, _: None = Depends(require_key)):
    # Notion API does not support direct update by task_id, so we have to search and update
    pages = notion.databases.query(database_id=NOTION_DATABASE_ID)["results"]
    for page in pages:
        props = page["properties"]
        page_task_id = None
        if "Task id" in props:
            if props["Task id"].get("number") is not None:
                page_task_id = props["Task id"]["number"]
            elif props["Task id"].get("unique_id"):
                page_task_id = props["Task id"]["unique_id"]["number"]
        if page_task_id == task_id:
            try:
                update_props = {}
                if task.task_name:
                    update_props["Task name"] = {"title": [{"text": {"content": task.task_name}}]}
                if task.status:
                    update_props["Status"] = {"status": {"name": task.status}}
                if task.assignee:
                    update_props["Assignee"] = {"people": [{"id": "6aaf53e2-c3b4-4fc6-93b3-c5d41e3f65a0"}]}
                if task.due_date:
                    update_props["Due date"] = {"date": {"start": task.due_date}}
                if task.priority:
                    update_props["Priority"] = {"select": {"name": task.priority}}
                if task.task_type:
                    update_props["Task type"] = {"multi_select": [{"name": task.task_type}]}
                if task.description:
                    update_props["Description"] = {"rich_text": [{"text": {"content": task.description}}]}
                if task.attach_file:
                    update_props["Attach file"] = {"files": [{"type": "external", "name": "attachment", "external": {"url": task.attach_file}}]}
                if task.past_due is not None:
                    update_props["Past due"] = {"checkbox": task.past_due}
                if task.effort_level:
                    update_props["Effort level"] = {"select": {"name": task.effort_level}}
                if task.summary:
                    update_props["Summary"] = {"rich_text": [{"text": {"content": task.summary}}]}
                if not update_props:
                    raise HTTPException(status_code=400, detail="No valid fields provided for update.")
                notion.pages.update(
                    page_id=page["id"],
                    properties=update_props
                )
                return get_task(task_id)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to update task in Notion: {str(e)}")
    raise HTTPException(status_code=404, detail="Task not found")


@app.patch("/tasks/{task_id}/status")
def mark_task_status(task_id: int, status: str):
    pages = notion.databases.query(database_id=NOTION_DATABASE_ID)["results"]
    for page in pages:
        props = page["properties"]
        page_task_id = None
        if "Task id" in props:
            if props["Task id"].get("number") is not None:
                page_task_id = props["Task id"]["number"]
            elif props["Task id"].get("unique_id"):
                page_task_id = props["Task id"]["unique_id"]["number"]
        if page_task_id == task_id:
            try:
                notion.pages.update(
                    page_id=page["id"],
                    properties={
                        "Status": {"status": {"name": status}}
                    }
                )
                return get_task(task_id)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to update status in Notion: {str(e)}")
    raise HTTPException(status_code=404, detail="Task not found")


@app.patch("/tasks/{task_id}/comment")
def add_comment(task_id: int, comment: str, _: None = Depends(require_key)):
    pages = notion.databases.query(database_id=NOTION_DATABASE_ID)["results"]
    for page in pages:
        props = page["properties"]
        page_task_id = None
        if "Task id" in props:
            if props["Task id"].get("number") is not None:
                page_task_id = props["Task id"]["number"]
            elif props["Task id"].get("unique_id"):
                page_task_id = props["Task id"]["unique_id"]["number"]
        if page_task_id == task_id:
            try:
                # Notion does not support comments as a property; use page discussion/comments API if needed
                # Here, we add a comment to the page using the discussion/comments endpoint
                notion.comments.create(
                    parent={"page_id": page["id"]},
                    rich_text=[{"text": {"content": comment}}]
                )
                return get_task(task_id)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add comment in Notion: {str(e)}")
    raise HTTPException(status_code=404, detail="Task not found")


@app.patch("/tasks/{task_id}/link")
def add_link(task_id: int, link: str, _: None = Depends(require_key)):
    pages = notion.databases.query(database_id=NOTION_DATABASE_ID)["results"]
    for page in pages:
        props = page["properties"]
        page_task_id = None
        if "Task id" in props:
            if props["Task id"].get("number") is not None:
                page_task_id = props["Task id"]["number"]
            elif props["Task id"].get("unique_id"):
                page_task_id = props["Task id"]["unique_id"]["number"]
        if page_task_id == task_id:
            try:
                # Notion does not support links as a property directly; you might want to append to a rich_text or URL property
                # Here, we append the link to the description if it exists
                description = props["Description"]["rich_text"][0]["plain_text"] if "Description" in props and props["Description"]["rich_text"] else ""
                new_description = description + f"\nLink: {link}"
                notion.pages.update(
                    page_id=page["id"],
                    properties={
                        "Description": {"rich_text": [{"text": {"content": new_description}}]}
                    }
                )
                return get_task(task_id)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to add link in Notion: {str(e)}")
    raise HTTPException(status_code=404, detail="Task not found")
