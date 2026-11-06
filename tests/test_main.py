import os

os.environ["ITJ_API_KEY"] = "test-key"
os.environ["ITJ_DATABASE_URL"] = "sqlite:///test_itrackjobs.db"

from fastapi.testclient import TestClient

from main import Base, app, engine

client = TestClient(app)
HEADERS = {"X-API-Key": "test-key"}
JOB = {
    "title": "Help Desk Technician",
    "company": "Acme",
    "url": "https://www.linkedin.com/jobs/view/123",
}


def setup_function():
    """Runs before EVERY test: start with an empty database."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_home_is_public():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "iTrackJobs is running"}


def test_jobs_require_api_key():
    assert client.get("/jobs").status_code == 401
    assert client.get("/jobs", headers={"X-API-Key": "wrong"}).status_code == 401


def test_create_job():
    response = client.post("/jobs", json=JOB, headers=HEADERS)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["title"] == "Help Desk Technician"
    assert body["status"] == "Applied"


def test_duplicate_url_is_not_saved_twice():
    client.post("/jobs", json=JOB, headers=HEADERS)
    second = client.post("/jobs", json=JOB, headers=HEADERS)
    assert second.status_code == 200
    assert len(client.get("/jobs", headers=HEADERS).json()) == 1


def test_missing_company_is_rejected():
    response = client.post("/jobs", json={"title": "Test"}, headers=HEADERS)
    assert response.status_code == 422


def test_update_status():
    job_id = client.post("/jobs", json=JOB, headers=HEADERS).json()["id"]
    response = client.patch(f"/jobs/{job_id}", json={"status": "Interview"}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "Interview"


def test_invalid_status_is_rejected():
    job_id = client.post("/jobs", json=JOB, headers=HEADERS).json()["id"]
    response = client.patch(f"/jobs/{job_id}", json={"status": "Hired!!"}, headers=HEADERS)
    assert response.status_code == 422


def test_update_missing_job_returns_404():
    response = client.patch("/jobs/999", json={"status": "Offer"}, headers=HEADERS)
    assert response.status_code == 404


def test_delete_job():
    job_id = client.post("/jobs", json=JOB, headers=HEADERS).json()["id"]
    assert client.delete(f"/jobs/{job_id}", headers=HEADERS).status_code == 204
    assert client.delete(f"/jobs/{job_id}", headers=HEADERS).status_code == 404