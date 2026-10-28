import hashlib
import hmac
import secrets
import time
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from messmate.models import User

# In-memory tracking of failed login attempts for brute-force mitigation
# Structure: { username: {"attempts": int, "locked_until": float} }
LOGIN_ATTEMPTS = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 300  # 5 minutes
ITERATIONS = 600_000  # OWASP standard for PBKDF2-HMAC-SHA256


def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a unique random salt.
    Format stored: 'pbkdf2:sha256:iterations$salt$hash'
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS
    )
    return f"pbkdf2:sha256:{ITERATIONS}${salt}${key.hex()}"


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify a plain password against the stored PBKDF2 hash."""
    if not stored_hash or not password:
        return False
    try:
        header, salt, expected_hash = stored_hash.split("$")
        algo_info, iter_str = header.split(":")[:2], header.split(":")[-1]
        iterations = int(iter_str)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations
        )
        return hmac.compare_digest(key.hex(), expected_hash)
    except Exception:
        return False


def is_rate_limited(username: str) -> Tuple[bool, int]:
    """Check if the user is currently locked out from repeated failed logins."""
    record = LOGIN_ATTEMPTS.get(username.lower())
    if not record:
        return False, 0
    now = time.time()
    if record.get("locked_until", 0) > now:
        remaining = int(record["locked_until"] - now)
        return True, remaining
    # If lockout expired, reset
    if record.get("locked_until", 0) <= now and record.get("attempts", 0) >= MAX_FAILED_ATTEMPTS:
        LOGIN_ATTEMPTS.pop(username.lower(), None)
    return False, 0


def record_failed_attempt(username: str) -> Tuple[int, int]:
    """Record a failed login attempt and apply lockout if max reached."""
    key = username.lower()
    now = time.time()
    record = LOGIN_ATTEMPTS.setdefault(key, {"attempts": 0, "locked_until": 0})
    record["attempts"] += 1
    if record["attempts"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = now + LOCKOUT_DURATION_SECONDS
        return record["attempts"], LOCKOUT_DURATION_SECONDS
    return record["attempts"], 0


def reset_failed_attempts(username: str):
    """Clear failed attempts upon successful login."""
    LOGIN_ATTEMPTS.pop(username.lower(), None)


def authenticate_user(session: Session, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
    """
    Authenticate a user by username and password.
    Returns (User, None) on success, or (None, error_message) on failure.
    """
    clean_username = username.strip().lower()
    locked, remaining = is_rate_limited(clean_username)
    if locked:
        return None, f"Too many failed login attempts. Please wait {remaining} seconds before trying again."

    user = session.query(User).filter(User.username == clean_username).first()
    if not user:
        record_failed_attempt(clean_username)
        return None, "Invalid username or password."

    if not user.is_active:
        return None, "This account has been deactivated. Please contact the mess administrator."

    if not verify_password(user.password_hash, password):
        attempts, lockout = record_failed_attempt(clean_username)
        if lockout > 0:
            return None, f"Incorrect password. Too many failed attempts. Locked out for {lockout // 60} minutes."
        remaining_tries = MAX_FAILED_ATTEMPTS - attempts
        return None, f"Incorrect password. {remaining_tries} attempt(s) remaining."

    reset_failed_attempts(clean_username)
    return user, None


def change_password(session: Session, user: User, current_password: str, new_password: str) -> Tuple[bool, str]:
    """Change an existing user's password after verifying the old password."""
    if not verify_password(user.password_hash, current_password):
        return False, "Current password does not match."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters long."
    user.password_hash = hash_password(new_password)
    session.add(user)
    session.commit()
    return True, "Password successfully updated."


def admin_reset_password(session: Session, target_user: User, new_password: str) -> Tuple[bool, str]:
    """Allows an administrator to reset a user's password without knowing old password."""
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters long."
    target_user.password_hash = hash_password(new_password)
    session.add(target_user)
    session.commit()
    return True, f"Password for {target_user.display_name} has been reset."

