from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import Dict, List, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from messmate.models import User, Meal, MealAttendance, SharedExpense, SharedExpenseAttendee, Deposit

TWO_PLACES = Decimal("0.01")


def to_decimal(value: Any) -> Decimal:
    """Safely convert any numeric/string value to Decimal with 2 decimal places."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    try:
        return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def split_expense_exact(total_cost: Decimal, num_attendees: int) -> List[Decimal]:
    """
    Split an exact Decimal amount among `num_attendees` with penny-exact balance.
    Example: Rs. 100 split among 3 people -> [33.34, 33.33, 33.33].
    Sum is guaranteed to exactly equal total_cost.
    """
    if num_attendees <= 0:
        return []
    total = to_decimal(total_cost)
    base = (total / Decimal(num_attendees)).quantize(TWO_PLACES, rounding=ROUND_DOWN)
    remainder = total - (base * Decimal(num_attendees))
    
    # remainder in cents
    cents = int((remainder * Decimal(100)).to_integral_value())
    
    shares = []
    for i in range(num_attendees):
        if i < cents:
            shares.append(base + Decimal("0.01"))
        else:
            shares.append(base)
    return shares


def calculate_member_balance(session: Session, user_id: int) -> Dict[str, Any]:
    """
    Compute real-time balance for a single member from persisted ledger records.
    Net Balance = Confirmed Deposits - Meal Charges - Shared Expense Charges.
    """
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        return {
            "user_id": user_id,
            "display_name": "Unknown",
            "total_deposits": Decimal("0.00"),
            "total_meal_charges": Decimal("0.00"),
            "total_shared_charges": Decimal("0.00"),
            "total_consumed": Decimal("0.00"),
            "net_balance": Decimal("0.00"),
            "status": "SETTLED"
        }

    # 1. Total Confirmed Deposits (excluding reversed)
    deposits_sum = session.query(func.coalesce(func.sum(Deposit.amount), 0)).filter(
        Deposit.user_id == user_id,
        Deposit.status == "confirmed",
        Deposit.is_reversed == False
    ).scalar()
    total_deposits = to_decimal(deposits_sum)

    # 2. Total Meal Charges (only for active meals, where present)
    meals_sum = session.query(func.coalesce(func.sum(MealAttendance.charged_amount), 0)).join(
        Meal, Meal.id == MealAttendance.meal_id
    ).filter(
        MealAttendance.user_id == user_id,
        MealAttendance.is_present == True,
        Meal.is_reversed == False
    ).scalar()
    total_meal_charges = to_decimal(meals_sum)

    # 3. Total Shared Charges (only for active shared expenses)
    shared_sum = session.query(func.coalesce(func.sum(SharedExpenseAttendee.charged_amount), 0)).join(
        SharedExpense, SharedExpense.id == SharedExpenseAttendee.shared_expense_id
    ).filter(
        SharedExpenseAttendee.user_id == user_id,
        SharedExpense.is_reversed == False
    ).scalar()
    total_shared_charges = to_decimal(shared_sum)

    total_consumed = (total_meal_charges + total_shared_charges).quantize(TWO_PLACES)
    net_balance = (total_deposits - total_consumed).quantize(TWO_PLACES)

    if net_balance > Decimal("0.00"):
        status = "CREDIT"
    elif net_balance < Decimal("0.00"):
        status = "DUES"
    else:
        status = "SETTLED"

    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "phone_number": user.phone_number or "",
        "is_active": user.is_active,
        "total_deposits": total_deposits,
        "total_meal_charges": total_meal_charges,
        "total_shared_charges": total_shared_charges,
        "total_consumed": total_consumed,
        "net_balance": net_balance,
        "status": status
    }


def calculate_all_balances(session: Session, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Compute balances for all users in the system."""
    query = session.query(User).order_by(User.id)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    users = query.all()
    return [calculate_member_balance(session, u.id) for u in users]


def get_mess_overall_summary(session: Session) -> Dict[str, Any]:
    """
    Compute macro-financial health of the hostel mess:
    - Total Cash Collected
    - Total Expenses (Meals + Shared)
    - Cash in Hand (Mess Pool)
    - Total Outstanding Dues
    - Total Member Credit
    - Audit conservation sanity check
    """
    # 1. Total Confirmed Deposits
    dep_sum = session.query(func.coalesce(func.sum(Deposit.amount), 0)).filter(
        Deposit.status == "confirmed",
        Deposit.is_reversed == False
    ).scalar()
    total_collected = to_decimal(dep_sum)

    # 2. Total Meal Expenses
    meal_sum = session.query(func.coalesce(func.sum(Meal.total_cost), 0)).filter(
        Meal.is_reversed == False
    ).scalar()
    total_meals_expense = to_decimal(meal_sum)

    # 3. Total Shared Expenses
    shared_sum = session.query(func.coalesce(func.sum(SharedExpense.total_amount), 0)).filter(
        SharedExpense.is_reversed == False
    ).scalar()
    total_shared_expense = to_decimal(shared_sum)

    total_spent = (total_meals_expense + total_shared_expense).quantize(TWO_PLACES)
    cash_in_hand = (total_collected - total_spent).quantize(TWO_PLACES)

    # 4. Sum up member balances
    members = calculate_all_balances(session, include_inactive=True)
    total_dues = Decimal("0.00")
    total_credit = Decimal("0.00")
    sum_balances = Decimal("0.00")

    for m in members:
        bal = m["net_balance"]
        sum_balances += bal
        if bal < Decimal("0.00"):
            total_dues += abs(bal)
        else:
            total_credit += bal

    # Math sanity check (difference should be 0.00 or negligible pennies due to remainder rounding)
    diff = abs(cash_in_hand - sum_balances)
    is_balanced = diff <= Decimal("0.05")

    return {
        "total_collected": total_collected,
        "total_spent": total_spent,
        "total_meals_expense": total_meals_expense,
        "total_shared_expense": total_shared_expense,
        "cash_in_hand": cash_in_hand,
        "total_dues": total_dues,
        "total_credit": total_credit,
        "member_balances_sum": sum_balances,
        "is_balanced": is_balanced,
        "active_member_count": sum(1 for m in members if m["is_active"]),
        "total_member_count": len(members)
    }

