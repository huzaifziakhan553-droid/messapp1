import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from messmate.database import Base
from messmate.models import User, Meal, Deposit, SharedExpense, AuditLog
from messmate.services.meal import record_meal, reverse_meal, update_meal_attendance
from messmate.services.deposit import record_deposit, reverse_deposit, record_shared_expense
from messmate.services.finance import calculate_member_balance


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create 8 members
    users = []
    for i in range(1, 9):
        role = "admin" if i == 1 else "member"
        name = "Huzaifa" if i == 1 else f"Friend {i}"
        u = User(
            username=f"user{i}",
            display_name=name,
            password_hash="dummy_hash",
            role=role,
            is_active=True
        )
        users.append(u)
    session.add_all(users)
    session.commit()

    yield session
    session.close()


def test_complete_mess_lifecycle(test_db):
    users = test_db.query(User).order_by(User.id).all()
    admin = users[0]
    friend2 = users[1]
    friend3 = users[2]

    # 1. Deposit
    dep, err = record_deposit(
        session=test_db,
        user_id=admin.id,
        amount=Decimal("3000.00"),
        payment_method="Cash",
        created_by_id=admin.id
    )
    assert err is None
    assert dep.amount == Decimal("3000.00")

    bal_admin = calculate_member_balance(test_db, admin.id)
    assert bal_admin["net_balance"] == Decimal("3000.00")

    # 2. Record Meal: Rs. 1200 split among first 4 users (Rs. 300 each)
    present_ids = [u.id for u in users[:4]]
    meal, err = record_meal(
        session=test_db,
        meal_date=date.today(),
        meal_type="dinner",
        title="Biryani",
        total_cost=Decimal("1200.00"),
        present_user_ids=present_ids,
        created_by_id=admin.id
    )
    assert err is None
    assert meal.id is not None
    assert meal.attendee_count == 4

    # Huzaifa was present -> 3000 - 300 = 2700
    bal_admin = calculate_member_balance(test_db, admin.id)
    assert bal_admin["total_meal_charges"] == Decimal("3000.00") * 0 + Decimal("300.00")
    assert bal_admin["net_balance"] == Decimal("2700.00")

    # Friend 2 was present -> 0 - 300 = -300
    bal_f2 = calculate_member_balance(test_db, friend2.id)
    assert bal_f2["net_balance"] == Decimal("-300.00")

    # Friend 5 was absent -> 0
    bal_f5 = calculate_member_balance(test_db, users[4].id)
    assert bal_f5["net_balance"] == Decimal("0.00")

    # 3. Update Attendance: Friend 5 was actually present too (now 5 attendees)
    new_present_ids = [u.id for u in users[:5]]
    ok, msg = update_meal_attendance(
        session=test_db,
        meal_id=meal.id,
        new_present_user_ids=new_present_ids,
        reason="Friend 5 came back late from library and ate",
        performed_by_id=admin.id
    )
    assert ok is True
    # 1200 / 5 = 240.00 each
    bal_admin_after = calculate_member_balance(test_db, admin.id)
    assert bal_admin_after["net_balance"] == Decimal("2760.00")  # 3000 - 240

    bal_f5_after = calculate_member_balance(test_db, users[4].id)
    assert bal_f5_after["net_balance"] == Decimal("-240.00")

    # 4. Reverse Meal with reason
    ok, msg = reverse_meal(
        session=test_db,
        meal_id=meal.id,
        reason="Meal cooked by university event sponsor, zero cost to mess",
        performed_by_id=admin.id
    )
    assert ok is True

    # After reversal, meal charges wiped, admin balance restored to 3000.00
    bal_admin_rev = calculate_member_balance(test_db, admin.id)
    assert bal_admin_rev["total_meal_charges"] == Decimal("0.00")
    assert bal_admin_rev["net_balance"] == Decimal("3000.00")

    # Audit logs must have captured CREATE_MEAL, UPDATE_ATTENDANCE, REVERSE_MEAL
    actions = [a.action for a in test_db.query(AuditLog).all()]
    assert "RECORD_DEPOSIT" in actions
    assert "CREATE_MEAL" in actions
    assert "UPDATE_ATTENDANCE" in actions
    assert "REVERSE_MEAL" in actions

