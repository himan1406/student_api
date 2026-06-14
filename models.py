from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from bson import ObjectId


class PersonalInfo(BaseModel):
    first_name: str = Field(..., example="Aanya")
    last_name: str = Field(..., example="Sharma")
    email: EmailStr = Field(..., example="aanya.sharma@example.com")
    phone: Optional[str] = Field(None, example="+91-9876543210")
    date_of_birth: Optional[str] = Field(None, example="2004-05-15")
    address: Optional[str] = Field(None, example="42, Lajpat Nagar, New Delhi")
    enrollment_year: int = Field(..., example=2022)
    department: str = Field(..., example="Computer Science")
    roll_number: str = Field(..., example="CS2022001")


class SubjectMarks(BaseModel):
    """Marks for a single subject in a year."""
    subject_name: str = Field(..., example="English")
    marks_obtained: float = Field(..., ge=0, le=100, example=82.0)
    max_marks: float = Field(default=100.0, example=100.0)
    grade: Optional[str] = Field(None, example="A")
    credits: Optional[float] = Field(None, example=4.0)


class YearResult(BaseModel):
    """All subject marks for one academic year."""
    year_number: int = Field(..., ge=1, le=4, example=1)
    academic_year: str = Field(..., example="2022-2023")
    subjects: list[SubjectMarks] = Field(default_factory=list)
    cgpa: Optional[float] = Field(None, ge=0, le=10, example=8.75)
    remarks: Optional[str] = Field(None, example="Pass")


class StudentCreate(BaseModel):
    personal_info: PersonalInfo
    year_1: Optional[YearResult] = None
    year_2: Optional[YearResult] = None
    year_3: Optional[YearResult] = None


class StudentUpdate(BaseModel):
    personal_info: Optional[PersonalInfo] = None
    year_1: Optional[YearResult] = None
    year_2: Optional[YearResult] = None
    year_3: Optional[YearResult] = None


class PersonalInfoUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    enrollment_year: Optional[int] = None
    department: Optional[str] = None
    roll_number: Optional[str] = None


class YearResultUpdate(BaseModel):
    academic_year: Optional[str] = None
    subjects: Optional[list[SubjectMarks]] = None
    cgpa: Optional[float] = None
    remarks: Optional[str] = None