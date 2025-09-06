from typing import Optional, List
from pydantic import BaseModel


class MsgPayload(BaseModel):
    msg_id: Optional[int]
    msg_name: str


class Task(BaseModel):
    task_id: int
    task_name: str
    status: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string
    priority: Optional[str] = None
    task_type: Optional[str] = None
    description: Optional[str] = None
    attach_file: Optional[str] = None  # URL or file name
    past_due: Optional[bool] = None
    updated_at: Optional[str] = None  # ISO date string
    effort_level: Optional[str] = None
    summary: Optional[str] = None
