import logging
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.orm import Session
from messmate.database import init_db, get_db
from messmate.models import User, AuditLog
from messmate.services.auth import hash_password
from messmate.services.meal import record_meal
from messmate.services.deposit import record_deposit, record_shared_expense
from messmate.config import (
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_NAME,
)

logger = logging.getLogger(__name__)

INITIAL_MEMBERS = [
    {"username": DEFAULT_ADMIN_USERNAME, "name": DEFAULT_ADMIN_NAME, "role": "admin", "phone": "03001234567"},
    {"username": "friend2", "name": "Friend 2", "role": "member", "phone": "03002345678"},
    {"username": "friend3", "name": "Friend 3", "role": "member", "phone": "03003456789"},
    {"username": "friend4", "name": "Friend 4", "role": "member", "phone": "03004567890"},
    {"username": "friend5", "name": "Friend 5", "role": "member", "phone": "03005678901"},
    {"username": "friend6", "name": "Friend 6", "role": "member", "phone": "03006789012"},
    {"username": "friend7", "name": "Friend 7", "role": "member", "phone": "03007890123"},
    {"username": "friend8", "name": "Friend 8", "role": "member", "phone": "03008901234"},
]

DEFAULT_MEMBER_PASSWORD = "MessFriend123!"


def seed_initial_eight_members(session: Session) -> bool:
    """
    Ensure the 8 initial hostel friends exist in the database.
    Does not delete or overwrite any existing members.
    """
    existing_count = session.query(User).count()
    if existing_count > 0:
        return False  # Already initialized

    logger.info("Seeding initial 8 hostel members...")
    for idx, item in enumerate(INITIAL_MEMBERS):
        password = DEFAULT_ADMIN_PASSWORD if item["role"] == "admin" else DEFAULT_MEMBER_PASSWORD
        user = User(
            username=item["username"],
            display_name=item["name"],
            role=item["role"],
            phone_number=item["phone"],
            password_hash=hash_password(password),
            is_active=True
        )
        session.add(user)

    session.flush()

    audit = AuditLog(
        action="SEED_MEMBERS",
        target_type="User",
        target_id=None,
        reason="Initial system setup",
        details="Initialized 8 hostel members (1 Admin, 7 Members)."
    )
    session.add(audit)
    session.commit()
    logger.info("Successfully seeded 8 members.")
    return True


def seed_sample_demo_data(session: Session):
    """
    Optional helper to populate realistic sample meals, deposits, and shared expenses
    to demonstrate live functionality immediately upon startup.
    """
    users = session.query(User).order_by(User.id).all()
    if len(users) < 8:
        return

    admin = users[0]
    today = date.today()

    # 1. Advance deposits
    # Huzaifa deposits 5,000, Friend 2 deposits 4,000, Friend 4 deposits 3,500, etc.
    deposits_plan = [
        (users[0].id, Decimal("5000.00"), "EasyPaisa", "EP-998821"),
        (users[1].id, Decimal("4000.00"), "JazzCash", "JC-441100"),
        (users[2].id, Decimal("3000.00"), "Cash", None),
        (users[3].id, Decimal("4500.00"), "Bank Transfer", "PK-HBL-10293"),
        (users[4].id, Decimal("2000.00"), "NayaPay", "NP-77123"),
        (users[5].id, Decimal("3500.00"), "Cash", None),
        (users[6].id, Decimal("4000.00"), "SadaPay", "SP-55442"),
        (users[7].id, Decimal("2500.00"), "JazzCash", "JC-882299"),
    ]
    for uid, amt, method, ref in deposits_plan:
        record_deposit(
            session=session,
            user_id=uid,
            amount=amt,
            payment_method=method,
            reference_no=ref,
            notes="Initial mess pool advance",
            status="confirmed",
            created_by_id=admin.id,
            deposit_date=today - timedelta(days=2)
        )

    # 2. Shared expense (e.g., Cooking Oil, Spices, Flour stock)
    all_user_ids = [u.id for u in users]
    record_shared_expense(
        session=session,
        expense_date=today - timedelta(days=2),
        title="Flour, Cooking Oil & Spices Stock",
        category="Kitchen Supplies",
        total_amount=Decimal("4800.00"),
        attendee_ids=all_user_ids,
        notes="Shared pantry staple stock for the hostel room",
        created_by_id=admin.id
    )

    # 3. Meals
    # Day 1: Dinner (6 present: Huzaifa, Friend 2, Friend 4, Friend 6, Friend 7, Friend 8) - exactly matching user prompt example!
    # Dinner costs Rs. 2,400 -> 6 attendees -> Rs. 400 each
    dinner_attendees = [users[0].id, users[1].id, users[3].id, users[5].id, users[6].id, users[7].id]
    record_meal(
        session=session,
        meal_date=today - timedelta(days=1),
        meal_type="dinner",
        title="Chicken Karahi & Naan",
        category="Chicken",
        total_cost=Decimal("2400.00"),
        present_user_ids=dinner_attendees,
        notes="Dinner with 6 friends present; Friend 3 and Friend 5 absent",
        created_by_id=admin.id
    )

    # Day 2: Breakfast (8 present)
    record_meal(
        session=session,
        meal_date=today,
        meal_type="breakfast",
        title="Anda Paratha & Chai",
        category="Eggs",
        total_cost=Decimal("1200.00"),
        present_user_ids=all_user_ids,
        notes="Morning breakfast for all 8 roommates",
        created_by_id=admin.id
    )

    # Day 2: Lunch (5 present: users 0, 1, 2, 4, 6)
    lunch_attendees = [users[0].id, users[1].id, users[2].id, users[4].id, users[6].id]
    record_meal(
        session=session,
        meal_date=today,
        meal_type="lunch",
        title="Daal Mash & Tandoori Roti",
        category="Daal",
        total_cost=Decimal("1000.00"),
        present_user_ids=lunch_attendees,
        notes="Campus hostel afternoon lunch",
        created_by_id=admin.id
    )

