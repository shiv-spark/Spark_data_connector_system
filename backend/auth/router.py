import os
import psycopg2
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from auth.security import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_role, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["auth"])

DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "postgres"),
    "database": os.getenv("DB_NAME",     "airflow"),
    "user":     os.getenv("DB_USER",     "airflow"),
    "password": os.getenv("DB_PASSWORD", "airflow"),
    "port":     os.getenv("DB_PORT",     "5432"),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "viewer"   # only an admin can set this to something else — enforced below


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool


@router.post("/login")
def login(req: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, password_hash, role, is_active FROM app_users WHERE username = %s",
        (req.username,)
    )
    row = cur.fetchone()

    if not row:
        cur.close(); conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_id, username, password_hash, role, is_active = row

    if not is_active:
        cur.close(); conn.close()
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if not verify_password(req.password, password_hash):
        cur.close(); conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    cur.execute("UPDATE app_users SET last_login = NOW() WHERE id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()

    token = create_access_token(
        data={"sub": username, "role": role, "user_id": user_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user_id, "username": username, "role": role},
    }


@router.post("/register")
def register(req: RegisterRequest, current_user: dict = Depends(require_role("admin"))):
    """
    Only an admin can create new users. This intentionally requires auth —
    there is no public self-signup endpoint, since this is an internal
    data-pipeline tool, not a public product.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM app_users WHERE username = %s OR email = %s", (req.username, req.email))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="Username or email already exists")

    if req.role not in ("admin", "editor", "viewer"):
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="role must be 'admin', 'editor', or 'viewer'")

    password_hash = hash_password(req.password)
    cur.execute(
        """
        INSERT INTO app_users (username, email, password_hash, role)
        VALUES (%s, %s, %s, %s)
        RETURNING id, username, email, role, is_active
        """,
        (req.username, req.email, password_hash, req.role),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return {
        "status": "SUCCESS",
        "user": {"id": row[0], "username": row[1], "email": row[2], "role": row[3], "is_active": row[4]},
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserOut])
def list_users(current_user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, email, role, is_active FROM app_users ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "username": r[1], "email": r[2], "role": r[3], "is_active": r[4]}
        for r in rows
    ]


@router.patch("/users/{user_id}/role")
def update_user_role(user_id: int, role: str, current_user: dict = Depends(require_role("admin"))):
    if role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE app_users SET role = %s WHERE id = %s RETURNING id", (role, user_id))
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "SUCCESS", "message": f"User {user_id} role updated to '{role}'"}


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, current_user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE app_users SET is_active = FALSE WHERE id = %s RETURNING id", (user_id,))
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "SUCCESS", "message": f"User {user_id} deactivated"}

@router.patch("/users/{user_id}/activate")
def activate_user(user_id: int, current_user: dict = Depends(require_role("admin"))):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE app_users SET is_active = TRUE WHERE id = %s RETURNING id", (user_id,))
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return {"status": "SUCCESS", "message": f"User {user_id} activated"}

# def activate_user(user_id: int, current_user: dict = Depends(require_role("admin"))):
#     conn = get_conn()
#     cur = conn.cursor()
#     cur.execute("UPDATE app_users SET is_active = TRUE WHERE id = %s RETURNING id", (user_id,))
#     updated = cur.fetchone()
#     conn.commit()
#     cur.close()
#     conn.close()

#     if not updated:
#         raise HTTPException(status_code=404, detail="User not found")

#     return {"status": "SUCCESS", "message": f"User {user_id} activated"}