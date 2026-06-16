from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from logger import setup_logger

logger = setup_logger("exceptions")


# ─── Custom Exception Classes ──────────────────────────────────────────────

class StudentNotFoundError(Exception):
    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Student not found: {identifier}")

class DuplicateRollNumberError(Exception):
    def __init__(self, roll_number: str):
        self.roll_number = roll_number
        super().__init__(f"Roll number already exists: {roll_number}")

class SubjectNotFoundError(Exception):
    def __init__(self, subject_name: str, year: int):
        self.subject_name = subject_name
        self.year = year
        super().__init__(f"Subject '{subject_name}' not found in year {year}")

class InvalidYearError(Exception):
    def __init__(self, year: int):
        self.year = year
        super().__init__(f"Invalid year: {year}. Must be 1, 2, or 3")


# ─── Exception Handlers ────────────────────────────────────────────────────

async def student_not_found_handler(request: Request, exc: StudentNotFoundError):
    logger.warning(f"404 Student not found | path={request.url.path} | id={exc.identifier}")
    return JSONResponse(
        status_code=404,
        content={"error": "Student Not Found", "detail": str(exc), "path": str(request.url.path)}
    )

async def duplicate_roll_handler(request: Request, exc: DuplicateRollNumberError):
    logger.warning(f"409 Duplicate roll number | roll={exc.roll_number}")
    return JSONResponse(
        status_code=409,
        content={"error": "Duplicate Roll Number", "detail": str(exc)}
    )

async def subject_not_found_handler(request: Request, exc: SubjectNotFoundError):
    logger.warning(f"404 Subject not found | subject={exc.subject_name} | year={exc.year}")
    return JSONResponse(
        status_code=404,
        content={"error": "Subject Not Found", "detail": str(exc)}
    )

async def invalid_year_handler(request: Request, exc: InvalidYearError):
    logger.warning(f"400 Invalid year | year={exc.year} | path={request.url.path}")
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid Year", "detail": str(exc)}
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code} | path={request.url.path} | detail={exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": f"HTTP {exc.status_code}", "detail": exc.detail, "path": str(request.url.path)}
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    logger.warning(f"422 Validation error | path={request.url.path} | errors={errors}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "detail": "One or more fields are invalid",
            "fields": [
                {
                    "field": " → ".join(str(x) for x in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"]
                }
                for err in errors
            ]
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"500 Unhandled exception | path={request.url.path} | error={type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred. Please try again later."}
    )