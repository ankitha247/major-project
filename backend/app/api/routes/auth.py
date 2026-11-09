from fastapi import APIRouter, HTTPException, status, Depends
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.db.repositories.user_repo import UserRepository
from app.core.security import verify_password, create_access_token, hash_password
from app.core.dependencies import get_current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest):
    repo = UserRepository()

    if await repo.email_exists(body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    hashed = hash_password(body.password)

    user = await repo.create(
        email=body.email,
        hashed_password=hashed,
        full_name=body.full_name,
        role=body.role,
    )

    token = create_access_token({"sub": user.id, "role": user.role})

    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    repo = UserRepository()

    user = await repo.get_by_email(body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user.id, "role": user.role})

    return TokenResponse(
        access_token=token,
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
    )


@router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }