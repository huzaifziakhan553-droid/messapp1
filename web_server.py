"""
MessMate Web Application Server
A zero-dependency, responsive web server using Python's standard library and SQLAlchemy.
Supports Huzaifa as Admin, member self-registration with admin approvals,
strict hisab-kitab privacy (members see mess pool remaining + their personal hisab kitab only),
and comprehensive admin editing and password resets.
"""

import sys
import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import date, datetime
from decimal import Decimal

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from messmate.database import init_db, get_db
from messmate.seed import seed_initial_eight_members
from messmate.models import User, Meal, MealAttendance, Deposit, SharedExpense, DisputeRequest, AuditLog
from messmate.services.auth import (
    authenticate_user,
    register_user,
    approve_user_registration,
    reject_user_registration,
    admin_reset_password
)
from messmate.services.finance import (
    calculate_member_balance,
    calculate_all_balances,
    get_mess_overall_summary
)
from messmate.services.meal import record_meal, reverse_meal
from messmate.services.deposit import record_deposit, reverse_deposit, record_shared_expense
from messmate.services.whatsapp import generate_daily_whatsapp_report, get_whatsapp_share_url
from messmate.services.export import export_balances_csv, export_meals_csv, export_deposits_csv

# In-memory session store: { cookie_token: user_dict }
SESSIONS = {}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Janan Mess - Hostel Mess Management System</title>
    <style>
        :root {
            --primary: #047857;
            --primary-dark: #065f46;
            --primary-light: #d1fae5;
            --text-dark: #0f172a;
            --text-muted: #64748b;
            --bg-light: #f8fafc;
            --card-bg: #ffffff;
            --border-color: #e2e8f0;
            --danger: #dc2626;
            --danger-bg: #fee2e2;
            --success: #166534;
            --success-bg: #dcfce7;
            --warning: #b45309;
            --warning-bg: #fef3c7;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: var(--bg-light); color: var(--text-dark); line-height: 1.5; padding-bottom: 40px; }
        
        .navbar {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            flex-wrap: wrap;
            gap: 12px;
        }
        .navbar h1 { font-size: 1.35rem; display: flex; align-items: center; gap: 8px; }
        .nav-user { display: flex; align-items: center; gap: 12px; font-size: 0.9rem; flex-wrap: wrap; }
        .nav-btn { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.4); color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 0.85rem; font-weight: 600; }
        .nav-btn:hover { background: rgba(255,255,255,0.3); }

        .container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }

        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .metric-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .metric-title { font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .metric-value { font-size: 1.65rem; font-weight: 700; color: var(--text-dark); }
        .metric-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

        .card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 22px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 24px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; flex-wrap: wrap; gap: 8px; }
        .card-header h2 { font-size: 1.2rem; color: var(--text-dark); display: flex; align-items: center; gap: 8px; }

        table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.92rem; }
        th { text-align: left; padding: 12px 14px; background: #f1f5f9; color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border-color); }
        td { padding: 12px 14px; border-bottom: 1px solid var(--border-color); }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background-color: #f8fafc; }

        .badge-credit { background: var(--success-bg); color: var(--success); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }
        .badge-dues { background: var(--danger-bg); color: var(--danger); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }
        .badge-settled { background: #f1f5f9; color: var(--text-muted); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }
        .badge-warning { background: var(--warning-bg); color: var(--warning); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }

        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; margin-bottom: 16px; }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-group label { font-size: 0.85rem; font-weight: 600; color: #334155; }
        .form-group input, .form-group select, .form-group textarea {
            padding: 9px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 0.95rem; outline: none; transition: border-color 0.2s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color: var(--primary); }

        .btn { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 0.92rem; cursor: pointer; border: none; text-decoration: none; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-dark); }
        .btn-whatsapp { background: #25D366; color: white; }
        .btn-whatsapp:hover { background: #1eb855; }
        .btn-secondary { background: #f1f5f9; color: #334155; border: 1px solid var(--border-color); }
        .btn-secondary:hover { background: #e2e8f0; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { background: #b91c1c; }
        .btn-sm { padding: 6px 12px; font-size: 0.82rem; }

        .attendance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 12px 0 18px 0; }
        .att-label { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: #f8fafc; border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; }
        .att-label input { width: 18px; height: 18px; accent-color: var(--primary); }

        .alert-success { background: #dcfce7; border: 1px solid #bbf7d0; color: #166534; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.92rem; }
        .alert-error { background: #fee2e2; border: 1px solid #fecaca; color: #991b1b; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.92rem; }
        .alert-info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.92rem; }

        .tabs-header { display: flex; gap: 8px; border-bottom: 2px solid var(--border-color); margin-bottom: 20px; }
        .tab-btn { padding: 10px 18px; background: none; border: none; font-size: 0.95rem; font-weight: 600; color: var(--text-muted); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; }
        .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }
    </style>
</head>
<body>
    {NAVBAR}
    <div class="container">
        {MESSAGE}
        {CONTENT}
    </div>
</body>
</html>
"""


class MessMateHandler(BaseHTTPRequestHandler):
    def get_current_user(self):
        cookie = self.headers.get("Cookie", "")
        for item in cookie.split(";"):
            item = item.strip()
            if item.startswith("messmate_session="):
                token = item.split("=", 1)[1]
                return SESSIONS.get(token)
        return None

    def send_html(self, html_content, set_cookie=None):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def send_redirect(self, path, set_cookie=None):
        self.send_response(303)
        self.send_header("Location", path)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        msg = query.get("msg", [""])[0]
        err = query.get("err", [""])[0]

        msg_html = ""
        if msg:
            msg_html = f'<div class="alert-success">✅ {urllib.parse.unquote(msg)}</div>'
        elif err:
            msg_html = f'<div class="alert-error">❌ {urllib.parse.unquote(err)}</div>'

        user = self.get_current_user()

        # Route /login or unauthenticated
        if path == "/login" or not user:
            tab = query.get("tab", ["login"])[0]
            self.render_login_signup_page(msg_html, active_tab=tab)
            return

        # Route /logout
        if path == "/logout":
            self.send_redirect("/login", set_cookie="messmate_session=; Path=/; Max-Age=0")
            return

        # Route /export/... (Admin only)
        if path.startswith("/export/") and user["role"] == "admin":
            if path == "/export/balances.csv":
                with get_db() as session:
                    csv_data = export_balances_csv(session)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", 'attachment; filename="messmate_balances.csv"')
                self.end_headers()
                self.wfile.write(csv_data.encode("utf-8"))
                return
            if path == "/export/meals.csv":
                with get_db() as session:
                    csv_data = export_meals_csv(session)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", 'attachment; filename="messmate_meals.csv"')
                self.end_headers()
                self.wfile.write(csv_data.encode("utf-8"))
                return
            if path == "/export/deposits.csv":
                with get_db() as session:
                    csv_data = export_deposits_csv(session)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", 'attachment; filename="messmate_deposits.csv"')
                self.end_headers()
                self.wfile.write(csv_data.encode("utf-8"))
                return

        # Route Main Dashboard
        self.render_dashboard(user, msg_html)

    def render_login_signup_page(self, msg_html, active_tab="login"):
        is_login = active_tab != "signup"

        tab_nav = f"""
        <div class="tabs-header" style="justify-content: center;">
            <a href="/login?tab=login" class="tab-btn {'active' if is_login else ''}" style="text-decoration: none;">🔑 Sign In</a>
            <a href="/login?tab=signup" class="tab-btn {'active' if not is_login else ''}" style="text-decoration: none;">📝 Sign Up (New Roommate)</a>
        </div>
        """

        if is_login:
            form_content = """
            <form method="POST" action="/api/login">
                <div class="form-group" style="margin-bottom: 14px;">
                    <label>Username</label>
                    <input type="text" name="username" placeholder="e.g. huzaifa or friend2" required>
                </div>
                <div class="form-group" style="margin-bottom: 20px;">
                    <label>Password</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">Sign In 🚀</button>
            </form>

            <div style="margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--border-color); font-size: 0.85rem; color: var(--text-muted);">
                <strong>💡 Sign-In Help:</strong>
                <div style="margin-top: 4px;">• <strong>Admin:</strong> <code>huzaifa</code></div>
                <div>• <strong>Roommates:</strong> Sign in with your approved username.</div>
                <div>• <em>Forgot password? Contact Administrator Huzaifa to reset your credentials.</em></div>
            </div>
            """
        else:
            form_content = """
            <div class="alert-info" style="font-size: 0.85rem; margin-bottom: 16px;">
                📢 <strong>Note:</strong> After signing up, your account will be sent to <strong>Administrator Huzaifa</strong> for approval and activation before you can log in.
            </div>
            <form method="POST" action="/api/register">
                <div class="form-group" style="margin-bottom: 12px;">
                    <label>Your Full Name / Display Name</label>
                    <input type="text" name="display_name" placeholder="e.g. Ali Ahmed" required>
                </div>
                <div class="form-group" style="margin-bottom: 12px;">
                    <label>Desired Username</label>
                    <input type="text" name="username" placeholder="e.g. ali" required>
                </div>
                <div class="form-group" style="margin-bottom: 12px;">
                    <label>Phone Number (WhatsApp)</label>
                    <input type="text" name="phone_number" placeholder="e.g. 03001234567">
                </div>
                <div class="form-group" style="margin-bottom: 20px;">
                    <label>Password (At least 6 characters)</label>
                    <input type="password" name="password" required minlength="6">
                </div>
                <button type="submit" class="btn btn-primary" style="width: 100%;">Submit Registration 📝</button>
            </form>
            """

        content = f"""
        <div style="max-width: 480px; margin: 30px auto;">
            <div class="card">
                <div class="card-header" style="justify-content: center; border-bottom: none; padding-bottom: 0;">
                    <h2>🍲 Janan Mess</h2>
                </div>
                <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 16px; text-align: center;">
                    Hostel Mess Khaata System for Room 8 Friends
                </p>
                {tab_nav}
                {form_content}
            </div>
        </div>
        """
        navbar = """
        <div class="navbar">
            <h1>🍲 Janan Mess</h1>
            <div class="nav-user">Hostel Mess System</div>
        </div>
        """
        html = HTML_TEMPLATE.replace("{NAVBAR}", navbar).replace("{MESSAGE}", msg_html).replace("{CONTENT}", content)
        self.send_html(html)

    def render_dashboard(self, user, msg_html):
        is_admin = user["role"] == "admin"

        with get_db() as session:
            summary = get_mess_overall_summary(session)
            my_bal = calculate_member_balance(session, user["id"])
            
            # Fetch pending user registrations (Admin only)
            pending_users = []
            if is_admin:
                pending_raw = session.query(User).filter(User.approval_status == "pending").all()
                pending_users = [{"id": u.id, "name": u.display_name, "username": u.username, "phone": u.phone_number or "-", "created": u.created_at.strftime("%Y-%m-%d")} for u in pending_raw]

            # Fetch all active users
            raw_users = session.query(User).filter(User.is_active == True).order_by(User.id).all()
            all_users_data = [{"id": u.id, "display_name": u.display_name, "username": u.username, "phone": u.phone_number or "-", "role": u.role} for u in raw_users]

            # Fetch all users for admin edit tool
            raw_all_registered = session.query(User).order_by(User.id).all()
            all_registered_data = [{"id": u.id, "display_name": u.display_name, "username": u.username, "phone": u.phone_number or "", "role": u.role, "is_active": u.is_active} for u in raw_all_registered]

            # Member's personal hisab kitab transactions
            my_attendances = session.query(MealAttendance, Meal).join(Meal, Meal.id == MealAttendance.meal_id).filter(
                MealAttendance.user_id == user["id"],
                MealAttendance.is_present == True,
                Meal.is_reversed == False
            ).order_by(Meal.date.desc(), Meal.id.desc()).all()

            my_meals_data = []
            for att, m in my_attendances:
                my_meals_data.append({
                    "date": m.date.strftime("%Y-%m-%d"),
                    "meal_type": m.meal_type.upper(),
                    "title": m.title or m.category,
                    "charged": att.charged_amount
                })

            my_deposits_raw = session.query(Deposit).filter(Deposit.user_id == user["id"]).order_by(Deposit.date.desc(), Deposit.id.desc()).all()
            my_deposits_data = []
            for d in my_deposits_raw:
                my_deposits_data.append({
                    "date": d.date.strftime("%Y-%m-%d"),
                    "amount": d.amount,
                    "method": d.payment_method,
                    "status": "❌ Reversed" if d.is_reversed else ("⏳ Pending" if d.status == "pending_approval" else "✅ Confirmed"),
                    "notes": d.notes or "-"
                })

            # For admin: full members summary
            all_member_balances = calculate_all_balances(session, include_inactive=False) if is_admin else []
            wa_text = generate_daily_whatsapp_report(session, date.today())

        wa_url = get_whatsapp_share_url(wa_text)

        # Personal Balance Pill
        bal = my_bal["net_balance"]
        if bal > Decimal("0.00"):
            my_pill = f'<span class="badge-credit">🟢 My Balance: +Rs. {bal:,.2f} (Credit)</span>'
        elif bal < Decimal("0.00"):
            my_pill = f'<span class="badge-dues">🔴 My Balance: -Rs. {abs(bal):,.2f} (Dues)</span>'
        else:
            my_pill = '<span class="badge-settled">⚪ My Balance: Rs. 0.00 (Clear)</span>'

        navbar = f"""
        <div class="navbar">
            <h1>🍲 Janan Mess</h1>
            <div class="nav-user">
                <span>{my_pill}</span>
                <span>👤 <strong>{user['display_name']}</strong> ({user['role'].upper()})</span>
                <a href="/logout" class="nav-btn">Sign Out</a>
            </div>
        </div>
        """

        content_parts = []

        # ==============================================================
        # 1. METRICS ROW
        # Both Admin and Members see Total Mess Money Remaining!
        # Members see ONLY their own financial stats; Admin sees full mess stats.
        # ==============================================================
        if is_admin:
            content_parts.append(f"""
            <div class="metrics-grid">
                <div class="metric-card" style="border-left: 4px solid var(--primary);">
                    <div class="metric-title">🏦 Total Mess Pool (Money Remaining)</div>
                    <div class="metric-value">Rs. {summary['cash_in_hand']:,.2f}</div>
                    <div class="metric-sub">Net communal mess fund</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Total Mess Expenses</div>
                    <div class="metric-value">Rs. {summary['total_spent']:,.2f}</div>
                    <div class="metric-sub">Meals + Shared items</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Total Roommate Dues</div>
                    <div class="metric-value" style="color: var(--danger);">Rs. {summary['total_dues']:,.2f}</div>
                    <div class="metric-sub">Unpaid balances across roommates</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Active Roommates</div>
                    <div class="metric-value">{summary['active_member_count']} Friends</div>
                    <div class="metric-sub">Admin: <strong>Huzaifa</strong></div>
                </div>
            </div>
            """)
        else:
            # REGULAR MEMBER VIEW:
            # Sees Total Mess Money Remaining, but ONLY their personal hisab kitab!
            content_parts.append(f"""
            <div class="metrics-grid">
                <div class="metric-card" style="border-left: 4px solid var(--primary);">
                    <div class="metric-title">🏦 Total Mess Pool (Money Remaining)</div>
                    <div class="metric-value">Rs. {summary['cash_in_hand']:,.2f}</div>
                    <div class="metric-sub">Communal fund in mess pool</div>
                </div>
                <div class="metric-card" style="border-left: 4px solid {'#166534' if bal >= 0 else '#dc2626'};">
                    <div class="metric-title">👤 My Net Balance</div>
                    <div class="metric-value" style="color: {'var(--success)' if bal >= 0 else 'var(--danger)'};">
                        {'Rs. ' if bal >= 0 else '-Rs. '}{abs(bal):,.2f}
                    </div>
                    <div class="metric-sub">{'🟢 Advance credit available' if bal >= 0 else '🔴 Outstanding dues pending'}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">💵 My Total Paid (Deposits)</div>
                    <div class="metric-value">Rs. {my_bal['total_deposits']:,.2f}</div>
                    <div class="metric-sub">All cash/digital deposits you paid</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">🍲 My Total Consumed</div>
                    <div class="metric-value">Rs. {my_bal['total_consumed']:,.2f}</div>
                    <div class="metric-sub">Meals & shared costs charged to you</div>
                </div>
            </div>
            """)

        # ==============================================================
        # 2. PENDING REGISTRATIONS (ADMIN ONLY)
        # ==============================================================
        if is_admin:
            if pending_users:
                pending_rows = []
                for pu in pending_users:
                    pending_rows.append(f"""
                    <tr>
                        <td><strong>{pu['name']}</strong></td>
                        <td><code>{pu['username']}</code></td>
                        <td>{pu['phone']}</td>
                        <td>{pu['created']}</td>
                        <td><span class="badge-warning">Pending Approval</span></td>
                        <td>
                            <div style="display: flex; gap: 6px;">
                                <form method="POST" action="/api/approve_user" style="display: inline;">
                                    <input type="hidden" name="user_id" value="{pu['id']}">
                                    <button type="submit" class="btn btn-primary btn-sm">✅ Approve</button>
                                </form>
                                <form method="POST" action="/api/reject_user" style="display: inline;">
                                    <input type="hidden" name="user_id" value="{pu['id']}">
                                    <button type="submit" class="btn btn-danger btn-sm">❌ Reject</button>
                                </form>
                            </div>
                        </td>
                    </tr>
                    """)
                content_parts.append(f"""
                <div class="card" style="border: 2px solid var(--warning);">
                    <div class="card-header">
                        <h2>📥 Pending Roommate Registrations ({len(pending_users)})</h2>
                    </div>
                    <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 12px;">
                        The following people signed up. Click <strong>Approve</strong> to activate their account and allow them to log in:
                    </p>
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Username</th>
                                    <th>Phone</th>
                                    <th>Applied On</th>
                                    <th>Status</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(pending_rows)}
                            </tbody>
                        </table>
                    </div>
                </div>
                """)

        # ==============================================================
        # 3. KHAATA TABLE
        # ADMIN sees all roommates.
        # MEMBER sees ONLY their personal hisab kitab (others are completely hidden).
        # ==============================================================
        if is_admin:
            member_rows = []
            for m in all_member_balances:
                b = m["net_balance"]
                if b > Decimal("0.00"):
                    badge = f'<span class="badge-credit">+Rs. {b:,.2f} (Credit)</span>'
                elif b < Decimal("0.00"):
                    badge = f'<span class="badge-dues">-Rs. {abs(b):,.2f} (Dues)</span>'
                else:
                    badge = '<span class="badge-settled">Rs. 0.00 (Clear)</span>'

                member_rows.append(f"""
                <tr>
                    <td><strong>{m['display_name']}</strong></td>
                    <td><code>{m['username']}</code></td>
                    <td>{m['phone_number'] or '-'}</td>
                    <td>Rs. {m['total_deposits']:,.2f}</td>
                    <td>Rs. {m['total_meal_charges']:,.2f}</td>
                    <td>Rs. {m['total_shared_charges']:,.2f}</td>
                    <td>{badge}</td>
                </tr>
                """)

            content_parts.append(f"""
            <div class="card">
                <div class="card-header">
                    <h2>👥 Roommates Master Khaata (Admin View)</h2>
                    <div style="display: flex; gap: 8px;">
                        <a href="/export/balances.csv" class="btn btn-secondary">📥 Export Balances (CSV)</a>
                        <a href="{wa_url}" target="_blank" class="btn btn-whatsapp">📲 WhatsApp Update</a>
                    </div>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Roommate</th>
                                <th>Username</th>
                                <th>Phone</th>
                                <th>Total Paid</th>
                                <th>Meals Cost</th>
                                <th>Shared Cost</th>
                                <th>Net Balance</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(member_rows)}
                        </tbody>
                    </table>
                </div>
            </div>
            """)
        else:
            # MEMBER PERSONAL HISAB KITAB ONLY:
            meal_rows = []
            for mm in my_meals_data:
                meal_rows.append(f"""
                <tr>
                    <td>{mm['date']}</td>
                    <td><strong>{mm['meal_type']}</strong></td>
                    <td>{mm['title']}</td>
                    <td style="color: var(--danger); font-weight: 600;">-Rs. {mm['charged']:,.2f}</td>
                </tr>
                """)

            dep_rows = []
            for md in my_deposits_data:
                dep_rows.append(f"""
                <tr>
                    <td>{md['date']}</td>
                    <td style="color: var(--success); font-weight: 600;">+Rs. {md['amount']:,.2f}</td>
                    <td>{md['method']}</td>
                    <td>{md['status']}</td>
                    <td>{md['notes']}</td>
                </tr>
                """)

            content_parts.append(f"""
            <div class="card">
                <div class="card-header">
                    <h2>📖 My Personal Meals & Consumption Ledger</h2>
                    <span style="font-size: 0.85rem; color: var(--text-muted); font-style: italic;">
                        🔒 Private to {user['display_name']}
                    </span>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Meal Type</th>
                                <th>Dish / Description</th>
                                <th>My Charged Share</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(meal_rows) if meal_rows else '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No meals recorded for you yet.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>💵 My Payment & Deposit History</h2>
                </div>
                <div style="overflow-x: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Amount Deposited</th>
                                <th>Method</th>
                                <th>Verification Status</th>
                                <th>Note / Ref</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(dep_rows) if dep_rows else '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No deposits recorded yet.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <h2>🔒 Password & Account Settings</h2>
                </div>
                <p style="font-size: 0.9rem; color: var(--text-muted);">
                    Password resets are managed securely by <strong>Administrator Huzaifa</strong>. If you forgot or need to reset your password, please contact Huzaifa directly.
                </p>
            </div>
            """)

        # ==============================================================
        # 4. ADMIN ACTIONS (RECORD MEAL, RECORD DEPOSIT, EDIT MEMBER INFO, RESET PASSWORDS)
        # ==============================================================
        if is_admin:
            # Meal Form
            att_checkboxes = []
            for u in all_users_data:
                att_checkboxes.append(f"""
                <label class="att-label">
                    <input type="checkbox" name="attendee_{u['id']}" value="{u['id']}" checked>
                    <span>{u['display_name']}</span>
                </label>
                """)

            content_parts.append(f"""
            <div class="card">
                <div class="card-header">
                    <h2>🍽️ Record Meal Expense & Split with Attendees</h2>
                </div>
                <form method="POST" action="/api/add_meal">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Date</label>
                            <input type="date" name="date" value="{date.today()}" required>
                        </div>
                        <div class="form-group">
                            <label>Meal Type</label>
                            <select name="meal_type">
                                <option value="dinner" selected>Dinner</option>
                                <option value="lunch">Lunch</option>
                                <option value="breakfast">Breakfast</option>
                                <option value="custom">Custom</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Total Expense (PKR / Rs.)</label>
                            <input type="number" step="10" name="total_cost" placeholder="e.g. 2400" required>
                        </div>
                        <div class="form-group">
                            <label>Meal Dish / Title</label>
                            <input type="text" name="title" placeholder="e.g. Chicken Karahi & Naan" required>
                        </div>
                    </div>

                    <label style="font-size: 0.85rem; font-weight: 600; color: #334155; display: block; margin-bottom: 6px;">
                        Mark Present Attendees for this Meal:
                    </label>
                    <div class="attendance-grid">
                        {''.join(att_checkboxes)}
                    </div>

                    <button type="submit" class="btn btn-primary" style="width: 100%;">
                        💾 Save Meal & Charge Present Attendees Automatically
                    </button>
                </form>
            </div>
            """)

            # Deposit Form
            user_options = "".join([f'<option value="{u["id"]}">{u["display_name"]} ({u["username"]})</option>' for u in all_users_data])
            content_parts.append(f"""
            <div class="card">
                <div class="card-header">
                    <h2>💰 Record Advance Pool Deposit</h2>
                </div>
                <form method="POST" action="/api/add_deposit">
                    <div class="form-grid">
                        <div class="form-group">
                            <label>Member</label>
                            <select name="user_id">
                                {user_options}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Deposit Amount (PKR / Rs.)</label>
                            <input type="number" step="100" name="amount" placeholder="e.g. 3000" required>
                        </div>
                        <div class="form-group">
                            <label>Payment Method</label>
                            <select name="payment_method">
                                <option value="Cash">Cash</option>
                                <option value="EasyPaisa">EasyPaisa</option>
                                <option value="JazzCash">JazzCash</option>
                                <option value="NayaPay">NayaPay</option>
                                <option value="SadaPay">SadaPay</option>
                                <option value="Bank Transfer">Bank Transfer</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Reference / Note</label>
                            <input type="text" name="notes" placeholder="e.g. Paid in cash to Huzaifa">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">💾 Confirm Deposit</button>
                </form>
            </div>
            """)

            # EDIT ANY INFORMATION & RESET PASSWORD (ADMIN CONTROL PANEL)
            member_edit_options = "".join([f'<option value="{u["id"]}">{u["display_name"]} (@{u["username"]})</option>' for u in all_registered_data])
            content_parts.append(f"""
            <div class="card" style="border-top: 4px solid var(--primary-dark);">
                <div class="card-header">
                    <h2>⚙️ Admin Control Panel: Edit Member Information & Reset Passwords</h2>
                </div>
                <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 16px;">
                    As administrator, you can edit any member's details or reset their password if they forgot it:
                </p>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;">
                    <!-- Edit Member Info Form -->
                    <div style="padding: 16px; background: #f8fafc; border: 1px solid var(--border-color); border-radius: 8px;">
                        <h3 style="font-size: 1rem; margin-bottom: 12px; color: var(--text-dark);">✏️ Edit Member Profile</h3>
                        <form method="POST" action="/api/edit_member">
                            <div class="form-group" style="margin-bottom: 10px;">
                                <label>Select Roommate</label>
                                <select name="target_user_id" required>
                                    {member_edit_options}
                                </select>
                            </div>
                            <div class="form-group" style="margin-bottom: 10px;">
                                <label>New Full Name</label>
                                <input type="text" name="new_display_name" placeholder="Leave blank to keep unchanged">
                            </div>
                            <div class="form-group" style="margin-bottom: 10px;">
                                <label>New Phone Number</label>
                                <input type="text" name="new_phone" placeholder="Leave blank to keep unchanged">
                            </div>
                            <div class="form-group" style="margin-bottom: 14px;">
                                <label>Account Status</label>
                                <select name="new_status">
                                    <option value="keep">Keep Current Status</option>
                                    <option value="active">Active</option>
                                    <option value="inactive">Inactive</option>
                                </select>
                            </div>
                            <button type="submit" class="btn btn-secondary btn-sm" style="width: 100%;">Update Member Details</button>
                        </form>
                    </div>

                    <!-- Reset Password Form -->
                    <div style="padding: 16px; background: #f8fafc; border: 1px solid var(--border-color); border-radius: 8px;">
                        <h3 style="font-size: 1rem; margin-bottom: 12px; color: var(--text-dark);">🔑 Admin Password Reset</h3>
                        <form method="POST" action="/api/admin_reset_password">
                            <div class="form-group" style="margin-bottom: 10px;">
                                <label>Select Member</label>
                                <select name="target_user_id" required>
                                    {member_edit_options}
                                </select>
                            </div>
                            <div class="form-group" style="margin-bottom: 14px;">
                                <label>New Password (At least 6 characters)</label>
                                <input type="password" name="new_password" placeholder="Enter new password" required minlength="6">
                            </div>
                            <button type="submit" class="btn btn-primary btn-sm" style="width: 100%;">Set New Password</button>
                        </form>
                    </div>
                </div>
            </div>
            """)

        html = HTML_TEMPLATE.replace("{NAVBAR}", navbar).replace("{MESSAGE}", msg_html).replace("{CONTENT}", "".join(content_parts))
        self.send_html(html)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(post_data)

        # 1. Login endpoint
        if path == "/api/login":
            username = params.get("username", [""])[0].strip()
            password = params.get("password", [""])[0]
            with get_db() as session:
                user, err = authenticate_user(session, username, password)
                if user:
                    import secrets
                    token = secrets.token_hex(16)
                    SESSIONS[token] = {
                        "id": user.id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "role": user.role
                    }
                    self.send_redirect("/", set_cookie=f"messmate_session={token}; Path=/; HttpOnly")
                    return
                else:
                    self.send_redirect(f"/login?err={urllib.parse.quote(err or 'Invalid credentials')}")
                    return

        # 2. Public Self-Registration endpoint
        if path == "/api/register":
            username = params.get("username", [""])[0].strip()
            display_name = params.get("display_name", [""])[0].strip()
            phone = params.get("phone_number", [""])[0].strip()
            password = params.get("password", [""])[0]

            with get_db() as session:
                new_u, err = register_user(session, username, password, display_name, phone)
                if new_u:
                    msg = f"Thank you, {display_name}! Your registration was submitted. Please wait for Administrator Huzaifa to approve and activate your account."
                    self.send_redirect(f"/login?msg={urllib.parse.quote(msg)}")
                else:
                    self.send_redirect(f"/login?tab=signup&err={urllib.parse.quote(err or 'Registration failed')}")
            return

        # Protected endpoints require valid session
        user = self.get_current_user()
        if not user:
            self.send_redirect("/login")
            return

        # 3. Approve User Registration (Admin only)
        if path == "/api/approve_user":
            if user["role"] != "admin":
                self.send_redirect("/?err=Only admin can approve registrations.")
                return
            target_id = int(params.get("user_id", ["0"])[0])
            with get_db() as session:
                ok, msg = approve_user_registration(session, target_id, user["id"])
                if ok:
                    self.send_redirect(f"/?msg={urllib.parse.quote(msg)}")
                else:
                    self.send_redirect(f"/?err={urllib.parse.quote(msg)}")
            return

        # 4. Reject User Registration (Admin only)
        if path == "/api/reject_user":
            if user["role"] != "admin":
                self.send_redirect("/?err=Only admin can reject registrations.")
                return
            target_id = int(params.get("user_id", ["0"])[0])
            with get_db() as session:
                ok, msg = reject_user_registration(session, target_id, user["id"])
                if ok:
                    self.send_redirect(f"/?msg={urllib.parse.quote(msg)}")
                else:
                    self.send_redirect(f"/?err={urllib.parse.quote(msg)}")
            return

        # 5. Edit Member Information (Admin only)
        if path == "/api/edit_member":
            if user["role"] != "admin":
                self.send_redirect("/?err=Only admin can edit members.")
                return
            target_id = int(params.get("target_user_id", ["0"])[0])
            new_name = params.get("new_display_name", [""])[0].strip()
            new_phone = params.get("new_phone", [""])[0].strip()
            new_status = params.get("new_status", ["keep"])[0]

            with get_db() as session:
                target_u = session.query(User).filter(User.id == target_id).first()
                if not target_u:
                    self.send_redirect("/?err=User not found.")
                    return
                if new_name:
                    target_u.display_name = new_name
                if new_phone:
                    target_u.phone_number = new_phone
                if new_status == "active":
                    target_u.is_active = True
                elif new_status == "inactive":
                    target_u.is_active = False
                session.commit()
                self.send_redirect(f"/?msg=Updated details for {target_u.display_name}!")
            return

        # 6. Admin Password Reset (Admin only)
        if path == "/api/admin_reset_password":
            if user["role"] != "admin":
                self.send_redirect("/?err=Only admin can reset passwords.")
                return
            target_id = int(params.get("target_user_id", ["0"])[0])
            new_pass = params.get("new_password", [""])[0]
            with get_db() as session:
                target_u = session.query(User).filter(User.id == target_id).first()
                if not target_u:
                    self.send_redirect("/?err=User not found.")
                    return
                ok, msg = admin_reset_password(session, target_u, new_pass)
                if ok:
                    self.send_redirect(f"/?msg={urllib.parse.quote(msg)}")
                else:
                    self.send_redirect(f"/?err={urllib.parse.quote(msg)}")
            return

        # 7. Add Meal (Admin only)
        if path == "/api/add_meal":
            if user["role"] != "admin":
                self.send_redirect("/?err=Only admin can record meals.")
                return

            try:
                meal_date = datetime.strptime(params.get("date", [""])[0], "%Y-%m-%d").date()
                meal_type = params.get("meal_type", ["dinner"])[0]
                total_cost = Decimal(params.get("total_cost", ["0"])[0])
                title = params.get("title", [""])[0]

                present_ids = []
                for k in params:
                    if k.startswith("attendee_"):
                        present_ids.append(int(params[k][0]))

                if not present_ids:
                    self.send_redirect("/?err=At least one attendee must be present.")
                    return

                with get_db() as session:
                    meal, err = record_meal(
                        session=session,
                        meal_date=meal_date,
                        meal_type=meal_type,
                        total_cost=total_cost,
                        present_user_ids=present_ids,
                        title=title,
                        created_by_id=user["id"]
                    )
                    if meal:
                        msg = f"Recorded {meal_type.capitalize()} (Rs. {total_cost:,.2f}) split among {len(present_ids)} members (Rs. {meal.per_head_cost:,.2f} each)!"
                        self.send_redirect(f"/?msg={urllib.parse.quote(msg)}")
                    else:
                        self.send_redirect(f"/?err={urllib.parse.quote(err)}")
            except Exception as e:
                self.send_redirect(f"/?err={urllib.parse.quote(str(e))}")
            return

        # 8. Add Deposit (Admin only)
        if path == "/api/add_deposit":
            if user["role"] != "admin":
                self.send_redirect("/?err=Only admin can record deposits directly.")
                return

            try:
                target_user_id = int(params.get("user_id", ["0"])[0])
                amount = Decimal(params.get("amount", ["0"])[0])
                method = params.get("payment_method", ["Cash"])[0]
                notes = params.get("notes", [""])[0]

                with get_db() as session:
                    dep, err = record_deposit(
                        session=session,
                        user_id=target_user_id,
                        amount=amount,
                        payment_method=method,
                        notes=notes,
                        status="confirmed",
                        created_by_id=user["id"]
                    )
                    if dep:
                        msg = f"Recorded Rs. {amount:,.2f} deposit via {method}!"
                        self.send_redirect(f"/?msg={urllib.parse.quote(msg)}")
                    else:
                        self.send_redirect(f"/?err={urllib.parse.quote(err)}")
            except Exception as e:
                self.send_redirect(f"/?err={urllib.parse.quote(str(e))}")
            return

        self.send_redirect("/")


def run_web_server(port=8000):
    init_db()
    with get_db() as session:
        seed_initial_eight_members(session)
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, MessMateHandler)
    print(f"Janan Mess Web Server running at http://localhost:{port}")
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_web_server(port)
