from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, text

from database import (
    AssignmentMaster,
    AuditLog,
    Department,
    FacultyAvailability,
    FacultyProfile,
    FacultySchedulingPreference,
    FixedSlotConstraint,
    Role,
    RoomMaster,
    SectionMaster,
    SubjectMaster,
    TimetableVersion,
    User,
    db,
    ensure_seed_data,
)

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

default_db_uri = f"sqlite:///{(INSTANCE_DIR / 'timetable.db').as_posix()}"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("TIMETABLE_DATABASE_URL", default_db_uri)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


LEGACY_COLUMN_MIGRATIONS = {
    "users": [
        ("must_change_password", "must_change_password BOOLEAN NOT NULL DEFAULT 0"),
        ("profile_class_name", "profile_class_name VARCHAR(64)"),
        ("profile_standard", "profile_standard VARCHAR(64)"),
        ("profile_section_code", "profile_section_code VARCHAR(16)"),
    ],
    "subjects_master": [
        ("default_weekly_periods", "default_weekly_periods INTEGER"),
        ("default_daily_max", "default_daily_max INTEGER"),
    ],
    "faculty_availability": [
        ("note", "note VARCHAR(255)"),
    ],
    "fixed_slot_constraints": [
        ("duration", "duration INTEGER NOT NULL DEFAULT 1"),
        ("room_code", "room_code VARCHAR(32)"),
    ],
    "assignment_master": [
        ("allowed_rooms", "allowed_rooms VARCHAR(512)"),
        ("daily_max", "daily_max INTEGER"),
    ],
    "timetable_versions": [
        ("rejected_by_user_id", "rejected_by_user_id INTEGER"),
        ("approval_comment", "approval_comment TEXT"),
        ("rejection_comment", "rejection_comment TEXT"),
        ("publish_comment", "publish_comment TEXT"),
        ("notification_summary", "notification_summary TEXT"),
        ("effective_from", "effective_from DATETIME"),
        ("rejected_at", "rejected_at DATETIME"),
        ("activated_at", "activated_at DATETIME"),
    ],
}


def ensure_legacy_columns() -> list[str]:
    inspector = inspect(db.engine)
    applied_steps: list[str] = []

    for table_name, columns in LEGACY_COLUMN_MIGRATIONS.items():
        if not inspector.has_table(table_name):
            continue

        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, column_sql in columns:
            if column_name in existing_columns:
                continue

            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
            applied_steps.append(f"Added column {table_name}.{column_name}")

    if applied_steps:
        db.session.commit()

    return applied_steps


def migrate() -> None:
    with app.app_context():
        # Import model symbols for table registration and create all missing tables.
        _ = (
            Role,
            User,
            Department,
            FacultyProfile,
            RoomMaster,
            SectionMaster,
            SubjectMaster,
            AssignmentMaster,
            FacultyAvailability,
            FacultySchedulingPreference,
            FixedSlotConstraint,
            TimetableVersion,
            AuditLog,
        )

        db.create_all()
        applied_steps = ensure_legacy_columns()

        ensure_seed_data(
            admin_username=os.environ.get("TIMETABLE_ADMIN_USERNAME", "admin"),
            admin_password=os.environ.get("TIMETABLE_ADMIN_PASSWORD", "admin123"),
            admin_full_name=os.environ.get("TIMETABLE_ADMIN_NAME", "System Admin"),
        )

        print("Database migration completed.")
        if applied_steps:
            print("Applied legacy schema updates:")
            for step in applied_steps:
                print(f"- {step}")
        else:
            print("No legacy schema updates were required.")


if __name__ == "__main__":
    migrate()
