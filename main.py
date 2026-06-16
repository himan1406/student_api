from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from config import settings
from routes import students, auth
from logger import setup_logger
from exceptions import (
    StudentNotFoundError, DuplicateRollNumberError,
    SubjectNotFoundError, InvalidYearError,
    student_not_found_handler, duplicate_roll_handler,
    subject_not_found_handler, invalid_year_handler,
    http_exception_handler, validation_exception_handler,
    global_exception_handler
)

logger = setup_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Student Management API...")
    try:
        app.mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
        app.mongodb = app.mongodb_client[settings.DB_NAME]
        # Ping to verify connection
        await app.mongodb_client.admin.command("ping")
        # Ensure email is unique at the database level too
        await app.mongodb["users"].create_index("email", unique=True)
        logger.info(f"✅ Connected to MongoDB Atlas — database: '{settings.DB_NAME}'")
    except Exception as e:
        logger.critical(f"❌ Failed to connect to MongoDB Atlas: {e}")
        raise
    yield
    logger.info("Shutting down — closing MongoDB connection...")
    app.mongodb_client.close()
    logger.info("MongoDB connection closed.")


app = FastAPI(
    title="Student Management API",
    description="REST API for managing student records, secured with JWT authentication.",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Middleware ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Exception Handlers ────────────────────────────────────────────────────

app.add_exception_handler(StudentNotFoundError, student_not_found_handler)
app.add_exception_handler(DuplicateRollNumberError, duplicate_roll_handler)
app.add_exception_handler(SubjectNotFoundError, subject_not_found_handler)
app.add_exception_handler(InvalidYearError, invalid_year_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# ─── Routes ────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(students.router, prefix="/students", tags=["Students"])


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    logger.info("Root endpoint hit")
    return {"message": "Student Management API is running 🎓", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health_check():
    logger.info("Health check requested")
    return {"status": "healthy", "database": settings.DB_NAME}