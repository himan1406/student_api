from fastapi import APIRouter, Request, Query, Depends
from bson import ObjectId
from typing import Optional
from models import (
    StudentCreate, StudentUpdate,
    PersonalInfoUpdate, YearResultUpdate, SubjectMarks
)
from logger import setup_logger
from exceptions import (
    StudentNotFoundError, DuplicateRollNumberError,
    SubjectNotFoundError, InvalidYearError
)
from auth_utils import get_current_user

# Every route in this router now requires a valid access token.
# FastAPI runs get_current_user() before the route body — 401 if token missing/invalid/expired.
router = APIRouter(dependencies=[Depends(get_current_user)])
logger = setup_logger("students")


def get_collection(request: Request):
    return request.app.mongodb["students"]


def fix_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def valid_oid(student_id: str) -> ObjectId:
    if not ObjectId.is_valid(student_id):
        raise ValueError(f"Invalid ObjectId format: {student_id}")
    return ObjectId(student_id)


def check_year(year_number: int):
    if year_number not in [1, 2, 3]:
        raise InvalidYearError(year_number)


# ─── CREATE ────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_student(request: Request, student: StudentCreate):
    """Create a new student with personal info and optional yearwise subject marks."""
    collection = get_collection(request)
    roll = student.personal_info.roll_number
    logger.info(f"POST /students — creating student with roll={roll}")

    existing = await collection.find_one({"personal_info.roll_number": roll})
    if existing:
        raise DuplicateRollNumberError(roll)

    doc = student.model_dump(exclude_none=True)
    result = await collection.insert_one(doc)
    logger.info(f"Student created | id={result.inserted_id} | roll={roll}")
    return {"message": "Student created successfully", "id": str(result.inserted_id), "roll_number": roll}


# ─── READ ALL ──────────────────────────────────────────────────────────────

@router.get("/")
async def get_all_students(
    request: Request,
    department: Optional[str] = Query(None),
    enrollment_year: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List all students with optional filters."""
    collection = get_collection(request)
    query = {}
    if department:
        query["personal_info.department"] = department
    if enrollment_year:
        query["personal_info.enrollment_year"] = enrollment_year

    logger.info(f"GET /students — filters: department={department}, year={enrollment_year}, skip={skip}, limit={limit}")
    students = []
    async for doc in collection.find(query).skip(skip).limit(limit):
        students.append(fix_id(doc))
    logger.info(f"Returned {len(students)} students")
    return students


# ─── SEARCH ────────────────────────────────────────────────────────────────

@router.get("/search/query")
async def search_students(
    request: Request,
    name: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    min_cgpa: Optional[float] = Query(None, ge=0, le=10),
    year: Optional[int] = Query(None, ge=1, le=3),
):
    """Search students by name, department, or minimum CGPA in a given year."""
    collection = get_collection(request)
    query = {}
    if name:
        query["$or"] = [
            {"personal_info.first_name": {"$regex": name, "$options": "i"}},
            {"personal_info.last_name":  {"$regex": name, "$options": "i"}},
        ]
    if department:
        query["personal_info.department"] = {"$regex": department, "$options": "i"}
    if min_cgpa is not None and year:
        query[f"year_{year}.cgpa"] = {"$gte": min_cgpa}
    elif year:
        query[f"year_{year}"] = {"$exists": True}

    logger.info(f"SEARCH — name={name}, dept={department}, min_cgpa={min_cgpa}, year={year}")
    results = []
    async for doc in collection.find(query).limit(50):
        results.append(fix_id(doc))
    logger.info(f"Search returned {len(results)} results")
    return results


# ─── READ ONE ──────────────────────────────────────────────────────────────

@router.get("/roll/{roll_number}")
async def get_student_by_roll(request: Request, roll_number: str):
    """Get a student by roll number."""
    collection = get_collection(request)
    logger.info(f"GET /students/roll/{roll_number}")
    doc = await collection.find_one({"personal_info.roll_number": roll_number})
    if not doc:
        raise StudentNotFoundError(roll_number)
    return fix_id(doc)


@router.get("/{student_id}")
async def get_student(request: Request, student_id: str):
    """Get a student by MongoDB _id."""
    collection = get_collection(request)
    logger.info(f"GET /students/{student_id}")
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid})
    if not doc:
        raise StudentNotFoundError(student_id)
    return fix_id(doc)


# ─── GET year / subjects ───────────────────────────────────────────────────

@router.get("/{student_id}/year/{year_number}")
async def get_year_result(request: Request, student_id: str, year_number: int):
    """Get the full result for a specific year."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"GET year result | student={student_id} | year={year_number}")
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}": 1})
    if not doc:
        raise StudentNotFoundError(student_id)
    year_data = doc.get(f"year_{year_number}")
    if not year_data:
        raise StudentNotFoundError(f"Year {year_number} data for student {student_id}")
    return year_data


