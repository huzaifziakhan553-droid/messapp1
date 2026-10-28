from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text, Date, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from messmate.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="member")  # "admin" or "member"
    display_name = Column(String(100), nullable=False)
    phone_number = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    meal_attendances = relationship("MealAttendance", back_populates="user", cascade="all, delete-orphan")
    shared_attendances = relationship("SharedExpenseAttendee", back_populates="user", cascade="all, delete-orphan")
    deposits = relationship("Deposit", back_populates="user", foreign_keys="[Deposit.user_id]", cascade="all, delete-orphan")
    disputes = relationship("DisputeRequest", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.id}: {self.username} ({self.role})>"


class Meal(Base):
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    meal_type = Column(String(20), nullable=False)  # "breakfast", "lunch", "dinner", "custom"
    title = Column(String(100), nullable=True)  # e.g., "Chicken Biryani", "Daal Chawal"
    category = Column(String(50), nullable=False, default="Regular")  # "Chicken", "Beef", "Vegetable", "Daal", "Eggs", "Special"
    total_cost = Column(Numeric(10, 2, asdecimal=True), nullable=False)
    notes = Column(Text, nullable=True)
    is_reversed = Column(Boolean, default=False, nullable=False)
    reversal_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    attendances = relationship("MealAttendance", back_populates="meal", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_id])

    @property
    def attendee_count(self):
        return sum(1 for a in self.attendances if a.is_present)

    @property
    def per_head_cost(self):
        if self.is_reversed:
            return Decimal("0.00")
        count = self.attendee_count
        if count == 0:
            return Decimal("0.00")
        return (Decimal(str(self.total_cost)) / Decimal(str(count))).quantize(Decimal("0.01"))

    def __repr__(self):
        return f"<Meal {self.id}: {self.date} {self.meal_type} - Rs.{self.total_cost}>"


class MealAttendance(Base):
    __tablename__ = "meal_attendances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meal_id = Column(Integer, ForeignKey("meals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_present = Column(Boolean, default=True, nullable=False)
    charged_amount = Column(Numeric(10, 2, asdecimal=True), default=Decimal("0.00"), nullable=False)

    meal = relationship("Meal", back_populates="attendances")
    user = relationship("User", back_populates="meal_attendances")

    def __repr__(self):
        return f"<Attendance Meal:{self.meal_id} User:{self.user_id} Present:{self.is_present} Cost:{self.charged_amount}>"


class SharedExpense(Base):
    __tablename__ = "shared_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    title = Column(String(100), nullable=False)  # e.g., "Cook Monthly Salary", "Cooking Oil & Masala Stock", "Gas Cylinder Refill"
    category = Column(String(50), nullable=False, default="Kitchen Supplies")  # Cook, Spices/Oil, Gas, Water, Cleaning, Misc
    total_amount = Column(Numeric(10, 2, asdecimal=True), nullable=False)
    per_member_amount = Column(Numeric(10, 2, asdecimal=True), nullable=False)
    notes = Column(Text, nullable=True)
    is_reversed = Column(Boolean, default=False, nullable=False)
    reversal_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    attendees = relationship("SharedExpenseAttendee", back_populates="shared_expense", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<SharedExpense {self.id}: {self.title} - Rs.{self.total_amount}>"


class SharedExpenseAttendee(Base):
    __tablename__ = "shared_expense_attendees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shared_expense_id = Column(Integer, ForeignKey("shared_expenses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    charged_amount = Column(Numeric(10, 2, asdecimal=True), nullable=False)

    shared_expense = relationship("SharedExpense", back_populates="attendees")
    user = relationship("User", back_populates="shared_attendances")


class Deposit(Base):
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(10, 2, asdecimal=True), nullable=False)
    payment_method = Column(String(30), nullable=False, default="Cash")  # Cash, EasyPaisa, JazzCash, Nayapay, SadaPay, Bank Transfer
    reference_no = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="confirmed")  # "confirmed", "pending_approval", "rejected"
    is_reversed = Column(Boolean, default=False, nullable=False)
    reversal_reason = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User", back_populates="deposits", foreign_keys=[user_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Deposit {self.id}: User {self.user_id} - Rs.{self.amount} ({self.status})>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    action = Column(String(50), nullable=False)  # CREATE_MEAL, REVERSE_MEAL, UPDATE_ATTENDANCE, RECORD_DEPOSIT, REVERSE_DEPOSIT, etc.
    target_type = Column(String(30), nullable=False)  # Meal, Deposit, SharedExpense, User, Dispute
    target_id = Column(Integer, nullable=True)
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # Human readable or JSON details

    performed_by = relationship("User", foreign_keys=[performed_by_id])

    def __repr__(self):
        return f"<AuditLog {self.id}: {self.action} on {self.target_type}#{self.target_id}>"


class DisputeRequest(Base):
    __tablename__ = "dispute_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(50), nullable=False)  # "ATTENDANCE_CORRECTION", "PAYMENT_CONFIRMATION", "EXPENSE_QUERY", "OTHER"
    description = Column(Text, nullable=False)
    amount = Column(Numeric(10, 2, asdecimal=True), nullable=True)
    meal_id = Column(Integer, ForeignKey("meals.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False, default="PENDING")  # "PENDING", "APPROVED", "REJECTED"
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="disputes")
    meal = relationship("Meal", foreign_keys=[meal_id])

    def __repr__(self):
        return f"<DisputeRequest {self.id}: {self.request_type} by User {self.user_id} - {self.status}>"

