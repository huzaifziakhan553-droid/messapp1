from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from messmate.models import Meal, MealAttendance, User, AuditLog
from messmate.services.finance import to_decimal, split_expense_exact


def record_meal(
    session: Session,
    meal_date: date,
    meal_type: str,
    total_cost: Decimal,
    present_user_ids: List[int],
    title: Optional[str] = None,
    category: str = "Regular",
    notes: Optional[str] = None,
    created_by_id: Optional[int] = None
) -> Tuple[Optional[Meal], Optional[str]]:
    """
    Record a meal expense and split it exactly among the present members.
    Absent active members are recorded with is_present=False and charged_amount=0.
    """
    cost_dec = to_decimal(total_cost)
    if cost_dec <= Decimal("0.00"):
        return None, "Meal total cost must be greater than zero."

    if not present_user_ids:
        return None, "At least one member must be present to record and split a meal expense."

    # Validate that present users exist and are active
    active_users = session.query(User).filter(User.is_active == True).all()
    active_user_map = {u.id: u for u in active_users}
    
    valid_present_ids = [uid for uid in present_user_ids if uid in active_user_map]
    if not valid_present_ids:
        return None, "No active members selected as present."

    meal = Meal(
        date=meal_date,
        meal_type=meal_type.lower().strip(),
        title=title.strip() if title else f"{meal_type.capitalize()} on {meal_date}",
        category=category.strip() if category else "Regular",
        total_cost=cost_dec,
        notes=notes.strip() if notes else None,
        created_by_id=created_by_id,
        is_reversed=False
    )
    session.add(meal)
    session.flush()  # to obtain meal.id

    shares = split_expense_exact(cost_dec, len(valid_present_ids))

    # Add attendance for all active users
    for user in active_users:
        if user.id in valid_present_ids:
            idx = valid_present_ids.index(user.id)
            share_amount = shares[idx]
            att = MealAttendance(
                meal_id=meal.id,
                user_id=user.id,
                is_present=True,
                charged_amount=share_amount
            )
        else:
            att = MealAttendance(
                meal_id=meal.id,
                user_id=user.id,
                is_present=False,
                charged_amount=Decimal("0.00")
            )
        session.add(att)

    # Log in Audit
    audit = AuditLog(
        action="CREATE_MEAL",
        target_type="Meal",
        target_id=meal.id,
        performed_by_id=created_by_id,
        reason="Meal recorded",
        details=f"Created {meal.meal_type} on {meal.date} costing Rs.{cost_dec} split among {len(valid_present_ids)} attendees."
    )
    session.add(audit)
    session.commit()
    session.refresh(meal)
    return meal, None


def reverse_meal(
    session: Session,
    meal_id: int,
    reason: str,
    performed_by_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Safely reverse a meal transaction. Marks meal as reversed, sets charged amounts to 0,
    and updates the financial audit log.
    """
    meal = session.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        return False, "Meal record not found."
    if meal.is_reversed:
        return False, "This meal has already been reversed."
    if not reason or not reason.strip():
        return False, "A reason must be provided to reverse a meal transaction."

    meal.is_reversed = True
    meal.reversal_reason = reason.strip()

    # Zero out charges in attendance records for this meal
    for att in meal.attendances:
        att.charged_amount = Decimal("0.00")

    audit = AuditLog(
        action="REVERSE_MEAL",
        target_type="Meal",
        target_id=meal.id,
        performed_by_id=performed_by_id,
        reason=reason.strip(),
        details=f"Reversed meal #{meal.id} ({meal.meal_type} on {meal.date}) of Rs.{meal.total_cost}. All attendee charges zeroed."
    )
    session.add(audit)
    session.commit()
    return True, f"Meal #{meal.id} has been reversed and charges removed."


def update_meal_attendance(
    session: Session,
    meal_id: int,
    new_present_user_ids: List[int],
    reason: str,
    performed_by_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Correct attendance for an existing active meal and recalculate charges safely.
    """
    meal = session.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        return False, "Meal record not found."
    if meal.is_reversed:
        return False, "Cannot modify attendance of a reversed meal."
    if not new_present_user_ids:
        return False, "At least one member must remain present for the meal."
    if not reason or not reason.strip():
        return False, "A reason must be provided to correct finalized attendance."

    # Active members map
    all_users = session.query(User).all()
    user_map = {u.id: u for u in all_users}
    valid_present_ids = [uid for uid in new_present_user_ids if uid in user_map]

    shares = split_expense_exact(meal.total_cost, len(valid_present_ids))

    existing_attendances = {att.user_id: att for att in meal.attendances}

    for uid, user in user_map.items():
        if uid in valid_present_ids:
            idx = valid_present_ids.index(uid)
            share_val = shares[idx]
            if uid in existing_attendances:
                att = existing_attendances[uid]
                att.is_present = True
                att.charged_amount = share_val
            else:
                att = MealAttendance(meal_id=meal.id, user_id=uid, is_present=True, charged_amount=share_val)
                session.add(att)
        else:
            if uid in existing_attendances:
                att = existing_attendances[uid]
                att.is_present = False
                att.charged_amount = Decimal("0.00")
            else:
                att = MealAttendance(meal_id=meal.id, user_id=uid, is_present=False, charged_amount=Decimal("0.00"))
                session.add(att)

    audit = AuditLog(
        action="UPDATE_ATTENDANCE",
        target_type="Meal",
        target_id=meal.id,
        performed_by_id=performed_by_id,
        reason=reason.strip(),
        details=f"Recalculated meal #{meal.id} attendance: {len(valid_present_ids)} present. Per-head: Rs.{shares[0] if shares else 0}."
    )
    session.add(audit)
    session.commit()
    return True, "Meal attendance updated and member accounts recalculated."

