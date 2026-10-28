import pytest
from decimal import Decimal
from messmate.services.finance import (
    to_decimal,
    split_expense_exact,
    calculate_member_balance,
    get_mess_overall_summary
)
from messmate.models import User, Meal, MealAttendance, Deposit, SharedExpense, SharedExpenseAttendee
from messmate.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date


@pytest.fixture
def db_session():
    """In-memory SQLite database for isolated unit and financial testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_to_decimal():
    assert to_decimal(100) == Decimal("100.00")
    assert to_decimal("2450.50") == Decimal("2450.50")
    assert to_decimal(None) == Decimal("0.00")
    assert to_decimal("invalid") == Decimal("0.00")
    assert to_decimal(Decimal("12.345")) == Decimal("12.35")


def test_split_expense_exact_even():
    # Rs. 2400 split among 6 members = 400.00 each
    shares = split_expense_exact(Decimal("2400.00"), 6)
    assert len(shares) == 6
    assert all(s == Decimal("400.00") for s in shares)
    assert sum(shares) == Decimal("2400.00")


def test_split_expense_exact_with_remainder():
    # Rs. 100 split among 3 members: 33.34, 33.33, 33.33
    shares = split_expense_exact(Decimal("100.00"), 3)
    assert len(shares) == 3
    assert shares[0] == Decimal("33.34")
    assert shares[1] == Decimal("33.33")
    assert shares[2] == Decimal("33.33")
    assert sum(shares) == Decimal("100.00")


def test_split_expense_single_and_zero():
    assert split_expense_exact(Decimal("500.00"), 0) == []
    shares = split_expense_exact(Decimal("750.00"), 1)
    assert shares == [Decimal("750.00")]


def test_balance_calculation_with_absentee(db_session):
    """
    Test prompt example:
    Dinner Rs. 2400.
    6 Present: each charged Rs. 400.
    2 Absent: charged Rs. 0.
    """
    user1 = User(username="huzaifa", display_name="Huzaifa", password_hash="dummy", role="admin")
    user2 = User(username="friend2", display_name="Friend 2", password_hash="dummy", role="member")
    user3 = User(username="friend3", display_name="Friend 3", password_hash="dummy", role="member")
    db_session.add_all([user1, user2, user3])
    db_session.commit()

    # User 1 deposits Rs. 1,000, User 3 deposits Rs. 500
    dep1 = Deposit(date=date.today(), user_id=user1.id, amount=Decimal("1000.00"), status="confirmed")
    dep3 = Deposit(date=date.today(), user_id=user3.id, amount=Decimal("500.00"), status="confirmed")
    db_session.add_all([dep1, dep3])
    db_session.commit()

    # Meal: Rs. 800, present: user1 and user2 (2 attendees, Rs. 400 each); user3 absent
    meal = Meal(date=date.today(), meal_type="dinner", total_cost=Decimal("800.00"))
    db_session.add(meal)
    db_session.flush()

    att1 = MealAttendance(meal_id=meal.id, user_id=user1.id, is_present=True, charged_amount=Decimal("400.00"))
    att2 = MealAttendance(meal_id=meal.id, user_id=user2.id, is_present=True, charged_amount=Decimal("400.00"))
    att3 = MealAttendance(meal_id=meal.id, user_id=user3.id, is_present=False, charged_amount=Decimal("0.00"))
    db_session.add_all([att1, att2, att3])
    db_session.commit()

    bal1 = calculate_member_balance(db_session, user1.id)
    assert bal1["total_deposits"] == Decimal("1000.00")
    assert bal1["total_meal_charges"] == Decimal("400.00")
    assert bal1["net_balance"] == Decimal("600.00")  # Credit
    assert bal1["status"] == "CREDIT"

    bal2 = calculate_member_balance(db_session, user2.id)
    assert bal2["total_deposits"] == Decimal("0.00")
    assert bal2["total_meal_charges"] == Decimal("400.00")
    assert bal2["net_balance"] == Decimal("-400.00")  # Dues
    assert bal2["status"] == "DUES"

    bal3 = calculate_member_balance(db_session, user3.id)
    assert bal3["total_deposits"] == Decimal("500.00")
    assert bal3["total_meal_charges"] == Decimal("0.00")
    assert bal3["net_balance"] == Decimal("500.00")  # Not charged because absent!
    assert bal3["status"] == "CREDIT"


def test_mess_conservation_law(db_session):
    """Verify that Total Cash in Hand strictly equals sum of all member balances."""
    u1 = User(username="u1", display_name="User 1", password_hash="dummy")
    u2 = User(username="u2", display_name="User 2", password_hash="dummy")
    db_session.add_all([u1, u2])
    db_session.commit()

    # Deposits: 3000 and 2000 = 5000 total
    db_session.add_all([
        Deposit(date=date.today(), user_id=u1.id, amount=Decimal("3000.00"), status="confirmed"),
        Deposit(date=date.today(), user_id=u2.id, amount=Decimal("2000.00"), status="confirmed")
    ])
    # Meal: 1500 (split 750 each)
    meal = Meal(date=date.today(), meal_type="lunch", total_cost=Decimal("1500.00"))
    db_session.add(meal)
    db_session.flush()
    db_session.add_all([
        MealAttendance(meal_id=meal.id, user_id=u1.id, is_present=True, charged_amount=Decimal("750.00")),
        MealAttendance(meal_id=meal.id, user_id=u2.id, is_present=True, charged_amount=Decimal("750.00"))
    ])
    # Shared: 600 (split 300 each)
    shared = SharedExpense(date=date.today(), title="Water", category="Water", total_amount=Decimal("600.00"), per_member_amount=Decimal("300.00"))
    db_session.add(shared)
    db_session.flush()
    db_session.add_all([
        SharedExpenseAttendee(shared_expense_id=shared.id, user_id=u1.id, charged_amount=Decimal("300.00")),
        SharedExpenseAttendee(shared_expense_id=shared.id, user_id=u2.id, charged_amount=Decimal("300.00"))
    ])
    db_session.commit()

    summary = get_mess_overall_summary(db_session)
    assert summary["total_collected"] == Decimal("5000.00")
    assert summary["total_spent"] == Decimal("2100.00")
    assert summary["cash_in_hand"] == Decimal("2900.00")
    assert summary["is_balanced"] is True
    assert summary["member_balances_sum"] == summary["cash_in_hand"]

