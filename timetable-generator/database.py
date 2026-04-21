from __future__ import annotations

import json
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), unique=True)
    profile_class_name = db.Column(db.String(64))
    profile_standard = db.Column(db.String(64))
    profile_section_code = db.Column(db.String(16))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    role = db.relationship("Role", lazy="joined")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def role_code(self) -> str:
        return str(self.role.code) if self.role else ""


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class FacultyProfile(db.Model):
    __tablename__ = "faculty_profiles"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(128), nullable=False)
    employee_code = db.Column(db.String(32), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    max_periods_per_day = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    department = db.relationship("Department", lazy="joined")


class RoomMaster(db.Model):
    __tablename__ = "rooms_master"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    room_type = db.Column(db.String(32), nullable=False, default="CLASSROOM")
    capacity = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class SectionMaster(db.Model):
    __tablename__ = "sections_master"
    __table_args__ = (
        UniqueConstraint("class_name", "standard", "section_code", name="uq_section_master"),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(64), nullable=False)
    standard = db.Column(db.String(64), nullable=False)
    section_code = db.Column(db.String(16), nullable=False)
    home_room = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class SubjectMaster(db.Model):
    __tablename__ = "subjects_master"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    name = db.Column(db.String(128), nullable=False)
    subject_type = db.Column(db.String(32), nullable=False, default="THEORY")
    default_weekly_periods = db.Column(db.Integer)
    default_daily_max = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class AssignmentMaster(db.Model):
    __tablename__ = "assignment_master"
    __table_args__ = (
        UniqueConstraint(
            "class_name",
            "standard",
            "section_code",
            "subject_name",
            "teacher_name",
            name="uq_assignment_master_row",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(64), nullable=False)
    standard = db.Column(db.String(64), nullable=False)
    section_code = db.Column(db.String(16), nullable=False)
    subject_name = db.Column(db.String(128), nullable=False)
    teacher_name = db.Column(db.String(128), nullable=False)
    lectures = db.Column(db.Integer, nullable=False)
    subject_type = db.Column(db.String(32), nullable=False, default="THEORY")
    allowed_rooms = db.Column(db.String(512))
    daily_max = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class FacultyAvailability(db.Model):
    __tablename__ = "faculty_availability"
    __table_args__ = (
        UniqueConstraint("faculty_name", "day_index", "period_number", name="uq_faculty_availability_slot"),
    )

    id = db.Column(db.Integer, primary_key=True)
    faculty_name = db.Column(db.String(128), nullable=False)
    day_index = db.Column(db.Integer, nullable=False)
    period_number = db.Column(db.Integer, nullable=False)
    is_available = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class FacultySchedulingPreference(db.Model):
    __tablename__ = "faculty_scheduling_preferences"
    __table_args__ = (
        UniqueConstraint("faculty_name", name="uq_faculty_scheduling_preference_faculty"),
    )

    id = db.Column(db.Integer, primary_key=True)
    faculty_name = db.Column(db.String(128), nullable=False)
    preferred_slots = db.Column(db.String(1024))
    avoid_slots = db.Column(db.String(1024))
    max_consecutive_classes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class FixedSlotConstraint(db.Model):
    __tablename__ = "fixed_slot_constraints"
    __table_args__ = (
        UniqueConstraint(
            "class_name",
            "standard",
            "section_code",
            "subject_name",
            "teacher_name",
            "day_index",
            "start_period",
            name="uq_fixed_slot_constraint",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(64), nullable=False)
    standard = db.Column(db.String(64), nullable=False)
    section_code = db.Column(db.String(16), nullable=False)
    subject_name = db.Column(db.String(128), nullable=False)
    teacher_name = db.Column(db.String(128), nullable=False)
    day_index = db.Column(db.Integer, nullable=False)
    start_period = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=1)
    room_code = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)


class TimetableVersion(db.Model):
    __tablename__ = "timetable_versions"

    id = db.Column(db.Integer, primary_key=True)
    version_label = db.Column(db.String(64), nullable=False, unique=True)
    status = db.Column(db.String(32), nullable=False, default="draft")
    optimization_score = db.Column(db.Float)
    summary_json = db.Column(db.Text, nullable=False, default="{}")
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    rejected_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    published_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approval_comment = db.Column(db.Text)
    rejection_comment = db.Column(db.Text)
    publish_comment = db.Column(db.Text)
    notification_summary = db.Column(db.Text)
    effective_from = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    approved_at = db.Column(db.DateTime(timezone=True))
    rejected_at = db.Column(db.DateTime(timezone=True))
    activated_at = db.Column(db.DateTime(timezone=True))
    published_at = db.Column(db.DateTime(timezone=True))

    created_by = db.relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id], lazy="joined")
    rejected_by = db.relationship("User", foreign_keys=[rejected_by_user_id], lazy="joined")
    published_by = db.relationship("User", foreign_keys=[published_by_user_id], lazy="joined")

    def summary(self) -> dict:
        try:
            return json.loads(self.summary_json)
        except json.JSONDecodeError:
            return {}


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor_role_code = db.Column(db.String(32), nullable=False)
    action = db.Column(db.String(128), nullable=False)
    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.String(64), nullable=False)
    details_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    actor = db.relationship("User", foreign_keys=[actor_user_id], lazy="joined")

    def details(self) -> dict:
        try:
            return json.loads(self.details_json)
        except json.JSONDecodeError:
            return {}


def ensure_seed_data(admin_username: str, admin_password: str, admin_full_name: str) -> None:
    role_map = {
        "ADMIN": "Administrator",
        "HOD": "Head of Department",
        "FACULTY": "Faculty",
        "STUDENT": "Student",
    }

    for role_code, role_name in role_map.items():
        existing = Role.query.filter_by(code=role_code).first()
        if existing is None:
            db.session.add(Role(code=role_code, name=role_name))

    db.session.commit()

    if User.query.count() > 0:
        return

    admin_role = Role.query.filter_by(code="ADMIN").first()
    if admin_role is None:
        return

    admin_user = User(
        username=admin_username,
        full_name=admin_full_name,
        role_id=admin_role.id,
        is_active=True,
    )
    admin_user.set_password(admin_password)
    db.session.add(admin_user)
    db.session.commit()