import os
import streamlit as st
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

try:
    import pandas as pd
    def render_dataframe(data, use_container_width=True, hide_index=True):
        if isinstance(data, list):
            st.dataframe(pd.DataFrame(data), use_container_width=use_container_width, hide_index=hide_index)
        else:
            st.dataframe(data, use_container_width=use_container_width, hide_index=hide_index)
except ImportError:
    def render_dataframe(data, use_container_width=True, hide_index=True):
        st.dataframe(data, use_container_width=use_container_width)

from messmate.config import (
    MESS_NAME,
    CURRENCY_SYMBOL,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_NAME
)
from messmate.database import get_db, init_db
from messmate.models import (
    User, Meal, MealAttendance, SharedExpense, SharedExpenseAttendee,
    Deposit, AuditLog, DisputeRequest
)
from messmate.seed import seed_initial_eight_members, seed_sample_demo_data
from messmate.services.auth import (
    authenticate_user,
    change_password,
    admin_reset_password
)
from messmate.services.finance import (
    to_decimal,
    calculate_member_balance,
    calculate_all_balances,
    get_mess_overall_summary,
    split_expense_exact
)
from messmate.services.meal import (
    record_meal,
    reverse_meal,
    update_meal_attendance
)
from messmate.services.deposit import (
    record_deposit,
    reverse_deposit,
    approve_pending_deposit,
    reject_pending_deposit,
    record_shared_expense,
    reverse_shared_expense
)
from messmate.services.whatsapp import (
    generate_daily_whatsapp_report,
    get_whatsapp_share_url,
    generate_member_statement_whatsapp
)
from messmate.services.export import (
    export_balances_csv,
    export_meals_csv,
    export_deposits_csv,
    export_audit_logs_csv
)

