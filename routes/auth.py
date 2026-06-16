from fastapi import APIRouter, Request, HTTPException, status, Depends
from auth_models import UserSignup, UserLogin, TokenResponse, RefreshRequest, UserPublic
from auth_utils import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, get_current_user
)
from config import settings
from logger import setup_logger

router = APIRouter()
logger = setup_logger("auth_routes")


def get_users_collection(request: Request):
    return request.app.mongodb["users"]


# ─── SIGNUP ────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: Request, user: UserSignup):
    """
    Create a new user account.
    Returns an access token (5 min) and refresh token (30 days) immediately —
    no separate login needed after signing up.
    """
    users = get_users_collection(request)

    existing = await users.find_one({"email": user.email})
    if existing:
        logger.warning(f"Signup blocked — email already exists: {user.email}")
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    hashed = hash_password(user.password)
    doc = {"full_name": user.full_name, "email": user.email, "password": hashed}
    result = await users.insert_one(doc)
    user_id = str(result.inserted_id)

    logger.info(f"New user signed up | id={user_id} | email={user.email}")

    access_token = create_access_token(user_id, user.email)
    refresh_token = create_refresh_token(user_id, user.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )


# ─── LOGIN ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(request: Request, credentials: UserLogin):
    """
    Authenticate with email + password.
    Returns a new access token (5 min) and refresh token (30 days).
    """
    users = get_users_collection(request)
    user = await users.find_one({"email": credentials.email})

    if not user or not verify_password(credentials.password, user["password"]):
        logger.warning(f"Failed login attempt | email={credentials.email}")
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    user_id = str(user["_id"])
    logger.info(f"User logged in | id={user_id} | email={credentials.email}")

    access_token = create_access_token(user_id, credentials.email)
    refresh_token = create_refresh_token(user_id, credentials.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )


# ─── REFRESH ───────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(payload: RefreshRequest):
    """
    Exchange a valid (unexpired) refresh token for a brand new access token.
    Call this when your access token expires (every 5 minutes) —
    no need to log in again until the refresh token itself expires (30 days).
    """
    decoded = decode_token(payload.refresh_token)

    if decoded.get("type") != "refresh":
        logger.warning("Refresh attempt with non-refresh token")
        raise HTTPException(status_code=401, detail="This is not a valid refresh token")

    user_id = decoded["sub"]
    email = decoded["email"]
    logger.info(f"Access token refreshed | user_id={user_id}")

    new_access_token = create_access_token(user_id, email)
    # Issue a new refresh token too (sliding session window)
    new_refresh_token = create_refresh_token(user_id, email)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )


# ─── ME (protected route example) ──────────────────────────────────────────

@router.get("/me", response_model=UserPublic)
async def get_me(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Returns the currently logged-in user's profile.
    Requires a valid access token in the Authorization header.
    """
    users = get_users_collection(request)
    from bson import ObjectId
    user = await users.find_one({"_id": ObjectId(current_user["user_id"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserPublic(id=str(user["_id"]), full_name=user["full_name"], email=user["email"])