@router.get("/{student_id}/year/{year_number}/subjects")
async def get_year_subjects(request: Request, student_id: str, year_number: int):
    """Get only the subjects list for a specific year."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"GET subjects | student={student_id} | year={year_number}")
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise StudentNotFoundError(student_id)
    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    return {"year": year_number, "subjects": subjects}


@router.get("/{student_id}/year/{year_number}/subjects/{subject_name}")
async def get_single_subject(request: Request, student_id: str, year_number: int, subject_name: str):
    """Get marks for a single subject by name in a given year."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"GET subject | student={student_id} | year={year_number} | subject={subject_name}")
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise StudentNotFoundError(student_id)
    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    match = next((s for s in subjects if s["subject_name"].lower() == subject_name.lower()), None)
    if not match:
        raise SubjectNotFoundError(subject_name, year_number)
    return match


# ─── PUT ───────────────────────────────────────────────────────────────────

@router.put("/{student_id}")
async def update_student(request: Request, student_id: str, student: StudentUpdate):
    """Replace any top-level fields on a student document."""
    collection = get_collection(request)
    logger.info(f"PUT /students/{student_id}")
    oid = valid_oid(student_id)
    update_data = student.model_dump(exclude_none=True)
    if not update_data:
        raise ValueError("No update data provided")
    result = await collection.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise StudentNotFoundError(student_id)
    logger.info(f"Student updated | id={student_id} | modified={result.modified_count}")
    return {"message": "Student updated", "modified_count": result.modified_count}


# ─── PATCH personal_info ───────────────────────────────────────────────────

@router.patch("/{student_id}/personal-info")
async def patch_personal_info(request: Request, student_id: str, info: PersonalInfoUpdate):
    """Patch individual fields inside personal_info."""
    collection = get_collection(request)
    logger.info(f"PATCH personal-info | student={student_id}")
    oid = valid_oid(student_id)
    patch = {f"personal_info.{k}": v for k, v in info.model_dump(exclude_none=True).items()}
    if not patch:
        raise ValueError("No fields to update")
    result = await collection.update_one({"_id": oid}, {"$set": patch})
    if result.matched_count == 0:
        raise StudentNotFoundError(student_id)
    logger.info(f"Personal info updated | id={student_id} | fields={list(patch.keys())}")
    return {"message": "Personal info updated", "modified_count": result.modified_count}


# ─── PATCH year meta ───────────────────────────────────────────────────────

@router.patch("/{student_id}/year/{year_number}")
async def patch_year_meta(request: Request, student_id: str, year_number: int, year_data: YearResultUpdate):
    """Patch year-level fields: academic_year, cgpa, remarks."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"PATCH year meta | student={student_id} | year={year_number}")
    oid = valid_oid(student_id)
    allowed = {k: v for k, v in year_data.model_dump(exclude_none=True).items() if k != "subjects"}
    if not allowed:
        raise ValueError("No valid fields to update. Use /subjects endpoints to update subject marks.")
    patch = {f"year_{year_number}.{k}": v for k, v in allowed.items()}
    result = await collection.update_one({"_id": oid}, {"$set": patch})
    if result.matched_count == 0:
        raise StudentNotFoundError(student_id)
    logger.info(f"Year {year_number} meta updated | id={student_id}")
    return {"message": f"Year {year_number} updated", "modified_count": result.modified_count}


# ─── PATCH all subjects ────────────────────────────────────────────────────

@router.patch("/{student_id}/year/{year_number}/subjects")
async def replace_all_subjects(request: Request, student_id: str, year_number: int, subjects: list[SubjectMarks]):
    """Replace the entire subjects list for a year."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"PATCH all subjects | student={student_id} | year={year_number} | count={len(subjects)}")
    oid = valid_oid(student_id)
    subjects_data = [s.model_dump() for s in subjects]
    result = await collection.update_one({"_id": oid}, {"$set": {f"year_{year_number}.subjects": subjects_data}})
    if result.matched_count == 0:
        raise StudentNotFoundError(student_id)
    logger.info(f"All subjects replaced | id={student_id} | year={year_number} | count={len(subjects_data)}")
    return {"message": f"All subjects for year {year_number} replaced", "subject_count": len(subjects_data)}


