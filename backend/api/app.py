"""
FastAPI application factory.
Import `app` from here to run with uvicorn: uvicorn api.app:app --reload --port 8000
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import routes  # registers all route handlers

load_dotenv()

_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="Financial Model Integrity Reviewer", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
