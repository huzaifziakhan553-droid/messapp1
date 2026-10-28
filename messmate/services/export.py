import csv
import io
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from messmate.models import Meal, MealAttendance, SharedExpense, Deposit, AuditLog, User
from messmate.services.finance import calculate_all_balances


def export_balances_csv(session: Session) -> str:
    """Export members balances table to CSV string."""
    balances = calculate_all_balances(session, include_inactive=True)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "User ID", "Username", "Display Name", "Phone Number", "Status",
        "Total Deposits (Rs)", "Meal Charges (Rs)", "Shared Charges (Rs)",
        "Total Consumed (Rs)", "Net Balance (Rs)", "Account Status"
    ])
    for b in balances:
        writer.writerow([
            b["user_id"],
            b["username"],
            b["display_name"],
            b["phone_number"],
            "Active" if b["is_active"] else "Inactive",
            f"{b['total_deposits']:.2f}",
            f"{b['total_meal_charges']:.2f}",
            f"{b['total_shared_charges']:.2f}",
            f"{b['total_consumed']:.2f}",
            f"{b['net_balance']:.2f}",
            b["status"]
        ])
    return output.getvalue()


def export_meals_csv(session: Session) -> str:
    """Export meals and attendee charges to CSV string."""
    meals = session.query(Meal).order_by(Meal.date.desc(), Meal.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Meal ID", "Date", "Meal Type", "Title", "Category", "Total Cost (Rs)",
        "Is Reversed", "Reversal Reason", "Present Count", "Attendees (Charged Amount)"
    ])
    for m in meals:
        attendee_details = []
        for att in m.attendances:
            if att.is_present:
                attendee_details.append(f"{att.user.display_name} (Rs.{att.charged_amount})")
        writer.writerow([
            m.id,
            m.date.strftime("%Y-%m-%d"),
            m.meal_type,
            m.title or "",
            m.category,
            f"{m.total_cost:.2f}",
            "Yes" if m.is_reversed else "No",
            m.reversal_reason or "",
            m.attendee_count,
            "; ".join(attendee_details)
        ])
    return output.getvalue()


def export_deposits_csv(session: Session) -> str:
    """Export deposits ledger to CSV string."""
    deposits = session.query(Deposit).order_by(Deposit.date.desc(), Deposit.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Deposit ID", "Date", "Member ID", "Member Name", "Amount (Rs)",
        "Payment Method", "Reference No", "Status", "Is Reversed", "Notes"
    ])
    for d in deposits:
        writer.writerow([
            d.id,
            d.date.strftime("%Y-%m-%d"),
            d.user_id,
            d.user.display_name if d.user else "Unknown",
            f"{d.amount:.2f}",
            d.payment_method,
            d.reference_no or "",
            d.status,
            "Yes" if d.is_reversed else "No",
            d.notes or ""
        ])
    return output.getvalue()


def export_audit_logs_csv(session: Session) -> str:
    """Export audit trail logs to CSV string."""
    logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Log ID", "Timestamp (UTC)", "Action", "Target Type", "Target ID",
        "Performed By", "Reason", "Details"
    ])
    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.action,
            log.target_type,
            log.target_id or "",
            log.performed_by.display_name if log.performed_by else "System",
            log.reason or "",
            log.details or ""
        ])
    return output.getvalue()

