"""
MessMate CLI Interface
Quick terminal management tool for the Hostel Mess Management System.
Shares the same database and financial models with the Streamlit web application.
"""

import sys
from datetime import date

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from decimal import Decimal
from messmate.database import init_db, get_db
from messmate.seed import seed_initial_eight_members
from messmate.models import User, Meal, Deposit
from messmate.services.finance import calculate_all_balances, get_mess_overall_summary
from messmate.services.meal import record_meal
from messmate.services.deposit import record_deposit
from messmate.services.whatsapp import generate_daily_whatsapp_report


def print_dashboard():
    with get_db() as session:
        summary = get_mess_overall_summary(session)
        members = calculate_all_balances(session, include_inactive=False)

    print("\n" + "=" * 70)
    print("                    JANAN MESS KHAATA DASHBOARD")
    print("=" * 70)
    print(f"Mess Pool (Cash in Hand): Rs. {summary['cash_in_hand']:,.2f}")
    print(f"Total Expenses:           Rs. {summary['total_spent']:,.2f}")
    print(f"Total Outstanding Dues:   Rs. {summary['total_dues']:,.2f}")
    print("-" * 70)
    print(f"{'Name':<14} | {'Total Paid':<14} | {'Total Consumed':<16} | {'Net Balance':<18}")
    print("-" * 70)
    for m in members:
        bal = m["net_balance"]
        if bal > Decimal("0.00"):
            status = f"+Rs.{bal:,.2f} (Credit)"
        elif bal < Decimal("0.00"):
            status = f"-Rs.{abs(bal):,.2f} (Dues)"
        else:
            status = "Rs. 0.00 (Settled)"
        print(f"{m['display_name']:<14} | Rs.{m['total_deposits']:<11,.2f} | Rs.{m['total_consumed']:<13,.2f} | {status:<18}")
    print("=" * 70)


def add_meal_cli():
    print("\n--- Record Meal Expense & Split ---")
    with get_db() as session:
        active_users = session.query(User).filter(User.is_active == True).order_by(User.id).all()
        admin = session.query(User).filter(User.role == "admin").first()

    meal_type = input("Enter meal type (breakfast / lunch / dinner) [default: dinner]: ").strip().lower() or "dinner"
    title = input("Enter dish/meal title (e.g. Chicken Karahi): ").strip()
    try:
        total_cost = float(input("Enter total expense for this meal (Rs.): "))
    except ValueError:
        print("❌ Invalid cost amount.")
        return

    print("\nMark attendance for active roommates (y/n):")
    present_ids = []
    for u in active_users:
        ans = input(f"  Was {u.display_name} present? (y/n) [default: y]: ").strip().lower()
        if ans != 'n':
            present_ids.append(u.id)

    if not present_ids:
        print("❌ No members marked present. Cannot record meal.")
        return

    with get_db() as session:
        meal, err = record_meal(
            session=session,
            meal_date=date.today(),
            meal_type=meal_type,
            total_cost=Decimal(str(total_cost)),
            present_user_ids=present_ids,
            title=title,
            created_by_id=admin.id if admin else None
        )
        if meal:
            print(f"✅ Recorded {meal_type.capitalize()}! Total: Rs. {total_cost:,.2f} split among {len(present_ids)} members (Rs. {meal.per_head_cost:,.2f} each).")
        else:
            print(f"❌ Error: {err}")


def add_deposit_cli():
    print("\n--- Record Member Deposit ---")
    with get_db() as session:
        users = session.query(User).filter(User.is_active == True).order_by(User.id).all()
        admin = session.query(User).filter(User.role == "admin").first()

    print("Active Members:")
    for idx, u in enumerate(users, 1):
        print(f"  {idx}. {u.display_name} ({u.username})")

    try:
        choice = int(input("Select member number: "))
        selected_user = users[choice - 1]
        amount = float(input(f"Enter deposit amount for {selected_user.display_name} (Rs.): "))
    except (ValueError, IndexError):
        print("❌ Invalid selection or amount.")
        return

    method = input("Payment method (Cash, EasyPaisa, JazzCash, etc.) [default: Cash]: ").strip() or "Cash"
    ref = input("Transaction Ref / Notes (optional): ").strip()

    with get_db() as session:
        dep, err = record_deposit(
            session=session,
            user_id=selected_user.id,
            amount=Decimal(str(amount)),
            payment_method=method,
            reference_no=ref,
            status="confirmed",
            created_by_id=admin.id if admin else None
        )
        if dep:
            print(f"✅ Successfully recorded Rs. {amount:,.2f} deposit for {selected_user.display_name}!")
        else:
            print(f"❌ Error: {err}")


def print_whatsapp_report():
    with get_db() as session:
        report = generate_daily_whatsapp_report(session, date.today())
    print("\n--- WHATSAPP DAILY REPORT PREVIEW ---")
    print(report)
    print("-------------------------------------")


def main():
    init_db()
    with get_db() as session:
        seed_initial_eight_members(session)

    while True:
        print("\n=== MESSMATE CLI ===")
        print("1. View Dashboard (Balances & Khaata)")
        print("2. Record Meal Expense (Daily Kharcha)")
        print("3. Record Advance Deposit")
        print("4. Generate WhatsApp Report")
        print("5. Exit")

        c = input("Choose an option (1-5): ").strip()
        if c == '1':
            print_dashboard()
        elif c == '2':
            add_meal_cli()
        elif c == '3':
            add_deposit_cli()
        elif c == '4':
            print_whatsapp_report()
        elif c == '5':
            print("Allah Hafiz!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    main()

