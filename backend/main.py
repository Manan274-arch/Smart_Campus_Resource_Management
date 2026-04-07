from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models  # import all models so Base knows about them

# Import routers
from routers import auth, resources, bookings, maintenance, analytics, reports

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Campus Resource Management",
    description="API for managing campus resources, bookings, and maintenance",
    version="1.0.0"
)

# CORS — allow frontend (served from file:// or localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(resources.router)
app.include_router(bookings.router)
app.include_router(maintenance.router)
app.include_router(analytics.router)
app.include_router(reports.router)


@app.get("/")
def root():
    return {"message": "Smart Campus API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}