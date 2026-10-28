import pytest
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from messmate.database import Base
from messmate.models import User
from messmate.services.auth import (
    hash_password,
    verify_password,
    authenticate_user,
    record_failed_attempt,
    reset_failed_attempts,
    LOGIN_ATTEMPTS,
    MAX_FAILED_ATTEMPTS
)


@pytest.fixture
def auth_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_password_hashing():
    pwd = "SecureHostelPassword123!"
    h1 = hash_password(pwd)
    h2 = hash_password(pwd)

    # Different salts must produce different hashes
    assert h1 != h2
    assert h1.startswith("pbkdf2:sha256:")

    # Both must verify correctly
    assert verify_password(h1, pwd) is True
    assert verify_password(h2, pwd) is True
    assert verify_password(h1, "WrongPassword") is False


def test_authenticate_success_and_failure(auth_session):
    user = User(
        username="huzaifa",
        display_name="Huzaifa",
        password_hash=hash_password("MyPass123"),
        role="admin",
        is_active=True
    )
    auth_session.add(user)
    auth_session.commit()

    # Success
    auth_user, err = authenticate_user(auth_session, "Huzaifa", "MyPass123")
    assert auth_user is not None
    assert err is None
    assert auth_user.username == "huzaifa"

    # Wrong password
    fail_user, err = authenticate_user(auth_session, "huzaifa", "BadPass")
    assert fail_user is None
    assert "Incorrect password" in err

    # Nonexistent user
    non_user, err = authenticate_user(auth_session, "ghost", "any")
    assert non_user is None
    assert "Invalid username" in err


def test_inactive_user_blocked(auth_session):
    user = User(
        username="inactive_friend",
        display_name="Old Friend",
        password_hash=hash_password("MyPass123"),
        role="member",
        is_active=False
    )
    auth_session.add(user)
    auth_session.commit()

    auth_user, err = authenticate_user(auth_session, "inactive_friend", "MyPass123")
    assert auth_user is None
    assert "deactivated" in err.lower()


def test_rate_limiting():
    uname = "test_lockout_user"
    reset_failed_attempts(uname)

    for i in range(MAX_FAILED_ATTEMPTS - 1):
        attempts, lockout = record_failed_attempt(uname)
        assert lockout == 0
        assert attempts == i + 1

    # 5th attempt triggers lockout
    attempts, lockout = record_failed_attempt(uname)
    assert attempts == MAX_FAILED_ATTEMPTS
    assert lockout > 0

    reset_failed_attempts(uname)

