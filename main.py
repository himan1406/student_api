from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from config import settings
from routes import students

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to MongoDB Atlas
    app.mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
    app.mongodb = app.mongodb_client[settings.DB_NAME]
    print(f"✅ Connected to MongoDB Atlas — database: '{settings.DB_NAME}'")
    yield
    # Shutdown: close connection
    app.mongodb_client.close()
    print("🔌 MongoDB connection closed")

app = FastAPI(
    title="Student Management API",
    description="REST API for managing student records with personal info and yearwise results",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(students.router, prefix="/students", tags=["Students"])

@app.get("/", tags=["Health"])
async def root():
    return {"message": "Student Management API is running 🎓", "docs": "/docs"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "database": settings.DB_NAME}