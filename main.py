import os
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Date, Integer, String, Text, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# ---------- Security ----------
load_dotenv()
API_KEY = os.getenv("ITJ_API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: Annotated[str | None, Depends(api_key_header)]):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server has no ITJ_API_KEY set")
    if key is None or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


AUTH = [Depends(require_api_key)]


# ---------- Dates ----------
def today() -> date:
    """Today's date in UTC, so the server and the cloud always agree."""
    return datetime.now(UTC).date()


# ---------- Database setup ----------
DATABASE_URL = os.getenv("ITJ_DATABASE_URL", "sqlite:///itrackjobs.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(30), default="Applied")
    applied_date: Mapped[date] = mapped_column(Date, default=today)
    notes: Mapped[str] = mapped_column(Text, default="")

Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DB = Annotated[Session, Depends(get_db)]


# ---------- Ghosted rule ----------
GHOST_AFTER_DAYS = int(os.getenv("ITJ_GHOST_DAYS", "21"))


def mark_ghosted(db: Session) -> None:
    """Mark jobs still 'Applied' after GHOST_AFTER_DAYS days as 'Ghosted'."""
    cutoff = today() - timedelta(days=GHOST_AFTER_DAYS)
    db.execute(
        update(Job)
        .where(Job.status == "Applied", Job.applied_date <= cutoff)
        .values(status="Ghosted")
    )
    db.commit()


# ---------- API ----------
app = FastAPI(title="iTrackJobs API")

STATUSES = ["Saved", "Applied", "Interview", "Offer", "Rejected", "Ghosted"]
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class JobIn(BaseModel):
    model_config = {"str_strip_whitespace": True}

    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    url: str = ""
    status: str = "Applied"
    notes: str = ""


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    url: str
    status: str
    applied_date: date
    notes: str

    model_config = {"from_attributes": True}


class JobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    status: str | None = None
    applied_date: date | None = None
    notes: str | None = None
   


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/jobs", response_model=list[JobOut], dependencies=AUTH)
def list_jobs(db: DB):
    mark_ghosted(db)
    return db.scalars(select(Job).order_by(Job.id.desc())).all()


@app.post("/jobs", response_model=JobOut, status_code=201, dependencies=AUTH)
def create_job(job: JobIn, response: Response, db: DB):
    if job.url:
        existing = db.scalars(select(Job).where(Job.url == job.url)).first()
        if existing:
            response.status_code = 200
            return existing

    new_job = Job(**job.model_dump())
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job


@app.patch("/jobs/{job_id}", response_model=JobOut, dependencies=AUTH)
def update_job(job_id: int, changes: JobUpdate, db: DB):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    data = changes.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of {STATUSES}")

    for field, value in data.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    return job


@app.delete("/jobs/{job_id}", status_code=204, dependencies=AUTH)
def delete_job(job_id: int, db: DB):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()