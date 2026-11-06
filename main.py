from datetime import date

from fastapi import Depends, FastAPI, Response
from pydantic import BaseModel
from sqlalchemy import Date, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# ---------- Database setup ----------
engine = create_engine("sqlite:///itrackjobs.db")
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
    applied_date: Mapped[date] = mapped_column(Date, default=date.today)


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- API ----------
app = FastAPI()


class JobIn(BaseModel):
    title: str
    company: str
    url: str = ""
    status: str = "Applied"


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    url: str
    status: str
    applied_date: date

    model_config = {"from_attributes": True}


@app.get("/")
def home():
    return {"message": "iTrackJobs is running"}


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(Job).order_by(Job.id.desc())).all()


@app.post("/jobs", response_model=JobOut, status_code=201)
def create_job(job: JobIn, response: Response, db: Session = Depends(get_db)):
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