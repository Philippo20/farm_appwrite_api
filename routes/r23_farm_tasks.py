from appwrite.query import Query
from fastapi import Query as ApiQuery
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from appwrite.id import ID
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status as http_status
from appwrite.exception import AppwriteException
from routes.messaging import current_member
from main import db_collection_id6

from audit_utils import write_audit
from db import db
from main import db_collection_id23, db_id
from routes.r25_notifications import create_notification

collection23_router = APIRouter(tags=["Farm Tasks"])


class TaskPriority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TaskStatus(str, Enum):
    NOT_STARTED = "Not Started"
    STARTED = "Started"
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_code() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"FT-{stamp}"


def _payload(
    *,
    farm_id: str,
    farm_name: str,
    title: str,
    description: str,
    manager_comment: str,
    caretaker_comment: str,
    assigned_to_id: str,
    assigned_to_name: str,
    assigned_by_id: str,
    assigned_by_name: str,
    priority: TaskPriority,
    status: TaskStatus,
    due_date: Optional[str] = None,
    created_at: Optional[str] = None,
):
    data = {
        "farm_id": farm_id,
        "farm_name": farm_name,
        "title": title,
        "description": description,
        "manager_comment": manager_comment,
        "caretaker_comment": caretaker_comment,
        "assigned_to_id": assigned_to_id,
        "assigned_to_name": assigned_to_name,
        "assigned_by_id": assigned_by_id,
        "assigned_by_name": assigned_by_name,
        "priority": priority.value,
        "status": status.value,
        "created_at": created_at or _now(),
        "updated_at": _now(),
    }
    if due_date:
        data["due_date"] = due_date
    return data


@collection23_router.post("/farm-tasks/info")
def create_farm_task(
    farm_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    title: Annotated[str, Form()],
    assigned_to_id: Annotated[str, Form()],
    assigned_to_name: Annotated[str, Form()],
    assigned_by_id: Annotated[str, Form()],
    assigned_by_name: Annotated[str, Form()],
    priority: Annotated[TaskPriority, Form()],
    description: Annotated[str, Form()] = "",
    manager_comment: Annotated[str, Form()] = "",
    caretaker_comment: Annotated[str, Form()] = "",
    due_date: Annotated[str, Form()] = "",
):
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")

    task_id = _task_code()
    data = _payload(
        farm_id=farm_id,
        farm_name=farm_name,
        title=title,
        description=description,
        manager_comment=manager_comment,
        caretaker_comment=caretaker_comment,
        assigned_to_id=assigned_to_id,
        assigned_to_name=assigned_to_name,
        assigned_by_id=assigned_by_id,
        assigned_by_name=assigned_by_name,
        priority=priority,
        status=TaskStatus.PENDING,
        due_date=due_date or None,
    )
    data["task_id"] = task_id

    try:
        created = db.create_document(
            database_id=db_id,
            collection_id=db_collection_id23,
            document_id=ID.unique(),
            data=data,
        )
        write_audit(
            action_type="Create",
            collection_name="Farm Tasks",
            performed_by_id=assigned_by_name or assigned_by_id,
            performed_by_role="farm_manager",
            action_details=f"Assigned task {task_id} to {assigned_to_name}",
            new_data=data,
        )
        if assigned_to_id and assigned_to_id != assigned_by_id:
            try:
                create_notification(
                    recipient_id=assigned_to_id,
                    recipient_name=assigned_to_name,
                    title="New task assigned",
                    message=(
                        f"{assigned_by_name or 'A farm manager'} assigned you "
                        f"'{title}' on {farm_name}."
                    ),
                    notification_type="task",
                    priority="high" if priority == TaskPriority.HIGH else "normal",
                    related_task_id=task_id,
                )
            except Exception:
                # A notification failure must not roll back task creation.
                pass
        return {"message": "Farm task assigned successfully", "task": created}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection23_router.get("/farm-tasks")
def get_farm_tasks(assigned_to_id: Optional[str] = None, offset: int = ApiQuery(0, ge=0), limit: int = ApiQuery(25, ge=1, le=500)):
    try:
        result = db.list_documents(
            database_id=db_id,
            collection_id=db_collection_id23,
            queries=[Query.limit(limit), Query.offset(offset), Query.order_desc("$updatedAt"), *([Query.equal("assigned_to_id", [assigned_to_id])] if assigned_to_id else [])],
        )
        return {
            "count": len(result["documents"]),
            "users": result["documents"],
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection23_router.get("/farm-tasks/{task_doc_id}")
def get_farm_task(task_doc_id: str):
    try:
        return db.get_document(
            database_id=db_id,
            collection_id=db_collection_id23,
            document_id=task_doc_id,
        )
    except Exception as error:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )


@collection23_router.put("/farm-tasks/{task_doc_id}")
def update_farm_task(
    task_doc_id: str,
    farm_id: Annotated[str, Form()],
    farm_name: Annotated[str, Form()],
    title: Annotated[str, Form()],
    assigned_to_id: Annotated[str, Form()],
    assigned_to_name: Annotated[str, Form()],
    assigned_by_id: Annotated[str, Form()],
    assigned_by_name: Annotated[str, Form()],
    priority: Annotated[TaskPriority, Form()],
    status: Annotated[TaskStatus, Form()],
    description: Annotated[str, Form()] = "",
    manager_comment: Annotated[str, Form()] = "",
    caretaker_comment: Annotated[Optional[str], Form()] = None,
    due_date: Annotated[str, Form()] = "",
):
    try:
        previous = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id23,
            document_id=task_doc_id,
        )
        data = _payload(
            farm_id=farm_id,
            farm_name=farm_name,
            title=title,
            description=description,
            manager_comment=manager_comment,
            caretaker_comment=(
                caretaker_comment
                if caretaker_comment is not None
                else previous.get("caretaker_comment", "")
            ),
            assigned_to_id=assigned_to_id,
            assigned_to_name=assigned_to_name,
            assigned_by_id=assigned_by_id,
            assigned_by_name=assigned_by_name,
            priority=priority,
            status=status,
            due_date=due_date or previous.get("due_date"),
            created_at=previous.get("created_at"),
        )
        updated = db.update_document(
            database_id=db_id,
            collection_id=db_collection_id23,
            document_id=task_doc_id,
            data=data,
            permissions=[],
        )
        write_audit(
            action_type="Update",
            collection_name="Farm Tasks",
            performed_by_id=assigned_by_name or assigned_by_id,
            performed_by_role="farm_manager",
            action_details=f"Updated task {previous.get('task_id', task_doc_id)}",
            previous_data=previous,
            new_data=data,
        )
        previous_assignee_id = previous.get("assigned_to_id", "")
        previous_caretaker_comment = previous.get("caretaker_comment", "") or ""
        current_caretaker_comment = data.get("caretaker_comment", "") or ""
        status_changed = previous.get("status") != status.value
        caretaker_comment_changed = (
            previous_caretaker_comment != current_caretaker_comment
        )
        assignment_changed = previous_assignee_id != assigned_to_id

        if assignment_changed and assigned_to_id and assigned_to_id != assigned_by_id:
            try:
                create_notification(
                    recipient_id=assigned_to_id,
                    recipient_name=assigned_to_name,
                    title="Task reassigned to you",
                    message=(
                        f"{assigned_by_name or 'A farm manager'} assigned you "
                        f"'{title}' on {farm_name}."
                    ),
                    notification_type="task",
                    priority="normal",
                    related_task_id=previous.get("task_id", task_doc_id),
                )
            except Exception:
                pass

        if (status_changed or caretaker_comment_changed) and assigned_by_id:
            try:
                update_note = (
                    f"Task status changed to {status.value}."
                    if status_changed
                    else "Task reply received."
                )
                if caretaker_comment_changed:
                    update_note += f" Reply: {current_caretaker_comment}"
                create_notification(
                    recipient_id=assigned_by_id,
                    recipient_name=assigned_by_name,
                    title="Task update received",
                    message=(
                        f"{assigned_to_name} updated task '{title}' on {farm_name}. "
                        f"{update_note}"
                    ),
                    notification_type="task",
                    priority="normal",
                    related_task_id=previous.get("task_id", task_doc_id),
                )
            except Exception:
                pass

        if not assignment_changed and not status_changed and not caretaker_comment_changed:
            if assigned_to_id and assigned_to_id != assigned_by_id:
                try:
                    create_notification(
                        recipient_id=assigned_to_id,
                        recipient_name=assigned_to_name,
                        title="Task details updated",
                        message=f"Task '{title}' on {farm_name} has been updated.",
                        notification_type="task",
                        priority="normal",
                        related_task_id=previous.get("task_id", task_doc_id),
                    )
                except Exception:
                    pass
        return {"message": "Farm task updated successfully", "task": updated}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@collection23_router.delete("/farm-tasks/{task_doc_id}")
