"""
MessMate Web Application Server
A zero-dependency, responsive web server using Python's standard library and SQLAlchemy.
Allows all 8 roommates to access the system immediately from any browser (laptop or mobile).
Shares the exact same database and business logic with `app.py` (Streamlit) and `cli.py`.
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
from messmate.seed import seed_initial_eight_members, seed_sample_demo_data
from messmate.models import User, Meal, Deposit, SharedExpense, DisputeRequest, AuditLog
from messmate.services.auth import authenticate_user, hash_password
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
    <title>MessMate - Hostel Mess Management System</title>
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
        }
        .navbar h1 { font-size: 1.4rem; display: flex; align-items: center; gap: 8px; }
        .nav-user { display: flex; align-items: center; gap: 12px; font-size: 0.9rem; }
        .nav-btn { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.4); color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 0.85rem; font-weight: 600; }
        .nav-btn:hover { background: rgba(255,255,255,0.3); }

        .container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }

        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .metric-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 18px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .metric-title { font-size: 0.78rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .metric-value { font-size: 1.7rem; font-weight: 700; color: var(--text-dark); }
        .metric-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }

        .card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 22px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 24px; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid var(--border-color); padding-bottom: 12px; }
        .card-header h2 { font-size: 1.2rem; color: var(--text-dark); display: flex; align-items: center; gap: 8px; }

        table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.92rem; }
        th { text-align: left; padding: 12px 14px; background: #f1f5f9; color: var(--text-muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border-color); }
        td { padding: 12px 14px; border-bottom: 1px solid var(--border-color); }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background-color: #f8fafc; }

        .badge-credit { background: var(--success-bg); color: var(--success); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }
        .badge-dues { background: var(--danger-bg); color: var(--danger); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }
        .badge-settled { background: #f1f5f9; color: var(--text-muted); padding: 4px 10px; border-radius: 9999px; font-weight: 700; font-size: 0.82rem; display: inline-block; }

        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 16px; }
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

        .attendance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 12px 0 18px 0; }
        .att-label { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: #f8fafc; border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 500; }
        .att-label input { width: 18px; height: 18px; accent-color: var(--primary); }

        .alert-success { background: #dcfce7; border: 1px solid #bbf7d0; color: #166534; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.92rem; }
        .alert-error { background: #fee2e2; border: 1px solid #fecaca; color: #991b1b; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.92rem; }
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

        # Route /login
        if path == "/login" or not user:
            self.render_login_page(msg_html)
            return

        # Route /logout
        if path == "/logout":
            self.send_redirect("/login", set_cookie="messmate_session=; Path=/; Max-Age=0")
            return

        # Route /export/...
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

        # Main Dashboard
        self.render_dashboard(user, msg_html)

    def render_login_page(self, msg_html):
        content = f"""
        <div style="max-width: 480px; margin: 40px auto;">
            <div class="card">
                <div class="card-header" style="justify-content: center;">
                    <h2>🍲 Sign In to MessMate</h2>
                </div>
                <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 20px; text-align: center;">
                    Hostel Mess Khaata System for Room 8 Friends
                </p>
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
                    <strong>💡 Demo Credentials:</strong>
                    <div style="margin-top: 6px;">• <strong>Admin:</strong> <code>huzaifa</code> / <code>MessAdmin2026!</code></div>
                    <div>• <strong>Roommates:</strong> <code>friend2</code> through <code>friend8</code> / <code>MessFriend123!</code></div>
                </div>
            </div>
        </div>
        """
        navbar = """
        <div class="navbar">
            <h1>🍲 MessMate</h1>
            <div class="nav-user">Hostel Mess System</div>
        </div>
        """
        html = HTML_TEMPLATE.replace("{NAVBAR}", navbar).replace("{MESSAGE}", msg_html).replace("{CONTENT}", content)
        self.send_html(html)

    def render_dashboard(self, user, msg_html):
        with get_db() as session:
            summary = get_mess_overall_summary(session)
            members = calculate_all_balances(session, include_inactive=False)
            my_bal = calculate_member_balance(session, user["id"])
            
            raw_meals = session.query(Meal).filter(Meal.date == date.today(), Meal.is_reversed == False).all()
            today_meals_data = []
            for tm in raw_meals:
                presents = [a.user.display_name for a in tm.attendances if a.is_present]
                today_meals_data.append({
                    "meal_type": tm.meal_type,
                    "title": tm.title,
                    "total_cost": tm.total_cost,
                    "per_head_cost": tm.per_head_cost,
                    "presents": presents
                })

            raw_users = session.query(User).filter(User.is_active == True).order_by(User.id).all()
            all_users_data = [{"id": u.id, "display_name": u.display_name, "username": u.username} for u in raw_users]
            wa_text = generate_daily_whatsapp_report(session, date.today())

        wa_url = get_whatsapp_share_url(wa_text)

        # Personal Balance Pill
        bal = my_bal["net_balance"]
        if bal > Decimal("0.00"):
            my_pill = f'<span class="badge-credit">🟢 My Balance: +Rs. {bal:,.2f}</span>'
        elif bal < Decimal("0.00"):
            my_pill = f'<span class="badge-dues">🔴 My Balance: -Rs. {abs(bal):,.2f}</span>'
        else:
            my_pill = '<span class="badge-settled">⚪ My Balance: Rs. 0.00</span>'

        navbar = f"""
        <div class="navbar">
            <h1>🍲 MessMate</h1>
            <div class="nav-user">
                <span>{my_pill}</span>
                <span>👤 <strong>{user['display_name']}</strong> ({user['role'].upper()})</span>
                <a href="/logout" class="nav-btn">Sign Out</a>
            </div>
        </div>
        """

        # Metrics cards
        metrics_html = f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">Mess Pool (Cash in Hand)</div>
                <div class="metric-value">Rs. {summary['cash_in_hand']:,.2f}</div>
                <div class="metric-sub">Net available mess fund</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Total Mess Expenses</div>
                <div class="metric-value">Rs. {summary['total_spent']:,.2f}</div>
                <div class="metric-sub">Meals + Shared items</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Total Outstanding Dues</div>
                <div class="metric-value" style="color: var(--danger);">Rs. {summary['total_dues']:,.2f}</div>
                <div class="metric-sub">Pending roommate dues</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Active Roommates</div>
                <div class="metric-value">{summary['active_member_count']} Friends</div>
                <div class="metric-sub">Accounting: {"✅ Balanced" if summary['is_balanced'] else "⚠️ Alert"}</div>
            </div>
        </div>
        """

        # Table of members
        member_rows = []
        for m in members:
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

        members_table_html = f"""
        <div class="card">
            <div class="card-header">
                <h2>👥 Roommate Khaata Accounts</h2>
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
        """

        # Record Meal Form (Admin)
        meal_form_html = ""
        if user["role"] == "admin":
            att_checkboxes = []
            for u in all_users_data:
                att_checkboxes.append(f"""
                <label class="att-label">
                    <input type="checkbox" name="attendee_{u['id']}" value="{u['id']}" checked>
                    <span>{u['display_name']}</span>
                </label>
                """)

            meal_form_html = f"""
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
            """

        # Deposit Form
        user_options = "".join([f'<option value="{u["id"]}">{u["display_name"]} ({u["username"]})</option>' for u in all_users_data])
        deposit_form_html = f"""
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
        """

        # Today's Meals List
        today_meals_html = ""
        if today_meals_data:
            tm_items = []
            for tm in today_meals_data:
                presents = tm["presents"]
                tm_items.append(f"""
                <div style="padding: 12px 14px; background: #f8fafc; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; font-weight: 600;">
                        <span>{tm['meal_type'].upper()}: {tm['title']}</span>
                        <span>Rs. {tm['total_cost']:,.2f}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
                        👥 {len(presents)} Present ({', '.join(presents)}) • 💵 Per Head: Rs. {tm['per_head_cost']:,.2f}
                    </div>
                </div>
                """)
            today_meals_html = f"""
            <div class="card">
                <div class="card-header">
                    <h2>🍽️ Today's Recorded Meals</h2>
                </div>
                {''.join(tm_items)}
            </div>
            """

        content = f"""
        {metrics_html}
        {members_table_html}
        {today_meals_html}
        {meal_form_html}
        {deposit_form_html}
        """

        html = HTML_TEMPLATE.replace("{NAVBAR}", navbar).replace("{MESSAGE}", msg_html).replace("{CONTENT}", content)
        self.send_html(html)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        params = urllib.parse.parse_qs(post_data)

        # Login endpoint
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

        user = self.get_current_user()
        if not user:
            self.send_redirect("/login")
            return

        # Add Meal endpoint
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

        # Add Deposit endpoint
        if path == "/api/add_deposit":
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
    print(f"MessMate Web Server running at http://localhost:{port}")
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_web_server(port)