# Set page configuration
st.set_page_config(
    page_title=f"{MESS_NAME} - MessMate",
    page_icon="🍲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling, cards, and responsive badges
st.markdown("""
<style>
    /* Main container clean style */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 12px;
    }
    .metric-title {
        color: #64748b;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metric-value {
        color: #0f172a;
        font-size: 1.75rem;
        font-weight: 700;
    }
    .metric-sub {
        color: #94a3b8;
        font-size: 0.8rem;
        margin-top: 4px;
    }
    /* Status Pills */
    .badge-credit {
        background-color: #dcfce7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.82rem;
        display: inline-block;
    }
    .badge-dues {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.82rem;
        display: inline-block;
    }
    .badge-settled {
        background-color: #f1f5f9;
        color: #475569;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.82rem;
        display: inline-block;
    }
    /* Header card */
    .app-header {
        background: linear-gradient(135deg, #047857 0%, #065f46 100%);
        color: white;
        padding: 20px 24px;
        border-radius: 14px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .app-header h1 {
        color: white !important;
        font-size: 1.8rem;
        margin: 0;
        padding: 0;
    }
    .app-header p {
        color: #a7f3d0;
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }
    /* Hide default footer */
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# Initialize DB and Seed once
@st.cache_resource
def ensure_database_initialized():
    init_db()
    with get_db() as session:
        seed_initial_eight_members(session)

ensure_database_initialized()


# Session State Initialization
if "user" not in st.session_state:
    st.session_state.user = None


def render_login_view():
    st.markdown("""
    <div class="app-header">
        <h1>🍲 MessMate</h1>
        <p>Hostel Mess Management & Khaata System for Room 8 Friends</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_demo = st.tabs(["🔑 Log In", "ℹ️ Demo Accounts & First-Run Setup"])

    with tab_login:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.subheader("Sign In to Your Account")
            with st.form("login_form"):
                username_input = st.text_input("Username", placeholder="e.g. huzaifa or friend2").strip()
                password_input = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign In 🚀", use_container_width=True)

                if submit:
                    if not username_input or not password_input:
                        st.error("Please enter both username and password.")
                    else:
                        with get_db() as session:
                            user, err = authenticate_user(session, username_input, password_input)
                            if user:
                                st.session_state.user = {
                                    "id": user.id,
                                    "username": user.username,
                                    "display_name": user.display_name,
                                    "role": user.role,
                                    "phone_number": user.phone_number
                                }
                                st.success(f"Welcome back, {user.display_name}!")
                                st.rerun()
                            else:
                                st.error(err)

    with tab_demo:
        st.info("💡 **First-Time Quick Access:** Below are the initial accounts created for the 8 hostel roommates:")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"""
            **👑 Administrator Account:**
            - **Username:** `{DEFAULT_ADMIN_USERNAME}`
            - **Password:** `{DEFAULT_ADMIN_PASSWORD}`
            - **Role:** Administrator (Full mess management, expense split, deposits & reports)
            """)
        with col_b:
            st.markdown("""
            **👤 Member Accounts (Friend 2 to Friend 8):**
            - **Usernames:** `friend2`, `friend3`, `friend4`, `friend5`, `friend6`, `friend7`, `friend8`
            - **Password:** `MessFriend123!`
            - **Role:** Member (View balances, attendance history, submit payments/disputes)
            """)
        
        st.divider()
        st.markdown("#### Populate Realistic Demo Data")
        st.caption("Click below if you would like to load sample deposits, shared expenses, and meals (e.g. Chicken Karahi, Parathas) to preview reports immediately.")
        if st.button("✨ Load Sample Activity Data"):
            with get_db() as session:
                seed_sample_demo_data(session)
            st.success("Sample demo transactions loaded! You can now log in to view the dashboard.")


def render_app_header(current_user):
    with get_db() as session:
        bal_info = calculate_member_balance(session, current_user["id"])
    
    bal = bal_info["net_balance"]
    if bal > Decimal("0.00"):
        pill_html = f"<span class='badge-credit'>🟢 Balance: +{CURRENCY_SYMBOL} {bal:,.2f} (Credit)</span>"
    elif bal < Decimal("0.00"):
        pill_html = f"<span class='badge-dues'>🔴 Balance: -{CURRENCY_SYMBOL} {abs(bal):,.2f} (Dues)</span>"
    else:
        pill_html = f"<span class='badge-settled'>⚪ Balance: {CURRENCY_SYMBOL} 0.00 (Settled)</span>"

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(f"### 🍲 {MESS_NAME}")
        st.caption(f"Signed in as **{current_user['display_name']}** (`{current_user['username']}`) • Role: **{current_user['role'].upper()}**")
    with col_h2:
        st.markdown(f"<div style='text-align: right; padding-top: 10px;'>{pill_html}</div>", unsafe_allow_html=True)
        if st.button("Sign Out 🚪", key="btn_signout", use_container_width=True):
            st.session_state.user = None
            st.rerun()


# ==========================================
# 1. MESS DASHBOARD
# ==========================================
def view_dashboard(current_user):
    st.subheader("📊 Mess Overview & Khaata Summary")
    
    with get_db() as session:
        summary = get_mess_overall_summary(session)
        members = calculate_all_balances(session, include_inactive=False)
        today_meals = session.query(Meal).filter(Meal.date == date.today(), Meal.is_reversed == False).all()

    # Metric Row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        cash = summary["cash_in_hand"]
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Mess Pool (Cash in Hand)</div>
            <div class="metric-value">{CURRENCY_SYMBOL} {cash:,.2f}</div>
            <div class="metric-sub">Net available mess fund</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        spent = summary["total_spent"]
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Mess Expenses</div>
            <div class="metric-value">{CURRENCY_SYMBOL} {spent:,.2f}</div>
            <div class="metric-sub">Meals + Shared kitchen items</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        dues = summary["total_dues"]
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Outstanding Dues</div>
            <div class="metric-value" style="color: #dc2626;">{CURRENCY_SYMBOL} {dues:,.2f}</div>
            <div class="metric-sub">Unpaid balances across members</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        active_count = summary["active_member_count"]
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Active Roommates</div>
            <div class="metric-value">{active_count} Friends</div>
            <div class="metric-sub">Accounting Status: {"✅ Healthy" if summary['is_balanced'] else "⚠️ Alert"}</div>
        </div>
        """, unsafe_allow_html=True)

    # Member Balances Table
    st.markdown("#### 👥 Roommate Accounts & Balances")
    table_data = []
    for m in members:
        bal = m["net_balance"]
        if bal > Decimal("0.00"):
            status_display = f"🟢 +{CURRENCY_SYMBOL} {bal:,.2f} (Credit)"
        elif bal < Decimal("0.00"):
            status_display = f"🔴 -{CURRENCY_SYMBOL} {abs(bal):,.2f} (Dues)"
        else:
            status_display = f"⚪ {CURRENCY_SYMBOL} 0.00 (Clear)"

        table_data.append({
            "Member": m["display_name"],
            "Username": m["username"],
            "Phone": m["phone_number"] or "-",
            "Total Paid": f"{CURRENCY_SYMBOL} {m['total_deposits']:,.2f}",
            "Meals Consumed": f"{CURRENCY_SYMBOL} {m['total_meal_charges']:,.2f}",
            "Shared Consumed": f"{CURRENCY_SYMBOL} {m['total_shared_charges']:,.2f}",
            "Net Balance": status_display
        })

    render_dataframe(table_data)

    # Today's Meals Section
    col_tm1, col_tm2 = st.columns([2, 1])
    with col_tm1:
        st.markdown("#### 🍽️ Today's Recorded Meals")
        if not today_meals:
            st.info("No meals recorded for today yet. Use the **Daily Meals & Attendance** tab to enter breakfast, lunch, or dinner.")
        else:
            for tm in today_meals:
                presents = [a.user.display_name for a in tm.attendances if a.is_present]
                with st.expander(f"**{tm.meal_type.upper()}**: {tm.title} — {CURRENCY_SYMBOL} {tm.total_cost:,.2f} (Rs. {tm.per_head_cost:,.2f} / person)", expanded=True):
                    st.write(f"**Category:** {tm.category} | **Attendees ({len(presents)}):** {', '.join(presents)}")
                    if tm.notes:
                        st.caption(f"Notes: {tm.notes}")

    with col_tm2:
        st.markdown("#### 📢 Quick WhatsApp Update")
        with get_db() as session:
            daily_report_txt = generate_daily_whatsapp_report(session, date.today())
        wa_url = get_whatsapp_share_url(daily_report_txt)
        st.markdown(f"""
        Share today's meals and Khaata balances directly to the hostel WhatsApp group with one click:
        
        <a href="{wa_url}" target="_blank" style="text-decoration:none;">
            <button style="width:100%; padding:10px 14px; background-color:#25D366; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">
                📲 Share Daily Update on WhatsApp
            </button>
        </a>
        """, unsafe_allow_html=True)


# ==========================================
# 2. MEALS & ATTENDANCE MANAGEMENT
# ==========================================
def view_meals(current_user):
    st.subheader("🍽️ Meal Expense & Attendance Management")

    if current_user["role"] == "admin":
        tab_record, tab_history = st.tabs(["➕ Record Meal & Attendance", "📜 Meal History & Corrections"])
    else:
        tab_history, tab_record = st.tabs(["📜 Meal History & Attendance", "ℹ️ Attendance Rules"])

    # Admin Recording Tab
    if current_user["role"] == "admin":
        with tab_record:
            st.markdown("##### Record a Meal Expense and Split with Attendees")
            with get_db() as session:
                active_users = session.query(User).filter(User.is_active == True).order_by(User.id).all()

            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                meal_date = st.date_input("Meal Date", value=date.today())
                meal_type = st.selectbox("Meal Type", ["dinner", "lunch", "breakfast", "custom"])
            with col_m2:
                meal_cost = st.number_input("Total Expense (PKR / Rs.)", min_value=0.0, step=50.0, value=1200.0)
                category = st.selectbox("Food Category", ["Chicken", "Beef", "Mutton", "Vegetable", "Daal", "Eggs", "Special Biryani", "Fast Food", "Misc"])
            with col_m3:
                meal_title = st.text_input("Meal Title / Dish", placeholder="e.g. Chicken Karahi & Naan")
                meal_notes = st.text_input("Notes (Optional)", placeholder="e.g. 1kg chicken, 10 naans, yogurt")

            st.markdown("###### Mark Present Members for This Meal:")
            col_b1, col_b2, col_b3 = st.columns([1, 1, 4])
            with col_b1:
                select_all = st.button("✅ Select All", use_container_width=True)
            with col_b2:
                clear_all = st.button("❌ Clear All", use_container_width=True)

            # Checkbox grid for members
            cols = st.columns(4)
            present_user_ids = []
            
            for idx, u in enumerate(active_users):
                with cols[idx % 4]:
                    default_state = True
                    if clear_all:
                        default_state = False
                    elif select_all:
                        default_state = True
                    
                    is_present = st.checkbox(
                        f"**{u.display_name}**",
                        value=default_state,
                        key=f"att_check_{u.id}_{idx}"
                    )
                    if is_present:
                        present_user_ids.append(u.id)

            present_count = len(present_user_ids)
            absent_count = len(active_users) - present_count
            per_head = (Decimal(str(meal_cost)) / Decimal(present_count)) if present_count > 0 else Decimal("0.00")

            st.info(f"👥 **Attendance Summary:** Present: **{present_count}** | Absent: **{absent_count}** | **Cost Per Head:** {CURRENCY_SYMBOL} {per_head:,.2f}")

            if st.button("💾 Save Meal & Charge Attendees", type="primary", use_container_width=True):
                if meal_cost <= 0:
                    st.error("Please enter a total expense greater than zero.")
                elif not present_user_ids:
                    st.error("At least one member must be present to split the meal expense.")
                else:
                    with get_db() as session:
                        meal, err = record_meal(
                            session=session,
                            meal_date=meal_date,
                            meal_type=meal_type,
                            total_cost=Decimal(str(meal_cost)),
                            present_user_ids=present_user_ids,
                            title=meal_title,
                            category=category,
                            notes=meal_notes,
                            created_by_id=current_user["id"]
                        )
                        if meal:
                            st.success(f"✅ Recorded {meal_type.capitalize()} of {CURRENCY_SYMBOL} {meal_cost:,.2f}. {present_count} attendees charged {CURRENCY_SYMBOL} {per_head:,.2f} each!")
                            st.rerun()
                        else:
                            st.error(err)

    # History & Corrections Tab
    with tab_history:
        st.markdown("##### Recorded Meals History")
        with get_db() as session:
            meals = session.query(Meal).order_by(Meal.date.desc(), Meal.id.desc()).all()
            all_users = session.query(User).all()
            user_dict = {u.id: u for u in all_users}

        if not meals:
            st.info("No meals recorded yet.")
        else:
            for m in meals:
                status_label = "❌ REVERSED" if m.is_reversed else "✅ ACTIVE"
                present_names = [a.user.display_name for a in m.attendances if a.is_present]
                
                with st.expander(f"{status_label} | {m.date} - **{m.meal_type.upper()}** ({m.title or m.category}) — {CURRENCY_SYMBOL} {m.total_cost:,.2f}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**Total Cost:** {CURRENCY_SYMBOL} {m.total_cost:,.2f}")
                        st.write(f"**Present ({len(present_names)}):** {', '.join(present_names) if present_names else 'None'}")
                        st.write(f"**Per Head Charge:** {CURRENCY_SYMBOL} {m.per_head_cost:,.2f}")
                        if m.notes:
                            st.write(f"**Notes:** {m.notes}")
                        if m.is_reversed:
                            st.warning(f"**Reversal Reason:** {m.reversal_reason}")

                    # Admin Actions (Edit attendance or Reverse)
                    if current_user["role"] == "admin" and not m.is_reversed:
                        with c2:
                            st.markdown("###### Actions")
                            
                            # Correction Form
                            with st.popover("✏️ Correct Attendance"):
                                st.write(f"Edit attendees for Meal #{m.id}")
                                current_presents = [a.user_id for a in m.attendances if a.is_present]
                                new_selection = []
                                for u in all_users:
                                    if u.is_active or u.id in current_presents:
                                        checked = st.checkbox(u.display_name, value=(u.id in current_presents), key=f"edit_att_{m.id}_{u.id}")
                                        if checked:
                                            new_selection.append(u.id)
                                reason = st.text_input("Reason for correction", key=f"corr_reason_{m.id}")
                                if st.button("Apply Correction", key=f"btn_corr_{m.id}"):
                                    if not reason:
                                        st.error("Please provide a reason.")
                                    elif not new_selection:
                                        st.error("At least one member must remain present.")
                                    else:
                                        with get_db() as session:
                                            ok, msg = update_meal_attendance(session, m.id, new_selection, reason, current_user["id"])
                                            if ok:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)

                            # Reversal Form
                            with st.popover("↩️ Reverse Meal"):
                                st.write(f"Reverse Meal #{m.id} entirely")
                                rev_reason = st.text_input("Reason for Reversal", key=f"rev_reason_{m.id}")
                                if st.button("Confirm Reversal", key=f"btn_rev_{m.id}", type="primary"):
                                    if not rev_reason:
                                        st.error("A reason is mandatory for reversal.")
                                    else:
                                        with get_db() as session:
                                            ok, msg = reverse_meal(session, m.id, rev_reason, current_user["id"])
                                            if ok:
                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)


# ==========================================
# 3. SHARED EXPENSES
# ==========================================
def view_shared_expenses(current_user):
    st.subheader("🛒 Shared Hostel Expenses")
    st.caption("Common kitchen items and utilities (Cook salary, cooking oil, spices, gas cylinder, drinking water) split equally.")

    tab_rec, tab_hist = st.tabs(["➕ Record Shared Expense", "📜 Shared Expenses Ledger"])

    with tab_rec:
        if current_user["role"] != "admin":
            st.warning("Only the mess administrator can record shared expenses.")
        else:
            with get_db() as session:
                users = session.query(User).filter(User.is_active == True).all()

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                s_date = st.date_input("Expense Date", value=date.today())
                s_title = st.text_input("Expense Title", placeholder="e.g. Monthly Cook Salary or Gas Refill")
                s_category = st.selectbox("Category", ["Cook Salary", "Gas Cylinder Refill", "Drinking Water Canisters", "Cooking Oil & Masala Stock", "Kitchen Cleaning Supplies", "Other"])
            with col_s2:
                s_amount = st.number_input("Total Amount (PKR)", min_value=0.0, step=100.0, value=2000.0)
                s_notes = st.text_area("Notes", placeholder="Receipt details, quantity, etc.")

            st.markdown("###### Split Among Members:")
            member_opts = {u.id: u.display_name for u in users}
            selected_members = st.multiselect("Select Included Members", options=list(member_opts.keys()), default=list(member_opts.keys()), format_func=lambda x: member_opts[x])

            if selected_members:
                per_head = Decimal(str(s_amount)) / Decimal(len(selected_members))
                st.info(f"💵 Each of the **{len(selected_members)}** members will be charged: **{CURRENCY_SYMBOL} {per_head:,.2f}**")

            if st.button("💾 Record Shared Expense", type="primary"):
                if s_amount <= 0:
                    st.error("Please enter a valid amount.")
                elif not s_title:
                    st.error("Please enter an expense title.")
                elif not selected_members:
                    st.error("At least one member must be selected.")
                else:
                    with get_db() as session:
                        exp, err = record_shared_expense(
                            session=session,
                            expense_date=s_date,
                            title=s_title,
                            category=s_category,
                            total_amount=Decimal(str(s_amount)),
                            attendee_ids=selected_members,
                            notes=s_notes,
                            created_by_id=current_user["id"]
                        )
                        if exp:
                            st.success(f"Recorded '{s_title}' of {CURRENCY_SYMBOL} {s_amount:,.2f} split among {len(selected_members)} friends!")
                            st.rerun()
                        else:
                            st.error(err)

    with tab_hist:
        with get_db() as session:
            expenses = session.query(SharedExpense).order_by(SharedExpense.date.desc(), SharedExpense.id.desc()).all()

        if not expenses:
            st.info("No shared expenses recorded yet.")
        else:
            for exp in expenses:
                status_str = "❌ REVERSED" if exp.is_reversed else "✅ ACTIVE"
                attendees = [a.user.display_name for a in exp.attendees]
                with st.expander(f"{status_str} | {exp.date} - **{exp.title}** ({exp.category}) — {CURRENCY_SYMBOL} {exp.total_amount:,.2f}"):
                    st.write(f"**Split Among ({len(attendees)}):** {', '.join(attendees)}")
                    st.write(f"**Per Member Share:** {CURRENCY_SYMBOL} {exp.per_member_amount:,.2f}")
                    if exp.notes:
                        st.caption(f"Notes: {exp.notes}")
                    if exp.is_reversed:
                        st.warning(f"Reversal Reason: {exp.reversal_reason}")
                    elif current_user["role"] == "admin":
                        with st.popover("↩️ Reverse Shared Expense"):
                            rev_reason = st.text_input("Reason", key=f"rev_sh_{exp.id}")
                            if st.button("Confirm Reversal", key=f"btn_rev_sh_{exp.id}"):
                                if not rev_reason:
                                    st.error("Reason required.")
                                else:
                                    with get_db() as session:
                                        ok, msg = reverse_shared_expense(session, exp.id, rev_reason, current_user["id"])
                                        if ok:
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)


# ==========================================
# 4. DEPOSITS & KHAATA POOL
# ==========================================
def view_deposits(current_user):
    st.subheader("💰 Member Deposits & Advance Pool Contributions")

    tab_record, tab_ledger, tab_pending = st.tabs(["➕ Record Deposit", "📜 Deposits Ledger", "📥 Pending Approvals"])

    with tab_record:
        col_d1, col_d2 = st.columns(2)
        with get_db() as session:
            users = session.query(User).order_by(User.id).all()
            user_map = {u.id: u.display_name for u in users}

        with col_d1:
            dep_date = st.date_input("Deposit Date", value=date.today())
            if current_user["role"] == "admin":
                target_user_id = st.selectbox("Select Member", options=list(user_map.keys()), format_func=lambda x: user_map[x])
            else:
                target_user_id = current_user["id"]
                st.write(f"**Depositing for:** {current_user['display_name']}")
            
            dep_amount = st.number_input("Amount (PKR / Rs.)", min_value=100.0, step=500.0, value=3000.0)

        with col_d2:
            pay_method = st.selectbox("Payment Method", ["Cash", "EasyPaisa", "JazzCash", "NayaPay", "SadaPay", "Bank Transfer"])
            ref_no = st.text_input("Transaction ID / Reference (Optional)", placeholder="e.g. TID 1092837482")
            notes = st.text_input("Notes (Optional)", placeholder="e.g. Paid in cash to Huzaifa")

        if current_user["role"] == "admin":
            btn_label = "💾 Confirm & Record Deposit"
        else:
            btn_label = "📤 Submit Payment for Admin Approval"

        if st.button(btn_label, type="primary"):
            if dep_amount <= 0:
                st.error("Amount must be positive.")
            else:
                status = "confirmed" if current_user["role"] == "admin" else "pending_approval"
                with get_db() as session:
                    dep, err = record_deposit(
                        session=session,
                        user_id=target_user_id,
                        amount=Decimal(str(dep_amount)),
                        payment_method=pay_method,
                        reference_no=ref_no,
                        notes=notes,
                        status=status,
                        created_by_id=current_user["id"],
                        deposit_date=dep_date
                    )
                    if dep:
                        if status == "confirmed":
                            st.success(f"✅ Successfully deposited {CURRENCY_SYMBOL} {dep_amount:,.2f} to {user_map[target_user_id]}'s account!")
                        else:
                            st.success(f"📤 Payment proof submitted! Admin will verify and approve your {CURRENCY_SYMBOL} {dep_amount:,.2f} deposit.")
                        st.rerun()
                    else:
                        st.error(err)

    with tab_ledger:
        with get_db() as session:
            deps_query = session.query(Deposit).order_by(Deposit.date.desc(), Deposit.id.desc())
            if current_user["role"] != "admin":
                deps_query = deps_query.filter(Deposit.user_id == current_user["id"])
            deps = deps_query.all()

        if not deps:
            st.info("No deposit records found.")
        else:
            dep_rows = []
            for d in deps:
                status_str = "❌ Reversed" if d.is_reversed else ("⏳ Pending Approval" if d.status == "pending_approval" else "✅ Confirmed")
                dep_rows.append({
                    "ID": d.id,
                    "Date": d.date.strftime("%Y-%m-%d"),
                    "Member": d.user.display_name if d.user else "Unknown",
                    "Amount": f"{CURRENCY_SYMBOL} {d.amount:,.2f}",
                    "Method": d.payment_method,
                    "Reference": d.reference_no or "-",
                    "Status": status_str,
                    "Notes": d.notes or "-"
                })
            render_dataframe(dep_rows)

            if current_user["role"] == "admin":
                with st.expander("↩️ Reverse an Incorrect Deposit"):
                    rev_dep_id = st.number_input("Deposit ID to Reverse", min_value=1, step=1)
                    rev_dep_reason = st.text_input("Reason for reversing deposit")
                    if st.button("Confirm Deposit Reversal"):
                        if not rev_dep_reason:
                            st.error("Reason is mandatory.")
                        else:
                            with get_db() as session:
                                ok, msg = reverse_deposit(session, rev_dep_id, rev_dep_reason, current_user["id"])
                                if ok:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

    with tab_pending:
        st.markdown("##### Member Payment Confirmations Pending Verification")
        with get_db() as session:
            pendings = session.query(Deposit).filter(Deposit.status == "pending_approval", Deposit.is_reversed == False).all()

        if not pendings:
            st.success("No pending payment approvals.")
        else:
            for p in pendings:
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.write(f"**{p.user.display_name}** deposited **{CURRENCY_SYMBOL} {p.amount:,.2f}** via {p.payment_method} on {p.date}")
                    st.caption(f"Ref: {p.reference_no or 'None'} | Notes: {p.notes or 'None'}")
                if current_user["role"] == "admin":
                    with c2:
                        if st.button("✅ Approve", key=f"app_dep_{p.id}"):
                            with get_db() as session:
                                ok, msg = approve_pending_deposit(session, p.id, current_user["id"])
                                st.success(msg)
                                st.rerun()
                    with c3:
                        if st.button("❌ Reject", key=f"rej_dep_{p.id}"):
                            with get_db() as session:
                                ok, msg = reject_pending_deposit(session, p.id, "Payment not received in bank/wallet", current_user["id"])
                                st.warning(msg)
                                st.rerun()


# ==========================================
# 5. WHATSAPP REPORTS
# ==========================================
def view_whatsapp(current_user):
    st.subheader("📢 Shareable WhatsApp Reports")
    st.caption("Generate official WhatsApp formatted summaries of daily meals and member balances.")

    with get_db() as session:
        members = calculate_all_balances(session, include_inactive=False)

    report_date = st.date_input("Select Report Date", value=date.today())
    with get_db() as session:
        wa_text = generate_daily_whatsapp_report(session, report_date)

    st.markdown("#### Preview of WhatsApp Message:")
    st.text_area("Formatted Message", value=wa_text, height=260)

    url_group = get_whatsapp_share_url(wa_text)

    col_w1, col_w2 = st.columns([1, 1])
    with col_w1:
        st.markdown(f"""
        <a href="{url_group}" target="_blank" style="text-decoration:none;">
            <button style="width:100%; padding:12px; background-color:#25D366; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">
                📲 Share to WhatsApp Group
            </button>
        </a>
        """, unsafe_allow_html=True)

    with col_w2:
        st.markdown("###### Send Individual Statement to a Friend:")
        target_name = st.selectbox("Select Friend", options=[m["display_name"] for m in members])
        target_member = next(m for m in members if m["display_name"] == target_name)
        individual_msg = generate_member_statement_whatsapp(target_member, report_date.strftime("%d %b %Y"))
        indiv_url = get_whatsapp_share_url(individual_msg, target_member["phone_number"])
        
        st.markdown(f"""
        <a href="{indiv_url}" target="_blank" style="text-decoration:none;">
            <button style="width:100%; padding:10px; background-color:#128C7E; color:white; border:none; border-radius:8px; font-weight:bold; cursor:pointer;">
                💬 Send Statement to {target_name} on WhatsApp
            </button>
        </a>
        """, unsafe_allow_html=True)


# ==========================================
# 6. MEMBER DIRECTORY & MANAGEMENT
# ==========================================
def view_members(current_user):
    st.subheader("👥 Roommate Directory & Account Management")

    with get_db() as session:
        all_members = session.query(User).order_by(User.id).all()
        member_balances = {m["user_id"]: m for m in calculate_all_balances(session, include_inactive=True)}

    tab_dir, tab_edit, tab_add = st.tabs(["📋 Directory", "✏️ Update Member Info", "➕ Add New Roommate"])

    with tab_dir:
        rows = []
        for u in all_members:
            b = member_balances.get(u.id, {})
            net = b.get("net_balance", Decimal("0.00"))
            rows.append({
                "ID": u.id,
                "Name": u.display_name,
                "Username": u.username,
                "Role": u.role.upper(),
                "Phone": u.phone_number or "-",
                "Status": "🟢 Active" if u.is_active else "🔴 Inactive",
                "Net Balance": f"{CURRENCY_SYMBOL} {net:,.2f}"
            })
        render_dataframe(rows)

    with tab_edit:
        if current_user["role"] != "admin":
            st.info("Contact the administrator to change names or deactivate accounts.")
        else:
            st.markdown("##### Update Member Display Name or Status")
            member_opts = {u.id: f"{u.display_name} ({u.username})" for u in all_members}
            selected_uid = st.selectbox("Select Member to Edit", options=list(member_opts.keys()), format_func=lambda x: member_opts[x])
            
            target = next(u for u in all_members if u.id == selected_uid)
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                new_name = st.text_input("Display Name", value=target.display_name)
                new_phone = st.text_input("Phone Number", value=target.phone_number or "")
            with col_e2:
                is_active = st.checkbox("Active Member", value=target.is_active)
                role_choice = st.selectbox("Role", ["member", "admin"], index=0 if target.role == "member" else 1)

            if st.button("💾 Save Member Updates"):
                with get_db() as session:
                    user_to_update = session.query(User).filter(User.id == selected_uid).first()
                    user_to_update.display_name = new_name.strip()
                    user_to_update.phone_number = new_phone.strip()
                    user_to_update.is_active = is_active
                    user_to_update.role = role_choice
                    session.commit()
                st.success(f"Updated {new_name}'s profile!")
                st.rerun()

            st.divider()
            st.markdown("##### 🔑 Admin Reset Password")
            new_pass = st.text_input("New Temporary Password for Member", placeholder="At least 6 characters", type="password")
            if st.button("Reset Member's Password"):
                with get_db() as session:
                    u_reset = session.query(User).filter(User.id == selected_uid).first()
                    ok, msg = admin_reset_password(session, u_reset, new_pass)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    with tab_add:
        if current_user["role"] != "admin":
            st.warning("Only admin can register new roommates.")
        else:
            st.markdown("##### Add a New Roommate to the Mess")
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                add_username = st.text_input("New Username", placeholder="e.g. usman").strip().lower()
                add_name = st.text_input("Display Name", placeholder="e.g. Usman Tariq")
            with col_a2:
                add_phone = st.text_input("Phone Number", placeholder="03001234567")
                add_pass = st.text_input("Password", type="password", value="MessFriend123!")

            if st.button("➕ Register Member"):
                if not add_username or not add_name:
                    st.error("Username and Name are required.")
                else:
                    with get_db() as session:
                        existing = session.query(User).filter(User.username == add_username).first()
                        if existing:
                            st.error(f"Username '{add_username}' is already taken.")
                        else:
                            from messmate.services.auth import hash_password
                            new_u = User(
                                username=add_username,
                                display_name=add_name,
                                phone_number=add_phone,
                                password_hash=hash_password(add_pass),
                                role="member",
                                is_active=True
                            )
                            session.add(new_u)
                            session.commit()
                            st.success(f"Roommate '{add_name}' registered successfully!")
                            st.rerun()


# ==========================================
# 7. FINANCIAL STATEMENTS & AUDIT LOG
# ==========================================
def view_ledger_and_audit(current_user):
    st.subheader("📑 Financial Statements, Reports & Audit Trail")

    tab_export, tab_audit = st.tabs(["📥 Export Financial Reports (CSV)", "🔍 Complete Audit Trail"])

    with tab_export:
        st.markdown("##### Download Exportable Spreadsheets")
        st.caption("Export exact balance sheets and ledger data for offline records or Excel analysis.")

        with get_db() as session:
            csv_balances = export_balances_csv(session)
            csv_meals = export_meals_csv(session)
            csv_deposits = export_deposits_csv(session)
            csv_audit = export_audit_logs_csv(session)

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 Download Member Balances Statement (.csv)",
                data=csv_balances,
                file_name=f"messmate_balances_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.download_button(
                "📥 Download Meals & Attendance Register (.csv)",
                data=csv_meals,
                file_name=f"messmate_meals_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c2:
            st.download_button(
                "📥 Download Deposits & Khaata Pool Ledger (.csv)",
                data=csv_deposits,
                file_name=f"messmate_deposits_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.download_button(
                "📥 Download Complete Audit Trail (.csv)",
                data=csv_audit,
                file_name=f"messmate_audit_trail_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True
            )

    with tab_audit:
        st.markdown("##### System Audit Logs (Transaction Reversals & Modifications)")
        with get_db() as session:
            logs = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()

        if not logs:
            st.info("No audit logs recorded yet.")
        else:
            log_rows = []
            for l in logs:
                log_rows.append({
                    "Timestamp (UTC)": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Action": l.action,
                    "Target": f"{l.target_type} #{l.target_id or ''}",
                    "Admin / User": l.performed_by.display_name if l.performed_by else "System",
                    "Reason": l.reason or "-",
                    "Details": l.details or "-"
                })
            render_dataframe(log_rows)


# ==========================================
# 8. DISPUTES & CORRECTION REQUESTS
# ==========================================
def view_disputes(current_user):
    st.subheader("🙋 Disputes & Correction Requests")
    st.caption("Roommates can raise attendance discrepancies or payment queries here.")

    tab_submit, tab_review = st.tabs(["📝 Submit Dispute / Query", "📋 All Requests"])

    with tab_submit:
        st.markdown("##### Submit an Attendance Correction or Khaata Query")
        req_type = st.selectbox("Request Type", [
            "Attendance Discrepancy (e.g. marked present while absent)",
            "Payment Proof / Unrecorded Deposit",
            "General Expense Query"
        ])
        req_desc = st.text_area("Detailed Explanation", placeholder="e.g. I was away in my hometown on Friday dinner and did not eat. Please remove my Rs. 400 charge.")

        if st.button("📤 Submit Request to Admin", type="primary"):
            if not req_desc:
                st.error("Please provide details for your dispute.")
            else:
                with get_db() as session:
                    dispute = DisputeRequest(
                        user_id=current_user["id"],
                        request_type=req_type,
                        description=req_desc,
                        status="PENDING"
                    )
                    session.add(dispute)
                    session.commit()
                st.success("Your dispute request has been submitted to the mess administrator.")
                st.rerun()

    with tab_review:
        with get_db() as session:
            d_query = session.query(DisputeRequest).order_by(DisputeRequest.created_at.desc())
            if current_user["role"] != "admin":
                d_query = d_query.filter(DisputeRequest.user_id == current_user["id"])
            disputes = d_query.all()

        if not disputes:
            st.info("No dispute requests found.")
        else:
            for d in disputes:
                status_color = "🟡 PENDING" if d.status == "PENDING" else ("🟢 APPROVED" if d.status == "APPROVED" else "🔴 REJECTED")
                with st.expander(f"{status_color} | {d.user.display_name} - {d.request_type} ({d.created_at.strftime('%Y-%m-%d')})"):
                    st.write(f"**Explanation:** {d.description}")
                    if d.admin_notes:
                        st.info(f"**Admin Note:** {d.admin_notes}")
                    
                    if current_user["role"] == "admin" and d.status == "PENDING":
                        admin_note_input = st.text_input("Resolution Note", key=f"d_note_{d.id}")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Mark Resolved / Approved", key=f"btn_d_app_{d.id}"):
                                with get_db() as session:
                                    disp = session.query(DisputeRequest).filter(DisputeRequest.id == d.id).first()
                                    disp.status = "APPROVED"
                                    disp.admin_notes = admin_note_input or "Approved by admin"
                                    disp.resolved_at = datetime.now(timezone.utc)
                                    session.commit()
                                st.success("Marked as Approved!")
                                st.rerun()
                        with c2:
                            if st.button("❌ Reject Dispute", key=f"btn_d_rej_{d.id}"):
                                with get_db() as session:
                                    disp = session.query(DisputeRequest).filter(DisputeRequest.id == d.id).first()
                                    disp.status = "REJECTED"
                                    disp.admin_notes = admin_note_input or "Rejected by admin"
                                    disp.resolved_at = datetime.now(timezone.utc)
                                    session.commit()
                                st.warning("Marked as Rejected.")
                                st.rerun()


# ==========================================
# 9. PROFILE & SETTINGS
# ==========================================
def view_profile(current_user):
    st.subheader("🔒 My Profile & Security")

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("##### Profile Details")
        st.write(f"**Display Name:** {current_user['display_name']}")
        st.write(f"**Username:** `{current_user['username']}`")
        st.write(f"**Role:** {current_user['role'].upper()}")
        st.write(f"**Phone Number:** {current_user['phone_number'] or 'Not provided'}")

    with col_p2:
        st.markdown("##### Change Password")
        old_p = st.text_input("Current Password", type="password")
        new_p = st.text_input("New Password", type="password")
        confirm_p = st.text_input("Confirm New Password", type="password")

        if st.button("Update Password"):
            if new_p != confirm_p:
                st.error("New passwords do not match.")
            else:
                with get_db() as session:
                    u = session.query(User).filter(User.id == current_user["id"]).first()
                    ok, msg = change_password(session, u, old_p, new_p)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


# ==========================================
# MAIN ROUTING
# ==========================================
def main():
    if not st.session_state.user:
        render_login_view()
        return

    render_app_header(st.session_state.user)

    # Sidebar Navigation
    with st.sidebar:
        st.markdown(f"### 🧭 Navigation")
        
        menu_options = [
            "📊 Dashboard",
            "🍽️ Daily Meals & Attendance",
            "🛒 Shared Kharcha",
            "💰 Deposits & Khaata",
            "📢 WhatsApp Reports",
            "👥 Roommates Directory",
            "📑 Financial Statements & Audit",
            "🙋 Disputes & Requests",
            "🔒 My Profile"
        ]
        
        choice = st.radio("Go to:", menu_options, label_visibility="collapsed")
        st.divider()
        st.caption("MessMate v1.0 • Built for Hostel Friends")

    # Route page
    if choice == "📊 Dashboard":
        view_dashboard(st.session_state.user)
    elif choice == "🍽️ Daily Meals & Attendance":
        view_meals(st.session_state.user)
    elif choice == "🛒 Shared Kharcha":
        view_shared_expenses(st.session_state.user)
    elif choice == "💰 Deposits & Khaata":
        view_deposits(st.session_state.user)
    elif choice == "📢 WhatsApp Reports":
        view_whatsapp(st.session_state.user)
    elif choice == "👥 Roommates Directory":
        view_members(st.session_state.user)
    elif choice == "📑 Financial Statements & Audit":
        view_ledger_and_audit(st.session_state.user)
    elif choice == "🙋 Disputes & Requests":
        view_disputes(st.session_state.user)
    elif choice == "🔒 My Profile":
        view_profile(st.session_state.user)


if __name__ == "__main__":
    main()

