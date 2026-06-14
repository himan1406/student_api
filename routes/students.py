from fastapi import APIRouter, HTTPException, status, Request, Query
from bson import ObjectId
from typing import Optional
from models import (
    StudentCreate, StudentUpdate,
    PersonalInfoUpdate, YearResultUpdate, SubjectMarks
)

router = APIRouter()


def get_collection(request: Request):
    return request.app.mongodb["students"]


def fix_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def valid_oid(student_id: str):
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID format")
    return ObjectId(student_id)


# ─── CREATE ────────────────────────────────────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_student(request: Request, student: StudentCreate):
    """Create a new student with personal info and optional yearwise subject marks."""
    collection = get_collection(request)
    existing = await collection.find_one(
        {"personal_info.roll_number": student.personal_info.roll_number}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Student with roll number '{student.personal_info.roll_number}' already exists"
        )
    doc = student.model_dump(exclude_none=True)
    result = await collection.insert_one(doc)
    return {
        "message": "Student created successfully",
        "id": str(result.inserted_id),
        "roll_number": student.personal_info.roll_number
    }


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
    students = []
    async for doc in collection.find(query).skip(skip).limit(limit):
        students.append(fix_id(doc))
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
    results = []
    async for doc in collection.find(query).limit(50):
        results.append(fix_id(doc))
    return results


# ─── READ ONE ──────────────────────────────────────────────────────────────

@router.get("/roll/{roll_number}")
async def get_student_by_roll(request: Request, roll_number: str):
    """Get a student by roll number."""
    collection = get_collection(request)
    doc = await collection.find_one({"personal_info.roll_number": roll_number})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Student '{roll_number}' not found")
    return fix_id(doc)


@router.get("/{student_id}")
async def get_student(request: Request, student_id: str):
    """Get a student by MongoDB _id."""
    collection = get_collection(request)
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")
    return fix_id(doc)


# ─── GET specific year / subject ───────────────────────────────────────────

@router.get("/{student_id}/year/{year_number}")
async def get_year_result(request: Request, student_id: str, year_number: int):
    """Get the full result for a specific year of a student."""
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")
    year_data = doc.get(f"year_{year_number}")
    if not year_data:
        raise HTTPException(status_code=404, detail=f"Year {year_number} data not found for this student")
    return year_data


@router.get("/{student_id}/year/{year_number}/subjects")
async def get_year_subjects(request: Request, student_id: str, year_number: int):
    """Get only the subjects list for a specific year."""
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")
    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    return {"year": year_number, "subjects": subjects}


@router.get("/{student_id}/year/{year_number}/subjects/{subject_name}")
async def get_single_subject(request: Request, student_id: str, year_number: int, subject_name: str):
    """Get marks for a single subject by name (case-insensitive) in a given year."""
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)
    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")
    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    match = next((s for s in subjects if s["subject_name"].lower() == subject_name.lower()), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_name}' not found in year {year_number}")
    return match


# ─── PUT (full replace) ────────────────────────────────────────────────────

@router.put("/{student_id}")
async def update_student(request: Request, student_id: str, student: StudentUpdate):
    collection = get_collection(request)
    oid = valid_oid(student_id)
    update_data = student.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    result = await collection.update_one({"_id": oid}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student updated", "modified_count": result.modified_count}


# ─── PATCH personal_info ───────────────────────────────────────────────────

@router.patch("/{student_id}/personal-info")
async def patch_personal_info(request: Request, student_id: str, info: PersonalInfoUpdate):
    """Patch individual fields inside personal_info — only send what you want to change."""
    collection = get_collection(request)
    oid = valid_oid(student_id)
    patch = {f"personal_info.{k}": v for k, v in info.model_dump(exclude_none=True).items()}
    if not patch:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await collection.update_one({"_id": oid}, {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Personal info updated", "modified_count": result.modified_count}


# ─── PATCH year (cgpa / remarks / academic_year only) ─────────────────────

@router.patch("/{student_id}/year/{year_number}")
async def patch_year_meta(
    request: Request, student_id: str, year_number: int, year_data: YearResultUpdate
):
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)
    # exclude subjects here — subjects have dedicated endpoints
    allowed = {k: v for k, v in year_data.model_dump(exclude_none=True).items() if k != "subjects"}
    if not allowed:
        raise HTTPException(status_code=400, detail="No fields to update. Use /subjects endpoints to update subject marks.")
    patch = {f"year_{year_number}.{k}": v for k, v in allowed.items()}
    result = await collection.update_one({"_id": oid}, {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": f"Year {year_number} meta updated", "modified_count": result.modified_count}


# ─── PATCH subjects (replace entire subjects list for a year) ──────────────

@router.patch("/{student_id}/year/{year_number}/subjects")
async def replace_all_subjects(
    request: Request, student_id: str, year_number: int, subjects: list[SubjectMarks]
):
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)
    subjects_data = [s.model_dump() for s in subjects]
    result = await collection.update_one(
        {"_id": oid},
        {"$set": {f"year_{year_number}.subjects": subjects_data}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": f"All subjects for year {year_number} replaced", "subject_count": len(subjects_data)}


# ─── PATCH single subject by name ─────────────────────────────────────────

@router.patch("/{student_id}/year/{year_number}/subjects/{subject_name}")
async def patch_single_subject(
    request: Request, student_id: str, year_number: int, subject_name: str, subject: SubjectMarks
):
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)

    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")

    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    idx = next((i for i, s in enumerate(subjects) if s["subject_name"].lower() == subject_name.lower()), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_name}' not found in year {year_number}")

    result = await collection.update_one(
        {"_id": oid},
        {"$set": {f"year_{year_number}.subjects.{idx}": subject.model_dump()}}
    )
    return {"message": f"Subject '{subject_name}' updated in year {year_number}", "modified_count": result.modified_count}


# ─── POST add a new subject to a year ─────────────────────────────────────

@router.post("/{student_id}/year/{year_number}/subjects")
async def add_subject(
    request: Request, student_id: str, year_number: int, subject: SubjectMarks
):
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)

    doc = await collection.find_one({"_id": oid}, {f"year_{year_number}.subjects": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Student not found")

    subjects = doc.get(f"year_{year_number}", {}).get("subjects", [])
    exists = any(s["subject_name"].lower() == subject.subject_name.lower() for s in subjects)
    if exists:
        raise HTTPException(status_code=409, detail=f"Subject '{subject.subject_name}' already exists in year {year_number}. Use PATCH to update it.")

    result = await collection.update_one(
        {"_id": oid},
        {"$push": {f"year_{year_number}.subjects": subject.model_dump()}}
    )
    return {"message": f"Subject '{subject.subject_name}' added to year {year_number}"}


# ─── DELETE a subject from a year ─────────────────────────────────────────

@router.delete("/{student_id}/year/{year_number}/subjects/{subject_name}")
async def delete_subject(request: Request, student_id: str, year_number: int, subject_name: str):
    if year_number not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="year_number must be 1, 2, or 3")
    collection = get_collection(request)
    oid = valid_oid(student_id)

    result = await collection.update_one(
        {"_id": oid},
        {"$pull": {f"year_{year_number}.subjects": {"subject_name": {"$regex": f"^{subject_name}$", "$options": "i"}}}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail=f"Subject '{subject_name}' not found in year {year_number}")
    return {"message": f"Subject '{subject_name}' deleted from year {year_number}"}


# ─── DELETE student ────────────────────────────────────────────────────────

@router.delete("/{student_id}")
async def delete_student(request: Request, student_id: str):
    collection = get_collection(request)
    oid = valid_oid(student_id)
    result = await collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}