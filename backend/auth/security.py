# import os
# from datetime import datetime, timedelta
# from typing import Optional

# from passlib.context import CryptContext
# from jose import JWTError, jwt
# from fastapi import Depends, HTTPException, status
# # from fastapi.security import OAuth2PasswordBearer
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION")
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours default

# # oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# bearer_scheme = HTTPBearer()


# def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
#     token = credentials.credentials
#     payload = decode_access_token(token)
#     username = payload.get("sub")
#     role = payload.get("role")
#     user_id = payload.get("user_id")
#     if not username:
#         raise HTTPException(status_code=401, detail="Invalid token payload")
#     return {"username": username, "role": role, "user_id": user_id}


# def hash_password(password: str) -> str:
#     return pwd_context.hash(password)


# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return pwd_context.verify(plain_password, hashed_password)


# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
#     to_encode = data.copy()
#     expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# def decode_access_token(token: str) -> dict:
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except JWTError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token",
#             headers={"WWW-Authenticate": "Bearer"},
#         )


# def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
#     """
#     Dependency — decodes JWT and returns the user payload.
#     Use this in any endpoint that just needs to know WHO is calling.
#     """
#     payload = decode_access_token(token)
#     username = payload.get("sub")
#     role = payload.get("role")
#     user_id = payload.get("user_id")
#     if not username:
#         raise HTTPException(status_code=401, detail="Invalid token payload")
#     return {"username": username, "role": role, "user_id": user_id}


# def require_role(*allowed_roles: str):
#     """
#     Dependency factory — restricts an endpoint to specific roles.

#     Usage:
#         @app.post("/create_pipeline")
#         def create_pipeline(req: ..., user: dict = Depends(require_role("admin", "editor"))):
#             ...
#     """
#     def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
#         if current_user["role"] not in allowed_roles:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail=f"Requires one of roles: {allowed_roles}. Your role: {current_user['role']}",
#             )
#         return current_user
#     return role_checker

import os
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours default

# NOTE: tokenUrl is only used by Swagger UI to know which endpoint issues
# tokens (for its "Authorize" popup) — it does NOT change how the actual
# /auth/login endpoint behaves, and it does NOT require /auth/login to
# accept form-encoded data. /auth/login still takes plain JSON as defined
# in auth/router.py. This scheme's only real job at runtime is extracting
# the "Authorization: Bearer <token>" header from incoming requests.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency — decodes JWT and returns the user payload.
    Use this in any endpoint that just needs to know WHO is calling.
    """
    payload = decode_access_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    user_id = payload.get("user_id")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return {"username": username, "role": role, "user_id": user_id}


def require_role(*allowed_roles: str):
    """
    Dependency factory — restricts an endpoint to specific roles.

    Usage:
        @app.post("/create_pipeline")
        def create_pipeline(req: ..., user: dict = Depends(require_role("admin", "editor"))):
            ...
    """
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {allowed_roles}. Your role: {current_user['role']}",
            )
        return current_user
    return role_checker