# ─── PATCH single subject ──────────────────────────────────────────────────

@router.patch("/{student_id}/year/{year_number}/subjects/{subject_name}")
async def patch_single_subject(request: Request, student_id: str, year_number: int, subject_name: str, subject: SubjectMarks):
    """Update marks for one specific subject by name."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"PATCH subject | student={student_id} | year={year_number} | subject={subject_name}")
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise StudentNotFoundError(student_id)
    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    idx = next((i for i, s in enumerate(subjects) if s["subject_name"].lower() == subject_name.lower()), None)
    if idx is None:
        raise SubjectNotFoundError(subject_name, year_number)
    result = await collection.update_one({"_id": oid}, {"$set": {f"year_{year_number}.subjects.{idx}": subject.model_dump()}})
    logger.info(f"Subject updated | id={student_id} | year={year_number} | subject={subject_name}")
    return {"message": f"Subject '{subject_name}' updated in year {year_number}", "modified_count": result.modified_count}


# ─── POST add subject ──────────────────────────────────────────────────────

@router.post("/{student_id}/year/{year_number}/subjects")
async def add_subject(request: Request, student_id: str, year_number: int, subject: SubjectMarks):
    """Add a new subject to a year's subjects list."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"POST add subject | student={student_id} | year={year_number} | subject={subject.subject_name}")
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise StudentNotFoundError(student_id)
    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    if any(s["subject_name"].lower() == subject.subject_name.lower() for s in subjects):
        raise DuplicateRollNumberError(f"Subject '{subject.subject_name}' already exists in year {year_number}")
    await collection.update_one({"_id": oid}, {"$push": {f"year_{year_number}.subjects": subject.model_dump()}})
    logger.info(f"Subject added | id={student_id} | year={year_number} | subject={subject.subject_name}")
    return {"message": f"Subject '{subject.subject_name}' added to year {year_number}"}


# ─── DELETE subject ────────────────────────────────────────────────────────

@router.delete("/{student_id}/year/{year_number}/subjects/{subject_name}")
async def delete_subject(request: Request, student_id: str, year_number: int, subject_name: str):
    """Remove a subject by name from a year."""
    check_year(year_number)
    collection = get_collection(request)
    logger.info(f"DELETE subject | student={student_id} | year={year_number} | subject={subject_name}")
    oid = valid_oid(student_id)
    result = await collection.update_one(
        {"_id": oid},
        {"$pull": {f"year_{year_number}.subjects": {"subject_name": {"$regex": f"^{subject_name}$", "$options": "i"}}}}
    )
    if result.matched_count == 0:
        raise StudentNotFoundError(student_id)
    if result.modified_count == 0:
        raise SubjectNotFoundError(subject_name, year_number)
    logger.info(f"Subject deleted | id={student_id} | year={year_number} | subject={subject_name}")
    return {"message": f"Subject '{subject_name}' deleted from year {year_number}"}


# ─── DELETE student ────────────────────────────────────────────────────────

@router.delete("/{student_id}")
async def delete_student(request: Request, student_id: str):
    """Permanently delete a student record."""
    collection = get_collection(request)
    logger.info(f"DELETE /students/{student_id}")
    oid = valid_oid(student_id)
    result = await collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise StudentNotFoundError(student_id)
    logger.info(f"Student deleted | id={student_id}")
    return {"message": "Student deleted successfully"}