from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


jobs = []


class JobIn(BaseModel):
    title: str
    company: str
    url: str = ""
    status: str = "Applied"


@app.get("/")
def home():
    return {"message": "iTrackJobs is running"}


@app.get("/jobs")
def list_jobs():
    return jobs


@app.post("/jobs", status_code=201)
def create_job(job: JobIn):
    
    for existing in jobs:
        if job.url and existing["url"] == job.url:   # blank 1: the new job's url
            return existing                          # blank 2: the job we already saved

    new_job = job.model_dump()
    new_job["id"] = len(jobs) + 1
    new_job["applied_date"] = str(date.today())
    jobs.append(new_job)
    return new_job