# 🍲 MessMate - Hostel Mess Management System

**MessMate** is a full-stack, centralized digital mess management and Khaata system built for university friends living together in a hostel and cooking their own meals.

It eliminates manual paper registers and messy calculations with an automated, penny-exact ledger that records daily meal attendance, shared groceries/utilities, advance member deposits, personal balances, and WhatsApp reports.

---

## 🌟 Key Features

### 1. 👥 Eight-Member Hostel Setup
- Pre-configured with the 8 hostel roommates: **Huzaifa, Friend 2, Friend 3, Friend 4, Friend 5, Friend 6, Friend 7, and Friend 8**.
- The mess administrator can rename any roommate (e.g. to their actual names like Ali, Hamza, etc.), add phone numbers, and deactivate members who temporarily leave while strictly preserving historical records.
- Unique internal user IDs, preventing duplicate usernames.

### 2. 🛡️ Role-Based Access Control (RBAC)
- **Administrator (Huzaifa):**
  - Full mess financial dashboard, total mess pool tracking, and cash-in-hand monitoring.
  - Record breakfast, lunch, dinner, or custom meals with individual attendance.
  - Record shared kitchen expenses (Cook salary, gas cylinder, spices/oil stock, water).
  - Record and verify cash/digital deposits (EasyPaisa, JazzCash, NayaPay, Bank).
  - Audit trail viewer, authorized transaction reversals, and attendance corrections with reasons.
  - WhatsApp daily report generator and spreadsheet CSV exports.
- **Roommate / Member (Friends 2–8):**
  - Secure personal dashboard showing real-time net balance (Credit / Dues), total deposits, and total consumption.
  - Complete history of attended meals, charges per meal, and payment history.
  - One-click payment proof submission (e.g., EasyPaisa TID) for admin approval.
  - Attendance dispute submission form (e.g., if marked present while away).
  - Profile & password management.

### 3. 🍽️ Precise Meal Attendance & Expense Splitting
- Separate attendance for every meal (Breakfast, Lunch, Dinner, Custom).
- Absent members are never charged for meals they did not attend.
- Exact penny/paisa division using Python's `Decimal` with remainder distribution to avoid floating-point loss:
  $$\sum \text{Member Charges} = \text{Total Meal Cost}$$
- Interactive attendance controls: "Select All", "Clear All", and live counters showing present/absent members and per-head cost before saving.

### 4. 🛒 Shared Kharcha Management
- Split general hostel supplies (Cook salary, gas cylinder refill, drinking water canisters, dishwashing soap, spices/cooking oil) equally across all or selected members.

### 5. 💰 Deposits & Advance Khaata Pool
- Record deposits via Cash, EasyPaisa, JazzCash, NayaPay, SadaPay, or Bank Transfer.
- Members can submit digital payment slips from their phones, which the admin verifies and approves with one click.
- Strict conservation law enforced:
  $$\text{Cash in Mess Pool} = \sum_{i=1}^{N} \text{Member Net Balances}$$

### 6. 📢 Shareable WhatsApp Reports
- Generates formatted WhatsApp messages using markdown asterisks, bold headers, and emojis:
  - Daily meal breakdown (Dish name, attendees, cost per head).
  - Shared expenses.
  - Member balance status: `🟢 Credit` vs `🔴 Dues Pending`.
- One-click share buttons using WhatsApp Web / WhatsApp Mobile API.
- Individual member WhatsApp statement link for private reminders.

### 7. 📑 Audit Trail & Corrections
- Every transaction modification, attendance correction, or reversal requires a reason and is permanently recorded in the `audit_logs` table.
- Safe transaction reversals zero out associated member charges and restore balances.

---

## 🛠️ Technology Stack

- **Backend:** Python 3, SQLAlchemy 2.0 ORM, Decimal financial math.
- **Frontend:** Streamlit with custom responsive CSS cards, status pills, and tables.
- **Database:** SQLite (default local) / PostgreSQL-ready connection string (`DATABASE_URL`).
- **Security:** NIST/OWASP approved PBKDF2-HMAC-SHA256 password hashing (600,000 iterations + unique salt) with brute-force rate-limiting.
- **Testing:** pytest test suite covering financial math, authentication, and integration workflows.

---

## 🚀 Getting Started (Windows Local Setup)

### 1. Prerequisites
Ensure Python 3.10+ is installed on your computer.

### 2. Install Dependencies
Open PowerShell or Command Prompt in the project folder and run:
```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` (optional; defaults work out-of-the-box):
```powershell
copy .env.example .env
```

## 🚀 How to Run the Application

MessMate provides three convenient interfaces sharing the exact same database and business models:

### 1. Zero-Dependency Web Application (Recommended for immediate local use)
Run the built-in responsive web server:
```powershell
python web_server.py
```
Open **`http://localhost:8000`** in any web browser on your laptop or phone!

### 2. Streamlit Web Dashboard
Launch the multi-tab Streamlit dashboard:
```powershell
streamlit run app.py
```
Opens automatically at **`http://localhost:8501`**.

### 3. Interactive Terminal CLI
For fast terminal-based entries and dashboard viewing:
```powershell
python cli.py
```

---

## 🔑 Default Accounts

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Admin** | `huzaifa` | `MessAdmin2026!` | Full administrator control |
| **Member** | `friend2` | `MessFriend123!` | Roommate account |
| **Member** | `friend3` | `MessFriend123!` | Roommate account |
| **Member** | `friend4` | `MessFriend123!` | Roommate account |
| **Member** | `friend5` | `MessFriend123!` | Roommate account |
| **Member** | `friend6` | `MessFriend123!` | Roommate account |
| **Member** | `friend7` | `MessFriend123!` | Roommate account |
| **Member** | `friend8` | `MessFriend123!` | Roommate account |

> 🔒 *Security Note: Change the admin and member passwords upon first deployment via the "My Profile" tab.*

---

## 🧪 Running Automated Tests

Run the full pytest suite:
```powershell
pytest -v
```

This tests:
1. `tests/test_finance.py`: Exact decimal division, remainder distribution, and balance conservation laws.
2. `tests/test_auth.py`: Password hashing, salt randomness, verification, and brute-force lockout.
3. `tests/test_workflow.py`: End-to-end integration of attendance, meals, shared expenses, corrections, and reversals.
4. `tests/test_whatsapp.py`: WhatsApp report generation and click-to-chat URL encoding.

---

## 🌐 Production Cloud Deployment Guide

When deploying MessMate so all 8 roommates can access it on their smartphones:

### Option A: Streamlit Community Cloud (Recommended & Free)
1. Push this repository to a private or public GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub account.
3. Select your repository, set the main file path to `app.py`, and deploy.
4. In "App Settings" -> "Secrets", set your custom production environment variables (e.g. `DEFAULT_ADMIN_PASSWORD`).

### Option B: Cloud VPS / Container with PostgreSQL
1. Provision a PostgreSQL database (e.g., Neon, Supabase, or AWS RDS).
2. Set `DATABASE_URL=postgresql+psycopg2://user:password@host:5432/messmate` in your `.env`.
3. Run behind Nginx with an SSL certificate (Let's Encrypt HTTPS) for end-to-end encryption.

