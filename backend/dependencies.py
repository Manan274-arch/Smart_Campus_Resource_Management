from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import SessionLocal
from auth import decode_access_token
import models

# Tells FastAPI: "tokens come from the /users/login endpoint"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def get_db():
    """
    Opens a DB session for a request, then closes it when done.
    Used as a dependency in every router that needs DB access.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Reads the JWT token from the request header,
    decodes it, and returns the matching User from the DB.
    Raises 401 if token is missing, invalid, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = decode_access_token(token)
    if email is None:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception

    return user