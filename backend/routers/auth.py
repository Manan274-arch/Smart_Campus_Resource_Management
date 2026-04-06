from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from auth import hash_password, verify_password, create_access_token
import models, schemas

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check duplicate email
    existing = db.query(models.User).filter(models.User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate role exists
    role = db.query(models.Role).filter(models.Role.role_id == user_data.role_id).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = models.User(
        name=user_data.name,
        email=user_data.email.lower(),
        password_hash=hash_password(user_data.password),
        role_id=user_data.role_id
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.user_id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email.lower()).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user.user_id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=schemas.UserOut)
def get_me(db: Session = Depends(get_db), current_user: models.User = Depends()):
    from auth import get_current_user
    return current_user