def delete_farm_task(task_doc_id: str, request: Request, actor=Depends(current_member)):
    if actor.get("role") not in {"admin", "superadmin"}:
        raise HTTPException(403, "Only administrators can delete farm tasks.")
    try:
        previous = db.get_document(
            database_id=db_id,
            collection_id=db_collection_id23,
            document_id=task_doc_id,
        )
        # Persist the actor and task identity before destructive work. If audit
        # storage is unavailable the task remains intact.
        audit_id = write_audit(
            action_type="Delete",
            collection_name="Farm Tasks",
            performed_by_id=actor["$id"],
            performed_by_role=actor["role"],
            action_details=f"Delete task {previous.get('task_id', task_doc_id)}: {previous.get('title', '')}",
            ip_address=request.client.host if request.client else "-",
            previous_data={"id": task_doc_id, "task": previous.get("task_id"),
                           "title": previous.get("title"), "farm": previous.get("farm_name"),
                           "assignee": previous.get("assigned_to_id"), "status": previous.get("status")},
            status="Pending", strict=True,
        )
        if not audit_id:
            raise HTTPException(503, "Unable to record the deletion. The task was not deleted.")
        try:
            db.delete_document(database_id=db_id, collection_id=db_collection_id23,
                               document_id=task_doc_id)
        except Exception:
            db.update_document(database_id=db_id, collection_id=db_collection_id6,
                               document_id=audit_id, data={"status": "Failed"})
            raise
        audit_pending = False
        try:
            db.update_document(database_id=db_id, collection_id=db_collection_id6,
                               document_id=audit_id, data={"status": "Success"})
        except Exception:
            # The durable Pending entry still identifies the deletion attempt.
            audit_pending = True
        assigned_to_id = previous.get("assigned_to_id", "")
        assigned_by_id = previous.get("assigned_by_id", "")
        if assigned_to_id and assigned_to_id != assigned_by_id:
            try:
                create_notification(
                    recipient_id=assigned_to_id,
                    recipient_name=previous.get("assigned_to_name", ""),
                    title="Task removed",
                    message=(
                        f"Task '{previous.get('title', previous.get('task_id', task_doc_id))}' "
                        f"on {previous.get('farm_name', 'your farm')} was removed."
                    ),
                    notification_type="task",
                    priority="normal",
                    related_task_id=previous.get("task_id", task_doc_id),
                )
            except Exception:
                pass
        return {"message": "Task deleted." if not audit_pending else
                "Task deleted. Its audit entry is pending confirmation.", "audit_pending": audit_pending}
    except HTTPException:
        raise
    except AppwriteException as error:
        if error.code == 404:
            raise HTTPException(404, "Task not found.") from error
        raise HTTPException(503, "Could not delete the task. Try again.") from error
    except Exception as error:
        raise HTTPException(503, "Could not delete the task. Try again.") from error
