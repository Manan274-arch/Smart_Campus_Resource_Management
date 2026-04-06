from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import users, resources, bookings, maintenance, analytics

app = FastAPI(title="Smart Campus API")

# CORS — allows your HTML frontend (opened from a file or local server)
# to make requests to this FastAPI backend without being blocked by the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace * with your actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This creates all tables in campus.db on startup if they don't exist yet
Base.metadata.create_all(bind=engine)

# Register all routers
app.include_router(users.router)
app.include_router(resources.router)
app.include_router(bookings.router)
app.include_router(maintenance.router)
app.include_router(analytics.router)


@app.get("/")
def root():
    return {"message": "Smart Campus API is running"}