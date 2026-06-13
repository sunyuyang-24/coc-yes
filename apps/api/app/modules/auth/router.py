from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.modules.auth.service import (
    authenticate,
    create_token,
    create_user,
    decode_token,
    get_user_by_id,
)

router = APIRouter()


@router.post("/auth/register", response_model=AuthResponse)
def register(body: RegisterRequest):
    try:
        user = create_user(body.username, body.password, body.display_name)
    except Exception:
        return JSONResponse({"error": "Username already taken"}, status_code=409)
    token = create_token(user["id"], user["username"])
    return {"user": UserResponse(**user).model_dump(), "token": token}


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest):
    user = authenticate(body.username, body.password)
    if user is None:
        return JSONResponse({"error": "Invalid username or password"}, status_code=401)
    token = create_token(user["id"], user["username"])
    return {"user": UserResponse(**user).model_dump(), "token": token}


@router.get("/auth/me", response_model=UserResponse)
def me(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    user = get_user_by_id(user_id)
    if user is None:
        return JSONResponse({"error": "User not found"}, status_code=404)
    return UserResponse(**user).model_dump()
