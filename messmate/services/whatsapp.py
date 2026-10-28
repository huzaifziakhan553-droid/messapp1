import urllib.parse
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from messmate.models import Meal, SharedExpense
from messmate.services.finance import calculate_all_balances, get_mess_overall_summary


def generate_daily_whatsapp_report(session: Session, report_date: Optional[date] = None) -> str:
    """
    Format a complete daily hostel mess summary in WhatsApp Markdown format.
    """
    target_date = report_date or date.today()
    date_str = target_date.strftime("%A, %d %B %Y")

    # Fetch meals on this date
    meals = session.query(Meal).filter(
        Meal.date == target_date,
        Meal.is_reversed == False
    ).all()

    # Fetch shared expenses on this date
    shared = session.query(SharedExpense).filter(
        SharedExpense.date == target_date,
        SharedExpense.is_reversed == False
    ).all()

    total_meal_cost = sum((m.total_cost for m in meals), Decimal("0.00"))
    total_shared_cost = sum((s.total_amount for s in shared), Decimal("0.00"))
    total_day_expense = total_meal_cost + total_shared_cost

    summary = get_mess_overall_summary(session)
    member_balances = calculate_all_balances(session, include_inactive=False)

    lines = []
    lines.append(f"🍲 *JANAN MESS - DAILY HOSTEL KHAATA* 🍲")
    lines.append(f"📅 *Date:* {date_str}")
    lines.append("────────────────────────")

    # Meals Section
    if meals:
        lines.append("*🍽️ TODAY'S MEALS:*")
        for m in meals:
            presents = [a.user.display_name for a in m.attendances if a.is_present]
            count = len(presents)
            per_head = m.per_head_cost
            lines.append(f"• *{m.meal_type.upper()}* ({m.title or m.category}): Rs. {m.total_cost:,.2f}")
            lines.append(f"   👥 {count} Present: {', '.join(presents) if presents else 'None'}")
            lines.append(f"   💵 *Per Head:* Rs. {per_head:,.2f}")
    else:
        lines.append("🍽️ *Meals:* No meals recorded for today yet.")

    # Shared Expenses Section
    if shared:
        lines.append("\n*🛒 SHARED KITCHEN EXPENSES:*")
        for s in shared:
            lines.append(f"• *{s.title}* ({s.category}): Rs. {s.total_amount:,.2f} (Rs. {s.per_member_amount:,.2f}/member)")

    lines.append("\n────────────────────────")
    lines.append(f"💰 *Total Day Expense:* Rs. {total_day_expense:,.2f}")
    lines.append(f"🏦 *Mess Pool Cash in Hand:* Rs. {summary['cash_in_hand']:,.2f}")
    lines.append("────────────────────────")

    # Member Balances
    lines.append("\n*📊 MEMBER BALANCES STATUS:*")
    dues_members = []
    for mb in sorted(member_balances, key=lambda x: x["net_balance"]):
        bal = mb["net_balance"]
        name = mb["display_name"]
        if bal < Decimal("0.00"):
            lines.append(f"🔴 {name}: -Rs. {abs(bal):,.2f} *(DUES PENDING)*")
            dues_members.append((name, abs(bal)))
        elif bal > Decimal("0.00"):
            lines.append(f"🟢 {name}: +Rs. {bal:,.2f} *(Advance Credit)*")
        else:
            lines.append(f"⚪ {name}: Rs. 0.00 *(Settled)*")

    if dues_members:
        lines.append("\n⚠️ *Reminder:* Members with pending dues are kindly requested to clear their mess balance.")

    lines.append("\n_Generated via MessMate Hostel System_")

    return "\n".join(lines)


def get_whatsapp_share_url(message_text: str, phone_number: Optional[str] = None) -> str:
    """
    Generate a direct WhatsApp click-to-chat link.
    If phone_number is provided (in international format without + or spaces),
    it targets that user; otherwise opens WhatsApp to pick contact/group.
    """
    encoded_text = urllib.parse.quote(message_text)
    if phone_number:
        # Clean phone number
        clean_num = "".join(filter(str.isdigit, phone_number))
        return f"https://api.whatsapp.com/send?phone={clean_num}&text={encoded_text}"
    return f"https://api.whatsapp.com/send?text={encoded_text}"


def generate_member_statement_whatsapp(member_data: Dict[str, Any], date_str: str) -> str:
    """Generate a personal WhatsApp message statement for a single member."""
    name = member_data["display_name"]
    bal = member_data["net_balance"]
    paid = member_data["total_deposits"]
    consumed = member_data["total_consumed"]

    lines = [
        f"Assalam-o-Alaikum *{name}*,",
        f"Here is your latest Hostel Mess Account statement as of {date_str}:",
        "",
        f"💵 *Total Deposited (Paid):* Rs. {paid:,.2f}",
        f"🍲 *Total Consumed (Meals & Shared):* Rs. {consumed:,.2f}",
        "────────────────────────"
    ]
    if bal < Decimal("0.00"):
        lines.append(f"🔴 *Net Balance:* -Rs. {abs(bal):,.2f} (Outstanding Dues)")
        lines.append("\nPlease deposit your mess share via Cash / EasyPaisa / JazzCash at your earliest.")
    elif bal > Decimal("0.00"):
        lines.append(f"🟢 *Net Balance:* +Rs. {bal:,.2f} (Advance Credit Available)")
    else:
        lines.append("⚪ *Net Balance:* Rs. 0.00 (All Clear)")

    lines.append("\n_Thank you!_")
    return "\n".join(lines)

