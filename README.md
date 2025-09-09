# To-Do Tracker API with Notion Integration

A FastAPI-based to-do tracker that integrates seamlessly with Notion, allowing you to manage tasks using both a modern API and your Notion workspace.

## Features
- **Task CRUD**: Create, read, update, and manage tasks via REST API.
- **Notion Integration**: Syncs tasks with a Notion database.
- **Swagger UI**: Interactive API docs at `/docs`.
- **File-based fallback**: Local `tasks.json` storage if Notion is not configured.
- **Rich Task Model**: Supports assignee, due date, priority, attachments, comments, and more.

## Requirements
- Python 3.8+
- [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), [notion-client](https://github.com/ramnes/notion-sdk-py), [httpx](https://www.python-httpx.org/), [python-dotenv](https://github.com/theskumar/python-dotenv)

Install dependencies:
```sh
pip install -r requirements.txt
```

## Environment Variables
Set the following in a `.env` file (see `.env.example`):
```
NOTION_TOKEN=your_notion_integration_token_here
NOTION_DATABASE_ID=your_notion_database_id_here
```

## Running the Application
```sh
uvicorn main:app --reload
```
- Access API at: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

## API Endpoints
| Method | Endpoint                | Description                  |
|--------|-------------------------|------------------------------|
| GET    | `/`                     | API welcome message          |
| GET    | `/about`                | About page                   |
| GET    | `/tasks`                | List all tasks               |
| POST   | `/tasks`                | Create a new task            |
| GET    | `/tasks/active`         | List all active tasks        |
| GET    | `/tasks/{task_id}`      | Get details of a task        |
| PUT    | `/tasks/{task_id}`      | Update a task                |
| PATCH  | `/tasks/{task_id}/status` | Update task status         |
| PATCH  | `/tasks/{task_id}/comment`| Add a comment to a task    |
| PATCH  | `/tasks/{task_id}/link`   | Add a link to task         |

## Task Model
Example of a Task object:
```json
{
  "task_id": 1,
  "task_name": "Sample Task",
  "status": "In Progress",
  "assignee": "Jeevanantham Govindaraju",
  "due_date": "2025-09-10",
  "priority": "High",
  "task_type": "Bug",
  "description": "Fix the login issue.",
  "attach_file": "https://example.com/file.pdf",
  "past_due": false,
  "updated_at": "2025-09-09T16:48:04+05:30",
  "effort_level": "Medium",
  "summary": "Login bug needs urgent fix."
}
```

## Testing
To run tests:
```sh
pytest
```

## Notes
- Ensure your Notion integration has access to the specified database.
- If Notion credentials are not set, tasks are stored in `tasks.json` locally.
- For more details, see code comments in `main.py` and `models.py`.
