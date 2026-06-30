"""Animus-Mind Celery worker bootstrap.

Placeholder: will configure outbox processor and workflow runner.
"""
from celery import Celery

app = Celery("animus_mind")
app.conf.update(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@app.task
def process_outbox() -> None:
    """Process pending outbox entries."""
    pass


@app.task
def run_workflow_checkpoint(workflow_id: str) -> None:
    """Resume or advance a workflow from its last checkpoint."""
    pass
