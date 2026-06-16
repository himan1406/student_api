from pydantic import BaseModel, Field, EmailStr


class UserSignup(BaseModel):
    """Payload for creating a new user account."""
    full_name: str = Field(..., example="Himanshu Rawat")
    email: EmailStr = Field(..., example="himanshu@example.com")
    password: str = Field(..., min_length=6, example="strongpassword123")


class UserLogin(BaseModel):
    """Payload for logging in."""
    email: EmailStr = Field(..., example="himanshu@example.com")
    password: str = Field(..., example="strongpassword123")


class TokenResponse(BaseModel):
    """What's returned after successful login/signup/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class RefreshRequest(BaseModel):
    """Payload to exchange a refresh token for a new access token."""
    refresh_token: str


class UserPublic(BaseModel):
    """Safe user data to return — never includes the password."""
    id: str
    full_name: str
    email: EmailStr