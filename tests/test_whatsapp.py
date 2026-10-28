import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from messmate.database import Base
from messmate.models import User, Meal, MealAttendance, Deposit
from messmate.services.whatsapp import (
    generate_daily_whatsapp_report,
    get_whatsapp_share_url,
    generate_member_statement_whatsapp
)


@pytest.fixture
def wa_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    u1 = User(username="huzaifa", display_name="Huzaifa", password_hash="x", role="admin")
    u2 = User(username="friend2", display_name="Friend 2", password_hash="x", role="member")
    session.add_all([u1, u2])
    session.commit()

    # Deposit
    dep = Deposit(date=date.today(), user_id=u1.id, amount=Decimal("2000.00"), status="confirmed")
    session.add(dep)

    # Meal
    meal = Meal(date=date.today(), meal_type="dinner", title="Chicken Biryani", category="Chicken", total_cost=Decimal("800.00"))
    session.add(meal)
    session.flush()
    att1 = MealAttendance(meal_id=meal.id, user_id=u1.id, is_present=True, charged_amount=Decimal("400.00"))
    att2 = MealAttendance(meal_id=meal.id, user_id=u2.id, is_present=True, charged_amount=Decimal("400.00"))
    session.add_all([att1, att2])
    session.commit()

    yield session
    session.close()


def test_whatsapp_daily_report_generation(wa_db):
    report = generate_daily_whatsapp_report(wa_db, report_date=date.today())
    assert "MESSMATE - DAILY HOSTEL KHAATA" in report
    assert "DINNER" in report
    assert "Rs. 800.00" in report
    assert "Huzaifa" in report
    assert "Friend 2" in report
    assert "Advance Credit" in report  # Huzaifa has 2000 - 400 = 1600 credit
    assert "DUES PENDING" in report   # Friend 2 has 0 - 400 = -400 dues


def test_whatsapp_share_url():
    msg = "Hello MessMate! Rs. 500"
    url = get_whatsapp_share_url(msg)
    assert url.startswith("https://api.whatsapp.com/send?text=")
    assert "Rs.%20500" in url or "Rs.+500" in url

    url_with_phone = get_whatsapp_share_url(msg, "+92 300 1234567")
    assert "phone=923001234567" in url_with_phone


def test_member_statement_whatsapp():
    member_data = {
        "display_name": "Ali",
        "net_balance": Decimal("-450.00"),
        "total_deposits": Decimal("1000.00"),
        "total_consumed": Decimal("1450.00")
    }
    msg = generate_member_statement_whatsapp(member_data, "28 Oct 2026")
    assert "Ali" in msg
    assert "Outstanding Dues" in msg
    assert "-Rs. 450.00" in msg

