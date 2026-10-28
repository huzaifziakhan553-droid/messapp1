from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from messmate.models import Deposit, SharedExpense, SharedExpenseAttendee, User, AuditLog
from messmate.services.finance import to_decimal, split_expense_exact


def record_deposit(
    session: Session,
    user_id: int,
    amount: Decimal,
    payment_method: str = "Cash",
    reference_no: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = "confirmed",
    created_by_id: Optional[int] = None,
    deposit_date: Optional[date] = None
) -> Tuple[Optional[Deposit], Optional[str]]:
    """
    Record an advance payment / deposit into the mess pool.
    """
    amount_dec = to_decimal(amount)
    if amount_dec <= Decimal("0.00"):
        return None, "Deposit amount must be greater than zero."

    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        return None, "Member not found."

    dep = Deposit(
        date=deposit_date or date.today(),
        user_id=user_id,
        amount=amount_dec,
        payment_method=payment_method,
        reference_no=reference_no.strip() if reference_no else None,
        notes=notes.strip() if notes else None,
        status=status,
        is_reversed=False,
        created_by_id=created_by_id
    )
    session.add(dep)
    session.flush()

    audit = AuditLog(
        action="RECORD_DEPOSIT",
        target_type="Deposit",
        target_id=dep.id,
        performed_by_id=created_by_id,
        reason=f"Deposit recorded via {payment_method}",
        details=f"Rs.{amount_dec} deposited for {user.display_name} ({user.username}). Status: {status}."
    )
    session.add(audit)
    session.commit()
    session.refresh(dep)
    return dep, None


def reverse_deposit(
    session: Session,
    deposit_id: int,
    reason: str,
    performed_by_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Safely reverse a deposit (e.g. bounce, misentry, or refunded).
    """
    dep = session.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not dep:
        return False, "Deposit record not found."
    if dep.is_reversed:
        return False, "This deposit has already been reversed."
    if not reason or not reason.strip():
        return False, "A reason must be provided to reverse a deposit."

    dep.is_reversed = True
    dep.reversal_reason = reason.strip()

    audit = AuditLog(
        action="REVERSE_DEPOSIT",
        target_type="Deposit",
        target_id=dep.id,
        performed_by_id=performed_by_id,
        reason=reason.strip(),
        details=f"Reversed deposit #{dep.id} of Rs.{dep.amount} for User #{dep.user_id}."
    )
    session.add(audit)
    session.commit()
    return True, f"Deposit #{dep.id} has been reversed."


def approve_pending_deposit(
    session: Session,
    deposit_id: int,
    performed_by_id: Optional[int] = None
) -> Tuple[bool, str]:
    """Admin approves a payment confirmation submitted by a member."""
    dep = session.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not dep:
        return False, "Deposit not found."
    if dep.status == "confirmed":
        return False, "Deposit is already confirmed."

    dep.status = "confirmed"
    audit = AuditLog(
        action="APPROVE_DEPOSIT",
        target_type="Deposit",
        target_id=dep.id,
        performed_by_id=performed_by_id,
        reason="Admin confirmed member payment receipt",
        details=f"Approved Rs.{dep.amount} payment for User #{dep.user_id} ({dep.payment_method})."
    )
    session.add(audit)
    session.commit()
    return True, "Payment successfully approved and credited to member's account."


def reject_pending_deposit(
    session: Session,
    deposit_id: int,
    reason: str,
    performed_by_id: Optional[int] = None
) -> Tuple[bool, str]:
    """Admin rejects a pending deposit submission."""
    dep = session.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not dep:
        return False, "Deposit not found."
    dep.status = "rejected"
    dep.notes = f"{dep.notes or ''} [Rejected: {reason}]".strip()
    audit = AuditLog(
        action="REJECT_DEPOSIT",
        target_type="Deposit",
        target_id=dep.id,
        performed_by_id=performed_by_id,
        reason=reason,
        details=f"Rejected payment claim of Rs.{dep.amount} for User #{dep.user_id}."
    )
    session.add(audit)
    session.commit()
    return True, "Payment claim marked as rejected."


def record_shared_expense(
    session: Session,
    expense_date: date,
    title: str,
    category: str,
    total_amount: Decimal,
    attendee_ids: List[int],
    notes: Optional[str] = None,
    created_by_id: Optional[int] = None
) -> Tuple[Optional[SharedExpense], Optional[str]]:
    """
    Record general shared costs (Cook, gas, oil/spices, water, cleaning)
    and split among selected members.
    """
    total_dec = to_decimal(total_amount)
    if total_dec <= Decimal("0.00"):
        return None, "Shared expense amount must be greater than zero."
    if not attendee_ids:
        return None, "At least one member must be selected for shared expense."

    active_users = session.query(User).filter(User.is_active == True).all()
    user_map = {u.id: u for u in active_users}
    valid_ids = [uid for uid in attendee_ids if uid in user_map]
    if not valid_ids:
        return None, "No active members selected."

    shares = split_expense_exact(total_dec, len(valid_ids))
    per_member = shares[0] if shares else Decimal("0.00")

    shared = SharedExpense(
        date=expense_date,
        title=title.strip(),
        category=category.strip(),
        total_amount=total_dec,
        per_member_amount=per_member,
        notes=notes.strip() if notes else None,
        created_by_id=created_by_id,
        is_reversed=False
    )
    session.add(shared)
    session.flush()

    for idx, uid in enumerate(valid_ids):
        att = SharedExpenseAttendee(
            shared_expense_id=shared.id,
            user_id=uid,
            charged_amount=shares[idx]
        )
        session.add(att)

    audit = AuditLog(
        action="CREATE_SHARED_EXPENSE",
        target_type="SharedExpense",
        target_id=shared.id,
        performed_by_id=created_by_id,
        reason=f"Shared expense '{title}' recorded",
        details=f"Rs.{total_dec} for '{title}' ({category}) split among {len(valid_ids)} members."
    )
    session.add(audit)
    session.commit()
    session.refresh(shared)
    return shared, None


def reverse_shared_expense(
    session: Session,
    shared_expense_id: int,
    reason: str,
    performed_by_id: Optional[int] = None
) -> Tuple[bool, str]:
    """Safely reverse a shared expense transaction."""
    shared = session.query(SharedExpense).filter(SharedExpense.id == shared_expense_id).first()
    if not shared:
        return False, "Shared expense record not found."
    if shared.is_reversed:
        return False, "This shared expense has already been reversed."
    if not reason or not reason.strip():
        return False, "A reason must be provided to reverse a shared expense."

    shared.is_reversed = True
    shared.reversal_reason = reason.strip()

    for att in shared.attendees:
        att.charged_amount = Decimal("0.00")

    audit = AuditLog(
        action="REVERSE_SHARED_EXPENSE",
        target_type="SharedExpense",
        target_id=shared.id,
        performed_by_id=performed_by_id,
        reason=reason.strip(),
        details=f"Reversed shared expense #{shared.id} ('{shared.title}') of Rs.{shared.total_amount}."
    )
    session.add(audit)
    session.commit()
    return True, f"Shared expense #{shared.id} has been reversed."

