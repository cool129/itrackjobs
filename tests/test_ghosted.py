import os

# Set test settings BEFORE importing the app
os.environ["ITJ_API_KEY"] = "test-key"
os.environ["ITJ_DATABASE_URL"] = "sqlite:///test_itrackjobs.db"

from datetime import timedelta

from fastapi.testclient import TestClient

from main import Base, app, engine, today

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}
JOB = {
    "title": "Help Desk Technician",
    "company": "Acme",
    "url": "https://www.linkedin.com/jobs/view/123",
}


def setup_function():
    """Start every test with an empty database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def days_ago(n):
    return str(today() - timedelta(days=n))


def create_job_applied(days, status="Applied"):
    """Create a job and pretend it was applied for `days` days ago."""
    job_id = client.post("/jobs", json=JOB, headers=HEADERS).json()["id"]
    client.patch(
        f"/jobs/{job_id}",
        json={"status": status, "applied_date": days_ago(days)},
        headers=HEADERS,
    )


def test_old_applied_job_becomes_ghosted():
    create_job_applied(30)
    jobs = client.get("/jobs", headers=HEADERS).json()
    assert jobs[0]["status"] == "Ghosted"


def test_recent_applied_job_stays_applied():
    create_job_applied(5)
    jobs = client.get("/jobs", headers=HEADERS).json()
    assert jobs[0]["status"] == "Applied"


def test_old_interview_is_not_ghosted():
    create_job_applied(30, status="Interview")
    jobs = client.get("/jobs", headers=HEADERS).json()
    assert jobs[0]["status"] == "Interview"