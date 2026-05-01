from __future__ import annotations

import csv
import importlib
import io
import json
import math
import os
import random
import re
import smtplib
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from typing import Dict, List, Set, Tuple
from urllib.parse import urlparse

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from database import (
    AssignmentMaster,
    AuditLog,
    Department,
    FacultyProfile,
    Role,
    RoomMaster,
    SectionMaster,
    SubjectMaster,
    TimetableVersion,
    User,
    db,
    ensure_seed_data,
)
from timetable_generator import (
    DAY_NAMES,
    build_class_timetable_tables,
    build_faculty_timetable_tables,
    build_multi_timetable_summary,
    build_room_timetable_tables,
    build_section_key,
    export_class_timetable_to_csv,
    export_class_timetable_to_excel,
    export_class_timetable_to_json,
    export_faculty_timetable_to_csv,
    export_faculty_timetable_to_excel,
    export_faculty_timetable_to_json,
    export_multi_timetable_to_csv,
    export_multi_timetable_to_excel,
    export_multi_timetable_to_json,
    export_room_timetable_to_csv,
    export_room_timetable_to_excel,
    export_room_timetable_to_json,
    generate_multi_section_timetable,
    validate_multi_section_timetable,
)

REPORTLAB_AVAILABLE = False
REPORTLAB_MODULES: Dict[str, object] = {}
try:
    reportlab_colors = importlib.import_module("reportlab.lib.colors")
    reportlab_pagesizes = importlib.import_module("reportlab.lib.pagesizes")
    reportlab_styles = importlib.import_module("reportlab.lib.styles")
    reportlab_platypus = importlib.import_module("reportlab.platypus")

    REPORTLAB_MODULES = {
        "colors": reportlab_colors,
        "A4": reportlab_pagesizes.A4,
        "landscape": reportlab_pagesizes.landscape,
        "getSampleStyleSheet": reportlab_styles.getSampleStyleSheet,
        "PageBreak": reportlab_platypus.PageBreak,
        "Paragraph": reportlab_platypus.Paragraph,
        "SimpleDocTemplate": reportlab_platypus.SimpleDocTemplate,
        "Spacer": reportlab_platypus.Spacer,
        "Table": reportlab_platypus.Table,
        "TableStyle": reportlab_platypus.TableStyle,
    }
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False
    REPORTLAB_MODULES = {}

PILLOW_AVAILABLE = False
PILLOW_MODULES: Dict[str, object] = {}
try:
    pil_image = importlib.import_module("PIL.Image")
    pil_image_draw = importlib.import_module("PIL.ImageDraw")
    pil_image_font = importlib.import_module("PIL.ImageFont")
    PILLOW_MODULES = {
        "Image": pil_image,
        "ImageDraw": pil_image_draw,
        "ImageFont": pil_image_font,
    }
    PILLOW_AVAILABLE = True
except Exception:
    PILLOW_AVAILABLE = False
    PILLOW_MODULES = {}

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_XLSX_FILE = OUTPUT_DIR / "timetable.xlsx"
OUTPUT_CSV_FILE = OUTPUT_DIR / "timetable.csv"
OUTPUT_JSON_FILE = OUTPUT_DIR / "timetable.json"
OUTPUT_CLASS_XLSX_FILE = OUTPUT_DIR / "class_timetable.xlsx"
OUTPUT_CLASS_CSV_FILE = OUTPUT_DIR / "class_timetable.csv"
OUTPUT_CLASS_JSON_FILE = OUTPUT_DIR / "class_timetable.json"
OUTPUT_ROOM_XLSX_FILE = OUTPUT_DIR / "room_timetable.xlsx"
OUTPUT_ROOM_CSV_FILE = OUTPUT_DIR / "room_timetable.csv"
OUTPUT_ROOM_JSON_FILE = OUTPUT_DIR / "room_timetable.json"
OUTPUT_FACULTY_XLSX_FILE = OUTPUT_DIR / "faculty_timetable.xlsx"
OUTPUT_FACULTY_CSV_FILE = OUTPUT_DIR / "faculty_timetable.csv"
OUTPUT_FACULTY_JSON_FILE = OUTPUT_DIR / "faculty_timetable.json"

DEFAULT_PERIODS_PER_DAY = 8
MAX_PERIODS_PER_DAY = 10


def read_bool_env(var_name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def read_positive_int_env(var_name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.environ.get(var_name, str(default)).strip()
    try:
        parsed_value = int(raw_value)
    except ValueError:
        parsed_value = default
    return max(minimum, parsed_value)


MIN_PASSWORD_LENGTH = read_positive_int_env("TIMETABLE_MIN_PASSWORD_LENGTH", 10, minimum=8)
LOGIN_RATE_LIMIT_WINDOW_SECONDS = read_positive_int_env("TIMETABLE_LOGIN_WINDOW_SECONDS", 900, minimum=30)
LOGIN_RATE_LIMIT_MAX_FAILURES = read_positive_int_env("TIMETABLE_LOGIN_MAX_FAILURES", 5, minimum=2)
LOGIN_RATE_LIMIT_LOCK_SECONDS = read_positive_int_env("TIMETABLE_LOGIN_LOCK_SECONDS", 600, minimum=30)
MAX_CONTENT_LENGTH_MB = read_positive_int_env("TIMETABLE_MAX_CONTENT_LENGTH_MB", 10, minimum=1)
_LOGIN_RATE_LIMIT_BUCKETS: Dict[str, Dict[str, float]] = {}

INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

default_db_uri = f"sqlite:///{(INSTANCE_DIR / 'timetable.db').as_posix()}"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("TIMETABLE_SECRET_KEY", "timetable-demo-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("TIMETABLE_DATABASE_URL", default_db_uri)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = read_bool_env("TIMETABLE_COOKIE_SECURE", default=False)
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_SECURE"] = app.config["SESSION_COOKIE_SECURE"]
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_MB * 1024 * 1024
app.jinja_env.auto_reload = True

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id: str):
    try:
        parsed_id = int(user_id)
    except ValueError:
        return None
    return db.session.get(User, parsed_id)


with app.app_context():
    db.create_all()
    ensure_seed_data(
        admin_username=os.environ.get("TIMETABLE_ADMIN_USERNAME", "admin"),
        admin_password=os.environ.get("TIMETABLE_ADMIN_PASSWORD", "admin123"),
        admin_full_name=os.environ.get("TIMETABLE_ADMIN_NAME", "System Admin"),
    )


def get_current_role_code() -> str:
    if not current_user.is_authenticated:
        return ""
    role = getattr(current_user, "role", None)
    if role is None:
        return ""
    return str(role.code).upper()


def roles_required(*allowed_roles: str):
    normalized_roles = {role.upper() for role in allowed_roles}

    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped(*args, **kwargs):
            if get_current_role_code() in normalized_roles:
                return view_function(*args, **kwargs)

            flash("Access denied for your role.", "danger")
            return redirect(url_for("dashboard"))

        return wrapped

    return decorator


def get_client_ip_address() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return request.remote_addr or "unknown"


def get_login_rate_limit_keys(username: str) -> List[str]:
    client_ip = get_client_ip_address()
    normalized_username = username.strip().lower() or "_"
    return [
        f"ip:{client_ip}",
        f"ip-user:{client_ip}:{normalized_username}",
    ]


def prune_login_rate_limit_buckets(now_epoch: float) -> None:
    stale_before = now_epoch - max(LOGIN_RATE_LIMIT_WINDOW_SECONDS, LOGIN_RATE_LIMIT_LOCK_SECONDS) * 2
    stale_keys: List[str] = []
    for bucket_key, bucket_state in _LOGIN_RATE_LIMIT_BUCKETS.items():
        if bucket_state.get("last_seen", 0.0) < stale_before:
            stale_keys.append(bucket_key)

    for bucket_key in stale_keys:
        _LOGIN_RATE_LIMIT_BUCKETS.pop(bucket_key, None)


    except Exception as error:
        return False, str(error)

    return True, "Sent"


def format_effective_timestamp(value: datetime | None) -> str:
    room_stats = summary.get("room_stats", {})
    if isinstance(room_stats, dict):
        room_names.update(str(room_name) for room_name in room_stats.keys() if str(room_name).strip())

    for section_table in section_tables:
        if not isinstance(section_table, dict):
            continue
        timetable = section_table.get("timetable")
        if not isinstance(timetable, list):
            continue
        for day_row in timetable:
            if not isinstance(day_row, list):
                continue
            for cell in day_row:
                if isinstance(cell, dict):
                    room_name = str(cell.get("room", "")).strip()
                    if room_name:
                        room_names.add(room_name)

    class_tables = build_class_timetable_tables(section_tables)
    faculty_tables = build_faculty_timetable_tables(
        days,
        periods,
        section_tables,
        lunch_break_periods=lunch_break_periods_by_day,
    )
    room_tables = build_room_timetable_tables(
        days,
        periods,
        section_tables,
        room_names=sorted(room_names),
        lunch_break_periods=lunch_break_periods_by_day,
    )

    export_multi_timetable_to_excel(
        days,
        periods,
        section_tables,
        OUTPUT_XLSX_FILE,
        lunch_break_periods_by_day,
    )
    export_multi_timetable_to_csv(
        days,
        periods,
        section_tables,
        OUTPUT_CSV_FILE,
        lunch_break_periods_by_day,
    )
    export_multi_timetable_to_json(
        days,
        periods,
        section_tables,
        OUTPUT_JSON_FILE,
        lunch_break_periods_by_day,
        summary,
    )
    export_faculty_timetable_to_excel(
        days,
        periods,
        faculty_tables,
        OUTPUT_FACULTY_XLSX_FILE,
        lunch_break_periods_by_day,
    )
    export_faculty_timetable_to_csv(
        days,
        periods,
        faculty_tables,
        OUTPUT_FACULTY_CSV_FILE,
        lunch_break_periods_by_day,
    )
    export_faculty_timetable_to_json(
        days,
        periods,
        faculty_tables,
        OUTPUT_FACULTY_JSON_FILE,
        lunch_break_periods_by_day,
        summary,
    )
    export_class_timetable_to_excel(
        days,
        periods,
        class_tables,
        OUTPUT_CLASS_XLSX_FILE,
        lunch_break_periods_by_day,
    )
    export_class_timetable_to_csv(
        days,
        periods,
        class_tables,
        OUTPUT_CLASS_CSV_FILE,
        lunch_break_periods_by_day,
    )
    export_class_timetable_to_json(
        days,
        periods,
        class_tables,
        OUTPUT_CLASS_JSON_FILE,
        lunch_break_periods_by_day,
        summary,
    )
    export_room_timetable_to_excel(
        days,
        periods,
        room_tables,
        OUTPUT_ROOM_XLSX_FILE,
        lunch_break_periods_by_day,
    )
    export_room_timetable_to_csv(
        days,
        periods,
        room_tables,
        OUTPUT_ROOM_CSV_FILE,
        lunch_break_periods_by_day,
    )
    export_room_timetable_to_json(
        days,
        periods,
        room_tables,
        OUTPUT_ROOM_JSON_FILE,
        lunch_break_periods_by_day,
        summary,
    )
    return True, "Exported"


def activate_due_scheduled_versions() -> List[TimetableVersion]:
    now_utc = datetime.now(timezone.utc)
    due_versions = (
        TimetableVersion.query.filter(
            TimetableVersion.status == "scheduled",
            TimetableVersion.effective_from.isnot(None),
            TimetableVersion.effective_from <= now_utc,
        )
        .order_by(TimetableVersion.effective_from.asc(), TimetableVersion.id.asc())
        .all()
    )

    if not due_versions:
        return []

    activated_versions: List[TimetableVersion] = []
    for version in due_versions:
        TimetableVersion.query.filter_by(status="published").update({"status": "archived"})
        version.status = "published"
        version.published_at = now_utc
        version.activated_at = now_utc
        activated_versions.append(version)

    db.session.commit()

    for version in activated_versions:
        try:
            publish_version_outputs(version)
        except Exception:
            pass

        try:
            notify_users_for_version_event(version, "Activated")
            db.session.commit()
        except Exception:
            db.session.rollback()

        log_audit_event(
            action="VERSION_ACTIVATED",
            target_type="TIMETABLE_VERSION",
            target_id=str(version.id),
            details={
                "version_label": version.version_label,
                "effective_from": format_effective_timestamp(version.effective_from),
            },
        )

    db.session.commit()
    return activated_versions


@app.before_request
def auto_activate_scheduled_versions() -> None:
    if not current_user.is_authenticated:
        return
    if request.endpoint == "static":
        return
    activate_due_scheduled_versions()


def split_non_empty_lines(raw_text: str) -> List[str]:
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def parse_integer_field(
    value: str,
    label: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a number.") from error

    if parsed < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{label} must be at most {maximum}.")
    return parsed


def parse_positive_integer_or_none(value: str) -> int | None:
    cleaned = value.strip()
    if not cleaned:
        return None

    try:
        parsed = int(cleaned)
    except ValueError as error:
        raise ValueError("Value must be a whole number.") from error

    if parsed < 1:
        raise ValueError("Value must be greater than 0.")
    return parsed


def parse_checkbox_field(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def parse_lunch_break_periods(
    raw_text: str,
    periods_per_day: int,
    working_days: int,
) -> Dict[int, Set[int]]:
    lunch_by_day: Dict[int, Set[int]] = {day_index: set() for day_index in range(working_days)}

    if not raw_text.strip():
        return lunch_by_day

    tokens = [token.strip() for token in raw_text.replace(";", ",").split(",") if token.strip()]
    parsed_periods: List[int] = []
    for token in tokens:
        parsed_periods.append(parse_integer_field(token, "Lunch break period", 1, periods_per_day))

    if len(parsed_periods) == working_days:
        for day_index, period_number in enumerate(parsed_periods):
            lunch_by_day[day_index].add(period_number)
        return lunch_by_day

    shared_periods = set(parsed_periods)
    for day_index in range(working_days):
        lunch_by_day[day_index] = set(shared_periods)

    return lunch_by_day


def min_teaching_periods_per_day(
    periods_per_day: int,
    lunch_break_periods_by_day: Dict[int, Set[int]],
    working_days: int,
) -> int:
    if working_days <= 0:
        return periods_per_day

    return min(
        periods_per_day - len(lunch_break_periods_by_day.get(day_index, set()))
        for day_index in range(working_days)
    )


def format_lunch_break_description(
    days: List[str],
    lunch_break_periods_by_day: Dict[int, Set[int]],
) -> str:
    parts: List[str] = []
    for day_index, day_name in enumerate(days):
        day_periods = sorted(lunch_break_periods_by_day.get(day_index, set()))
        if not day_periods:
            continue
        parts.append(f"{day_name[:3]}:{'/'.join(str(period) for period in day_periods)}")

    if not parts:
        return "None"

    return ", ".join(parts)


def estimate_assignment_text_stats(assignments_text: str) -> Dict[str, int]:
    stats = {
        "row_count": 0,
        "section_count": 0,
        "teacher_count": 0,
        "lecture_total": 0,
        "lab_rows": 0,
        "lab_missing_allowed": 0,
        "lab_odd_lectures": 0,
    }

    section_keys: Set[str] = set()
    teacher_names: Set[str] = set()

    for line in split_non_empty_lines(assignments_text):
        stats["row_count"] += 1
        row = [value.strip() for value in next(csv.reader([line], skipinitialspace=True))]

        if len(row) < 6:
            continue

        class_name, standard, section = row[0], row[1], row[2]
        teacher_name = row[4]
        lecture_raw = row[5]
        assignment_type = row[6].upper() if len(row) >= 7 and row[6].strip() else "THEORY"
        allowed_rooms_raw = row[7] if len(row) >= 8 else ""

        if class_name and standard and section:
            section_keys.add(build_section_key(class_name, standard, section))

        if teacher_name:
            teacher_names.add(teacher_name)

        lecture_count = 0
        try:
            lecture_count = int(lecture_raw)
        except ValueError:
            lecture_count = 0

        if lecture_count > 0:
            stats["lecture_total"] += lecture_count

        is_lab = assignment_type in {"LAB", "PRACTICAL", "P", "LABORATORY"}
        if is_lab:
            stats["lab_rows"] += 1
            if not parse_allowed_rooms(allowed_rooms_raw):
                stats["lab_missing_allowed"] += 1
            if lecture_count > 0 and lecture_count % 2 != 0:
                stats["lab_odd_lectures"] += 1

    stats["section_count"] = len(section_keys)
    stats["teacher_count"] = len(teacher_names)
    return stats


def build_generation_failure_diagnostics(
    form_values: Dict[str, str],
    generation_scope_description: str,
) -> List[str]:
    diagnostics: List[str] = []

    assignment_source = form_values.get("assignment_source", "manual").strip().lower() or "manual"
    room_count = len(split_non_empty_lines(form_values.get("rooms", "")))
    assignment_stats = estimate_assignment_text_stats(form_values.get("assignments", ""))

    diagnostics.append(
        "Diagnostics: "
        f"Scope={generation_scope_description}; Source={assignment_source.upper()}; "
        f"Rooms={room_count}; AssignmentRows={assignment_stats['row_count']}; "
        f"Sections={assignment_stats['section_count']}; Faculty={assignment_stats['teacher_count']}; "
        f"Lectures={assignment_stats['lecture_total']}"
    )

    working_days = 0
    periods_per_day = 0
    teachable_per_day = 0
    try:
        working_days = parse_integer_field(form_values.get("working_days", "0"), "Working days", 1, 7)
        periods_per_day = parse_integer_field(form_values.get("periods_per_day", "0"), "Periods per day", 1, MAX_PERIODS_PER_DAY)
        lunch_breaks = parse_lunch_break_periods(
            form_values.get("lunch_break_periods", ""),
            periods_per_day,
            working_days,
        )
        teachable_per_day = min_teaching_periods_per_day(periods_per_day, lunch_breaks, working_days)
    except ValueError:
        teachable_per_day = 0

    if teachable_per_day > 0 and room_count > 0 and assignment_stats["section_count"] > 0:
        approximate_capacity = teachable_per_day * working_days * min(room_count, assignment_stats["section_count"])
        diagnostics.append(
            f"Capacity estimate: {approximate_capacity} lecture slots with current days/periods/lunch/rooms."
        )
        if assignment_stats["lecture_total"] > approximate_capacity:
            diagnostics.append(
                "Likely cause: total lectures exceed global capacity. Increase rooms/days/periods, reduce lunch breaks, or reduce lecture load."
            )

    if assignment_stats["lab_missing_allowed"] > 0:
        diagnostics.append(
            f"LAB issue: {assignment_stats['lab_missing_allowed']} LAB row(s) have empty allowed room list."
        )

    if assignment_stats["lab_odd_lectures"] > 0:
        diagnostics.append(
            f"LAB issue: {assignment_stats['lab_odd_lectures']} LAB row(s) have odd lecture counts; LAB requires even counts."
        )

    if assignment_source == "master":
        try:
            if AssignmentMaster.query.count() == 0:
                diagnostics.append(
                    "Master data issue: Assignment Master is empty. Add rows in Assignment Master or switch source to Manual."
                )
        except Exception:
            pass

    if room_count == 0:
        diagnostics.append("Input issue: room list is empty.")

    if assignment_source == "manual" and assignment_stats["row_count"] == 0:
        diagnostics.append("Input issue: manual assignment rows are empty.")

    return diagnostics


def build_generation_fix_suggestions(
    form_values: Dict[str, str],
    generation_scope_description: str,
) -> List[str]:
    _ = generation_scope_description
    suggestions: List[str] = []
    assignment_source = form_values.get("assignment_source", "manual").strip().lower() or "manual"
    assignment_stats = estimate_assignment_text_stats(form_values.get("assignments", ""))
    room_count = len(split_non_empty_lines(form_values.get("rooms", "")))

    working_days = 0
    periods_per_day = 0
    teachable_per_day = 0
    try:
        working_days = parse_integer_field(form_values.get("working_days", "0"), "Working days", 1, 7)
        periods_per_day = parse_integer_field(
            form_values.get("periods_per_day", "0"),
            "Periods per day",
            1,
            MAX_PERIODS_PER_DAY,
        )
        lunch_breaks = parse_lunch_break_periods(
            form_values.get("lunch_break_periods", ""),
            periods_per_day,
            working_days,
        )
        teachable_per_day = min_teaching_periods_per_day(periods_per_day, lunch_breaks, working_days)
    except ValueError:
        teachable_per_day = 0

    if room_count == 0:
        suggestions.append("Fix suggestion: add at least one room in Rooms before generating.")

    if assignment_source == "manual" and assignment_stats["row_count"] == 0:
        suggestions.append(
            "Fix suggestion: add assignment rows or click Load Starter Dataset for a one-click valid sample."
        )

    if assignment_stats["lab_missing_allowed"] > 0:
        suggestions.append(
            "Fix suggestion: add AllowedRooms to every LAB row (for example LAB-01|LAB-02|LAB-03)."
        )

    if assignment_stats["lab_odd_lectures"] > 0:
        suggestions.append("Fix suggestion: keep LAB lectures even (2, 4, 6, ...).")

    if (
        teachable_per_day > 0
        and working_days > 0
        and room_count > 0
        and assignment_stats["section_count"] > 0
    ):
        capacity = teachable_per_day * working_days * min(room_count, assignment_stats["section_count"])
        if assignment_stats["lecture_total"] > capacity:
            suggestions.append(
                "Fix suggestion: capacity is low. Increase rooms/days/periods or reduce lecture totals."
            )

    scenario_runs_raw = form_values.get("scenario_runs", "1").strip() or "1"
    try:
        scenario_runs = max(1, int(scenario_runs_raw))
    except ValueError:
        scenario_runs = 1
    if scenario_runs == 1:
        suggestions.append(
            "Fix suggestion: set Scenario Runs > 1 to auto-compare multiple runs and pick the best timetable."
        )

    if not suggestions:
        suggestions.append(
            "Fix suggestion: click Load Starter Dataset to verify pipeline health, then re-apply your data incrementally."
        )

    deduped: List[str] = []
    seen: Set[str] = set()
    for suggestion in suggestions:
        if suggestion in seen:
            continue
        seen.add(suggestion)
        deduped.append(suggestion)
    return deduped


def parse_allowed_rooms(raw_text: str) -> List[str]:
    normalized = raw_text.replace(";", "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def parse_section_group(section_text: str) -> Tuple[str, int | None]:
    cleaned = section_text.strip()
    upper_cleaned = cleaned.upper()
    marker = "-G"
    marker_index = upper_cleaned.rfind(marker)
    if marker_index <= 0:
        return cleaned, None

    suffix = upper_cleaned[marker_index + len(marker):]
    if suffix in {"1", "2", "3"}:
        return cleaned[:marker_index].strip(), int(suffix)

    return cleaned, None


def serialize_assignment_master_row(row: AssignmentMaster) -> str:
    return ",".join(
        [
            row.class_name,
            row.standard,
            row.section_code,
            row.subject_name,
            row.teacher_name,
            str(row.lectures),
            row.subject_type or "THEORY",
            row.allowed_rooms or "",
            str(row.daily_max) if row.daily_max is not None else "",
        ]
    )


def build_assignments_text_from_master() -> Tuple[str, int]:
    assignment_rows = AssignmentMaster.query.order_by(
        AssignmentMaster.class_name.asc(),
        AssignmentMaster.standard.asc(),
        AssignmentMaster.section_code.asc(),
        AssignmentMaster.subject_name.asc(),
        AssignmentMaster.teacher_name.asc(),
    ).all()
    lines = [serialize_assignment_master_row(row) for row in assignment_rows]
    return "\n".join(lines), len(lines)


def resolve_assignment_payload(assignments_text: str, assignment_source: str) -> Tuple[List[Dict[str, object]], str, str]:
    normalized_source = assignment_source.strip().lower()
    if normalized_source not in {"manual", "master"}:
        normalized_source = "manual"

    if normalized_source == "master":
        assignments_text, assignment_count = build_assignments_text_from_master()
        if assignment_count == 0:
            raise ValueError(
                "Assignment master is empty. Add rows in Admin > Assignment Master, or switch assignment source to Manual."
            )

    assignment_payload = build_assignment_payload(assignments_text)
    return assignment_payload, assignments_text, normalized_source


def load_default_form_values() -> Dict[str, str]:
    defaults = {
        "working_days": "5",
        "periods_per_day": str(DEFAULT_PERIODS_PER_DAY),
        "lunch_break_periods": "5",
        "faculty_daily_max_periods": "6",
        "faculty_daily_free_period": "1",
        "lab_same_day_subject_threshold": "3",
        "scenario_runs": "1",
        "rooms": "",
        "assignments": "",
        "section_classrooms": "",
        "faculty_daily_limits": "",
        "assignment_source": "manual",
        "assignment_master_count": "0",
    }

    rooms_file = DATA_DIR / "rooms.csv"
    assignments_file = DATA_DIR / "assignments.csv"
    section_classrooms_file = DATA_DIR / "section_classrooms.csv"
    faculty_limits_file = DATA_DIR / "faculty_daily_limits.csv"

    if rooms_file.exists():
        with rooms_file.open("r", encoding="utf-8", newline="") as room_stream:
            reader = csv.DictReader(room_stream)
            rooms = [str(row.get("room", "")).strip() for row in reader if str(row.get("room", "")).strip()]
        defaults["rooms"] = "\n".join(rooms)

    if assignments_file.exists():
        lines: List[str] = []
        with assignments_file.open("r", encoding="utf-8", newline="") as assignment_stream:
            reader = csv.DictReader(assignment_stream)
            for row in reader:
                class_name = str(row.get("class_name", "")).strip()
                standard = str(row.get("standard", "")).strip()
                section = str(row.get("section", "")).strip()
                subject = str(row.get("subject", "")).strip()
                teacher = str(row.get("teacher", "")).strip()
                lectures = str(row.get("lectures", "")).strip()
                assignment_type = str(row.get("type", "THEORY")).strip() or "THEORY"
                allowed_rooms = str(row.get("allowed_rooms", "")).strip()
                daily_max = str(row.get("daily_max", "")).strip()
                if all([class_name, standard, section, subject, teacher, lectures]):
                    lines.append(
                        f"{class_name},{standard},{section},{subject},{teacher},{lectures},{assignment_type},{allowed_rooms},{daily_max}"
                    )

        defaults["assignments"] = "\n".join(lines)

    if section_classrooms_file.exists():
        lines = []
        with section_classrooms_file.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                class_name = str(row.get("class_name", "")).strip()
                standard = str(row.get("standard", "")).strip()
                section = str(row.get("section", "")).strip()
                home_room = str(row.get("home_room", "")).strip()
                if all([class_name, standard, section, home_room]):
                    lines.append(f"{class_name},{standard},{section},{home_room}")
        defaults["section_classrooms"] = "\n".join(lines)

    if faculty_limits_file.exists():
        lines = []
        with faculty_limits_file.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for row in reader:
                teacher = str(row.get("teacher", "")).strip()
                max_periods = str(row.get("max_periods_per_day", "")).strip()
                if teacher and max_periods:
                    lines.append(f"{teacher},{max_periods}")
        defaults["faculty_daily_limits"] = "\n".join(lines)

    master_assignments_text, master_assignment_count = build_assignments_text_from_master()
    if master_assignment_count > 0:
        defaults["assignment_source"] = "master"
        defaults["assignments"] = master_assignments_text
        defaults["assignment_master_count"] = str(master_assignment_count)

    return defaults


def build_benchmark_lunch_pattern(working_days: int, periods_per_day: int) -> str:
    values: List[str] = []
    for day_index in range(max(1, working_days)):
        if periods_per_day >= 6:
            lunch_period = 5 if day_index % 2 == 0 else 6
        else:
            lunch_period = min(5, max(1, periods_per_day))
        values.append(str(lunch_period))
    return ",".join(values)


def build_large_demo_sample_form_values() -> Dict[str, str]:
    sample_values = load_default_form_values()

    working_days = 6
    periods_per_day = 10
    faculty_daily_max_periods = 6
    lab_same_day_subject_threshold = 3

    class_definitions = [
        (f"Class-{class_number:02d}", f"Year-{((class_number - 1) % 4) + 1}")
        for class_number in range(1, 7)
    ]
    section_codes = ["A", "B", "C", "D"]

    theory_subjects = [
        "Mathematics",
        "Programming Fundamentals",
        "Data Structures",
        "Database Systems",
        "Operating Systems",
    ]
    theory_subject_codes = {
        "Mathematics": "MATH",
        "Programming Fundamentals": "PROG",
        "Data Structures": "DSTR",
        "Database Systems": "DBMS",
        "Operating Systems": "OSYS",
    }
    lab_subjects = [
        ("Programming Lab", "LAB-01|LAB-02|LAB-03"),
        ("Electronics Lab", "LAB-04|LAB-05|LAB-06"),
        ("Data Analytics Lab", "LAB-07|LAB-08|LAB-09"),
    ]
    lab_subject_codes = {
        "Programming Lab": "PLAB",
        "Electronics Lab": "ELAB",
        "Data Analytics Lab": "DLAB",
    }

    room_lines = [f"CR-{room_number:03d}" for room_number in range(101, 125)]
    room_lines.extend([f"LAB-{room_number:02d}" for room_number in range(1, 13)])

    def make_faculty_name(prefix: str, index: int) -> str:
        return f"{prefix}-{index:02d}"

    theory_faculty_map: Dict[Tuple[str, str], List[str]] = {}
    lab_faculty_map: Dict[str, List[str]] = {}

    for year_number in range(1, 5):
        year_key = f"Year-{year_number}"
        for subject_name in theory_subjects:
            faculty_pool = [make_faculty_name(f"Y{year_number}-{theory_subject_codes[subject_name]}", index) for index in range(1, 5)]
            theory_faculty_map[(year_key, subject_name)] = faculty_pool

    for subject_name, _ in lab_subjects:
        prefix = lab_subject_codes[subject_name]
        lab_faculty_map[subject_name] = [make_faculty_name(f"LAB-{prefix}", index) for index in range(1, 5)]

    assignment_lines: List[str] = []
    section_home_room_lines: List[str] = []
    faculty_names_used: Set[str] = set()

    classroom_number = 101
    for class_index, (class_name, standard) in enumerate(class_definitions):
        for section_index, section_code in enumerate(section_codes):
            home_room = f"CR-{classroom_number:03d}"
            classroom_number += 1
            section_home_room_lines.append(f"{class_name},{standard},{section_code},{home_room}")

            for subject_index, subject_name in enumerate(theory_subjects):
                teacher_pool = theory_faculty_map[(standard, subject_name)]
                teacher_name = teacher_pool[(class_index + section_index + subject_index) % len(teacher_pool)]
                faculty_names_used.add(teacher_name)
                assignment_lines.append(
                    f"{class_name},{standard},{section_code},{subject_name},{teacher_name},4,THEORY,,2"
                )

            for subject_index, (subject_name, allowed_rooms) in enumerate(lab_subjects):
                teacher_pool = lab_faculty_map[subject_name]
                teacher_name = teacher_pool[(class_index + section_index + subject_index) % len(teacher_pool)]
                faculty_names_used.add(teacher_name)
                assignment_lines.append(
                    f"{class_name},{standard},{section_code},{subject_name},{teacher_name},2,LAB,{allowed_rooms},2"
                )

    sample_values["working_days"] = str(working_days)
    sample_values["periods_per_day"] = str(periods_per_day)
    sample_values["lunch_break_periods"] = build_benchmark_lunch_pattern(working_days, periods_per_day)
    sample_values["faculty_daily_max_periods"] = str(faculty_daily_max_periods)
    sample_values["faculty_daily_free_period"] = "1"
    sample_values["lab_same_day_subject_threshold"] = str(lab_same_day_subject_threshold)
    sample_values["scenario_runs"] = "3"
    sample_values["rooms"] = "\n".join(room_lines)
    sample_values["assignments"] = "\n".join(assignment_lines)
    sample_values["section_classrooms"] = "\n".join(section_home_room_lines)
    sample_values["faculty_daily_limits"] = "\n".join(f"{teacher_name},6" for teacher_name in sorted(faculty_names_used))
    sample_values["assignment_source"] = "manual"
    sample_values["assignment_master_count"] = str(AssignmentMaster.query.count())

    return sample_values


def build_assignment_payload(assignments_text: str) -> List[Dict[str, object]]:
    lines = split_non_empty_lines(assignments_text)
    if not lines:
        raise ValueError(
            "Provide at least one assignment row in format: "
            "Class,Standard,Section,Subject,Teacher,Lectures[,Type[,AllowedRooms[,DailyMax]]]"
        )

    reader = csv.reader(lines, skipinitialspace=True)
    payload: List[Dict[str, object]] = []
    lab_sessions_by_section: Dict[str, int] = {}
    lab_teachers_by_section: Dict[str, Set[str]] = {}
    lab_allowed_rooms_by_section: Dict[str, Set[str]] = {}
    lab_subjects_by_section: Dict[str, Set[str]] = {}

    for index, row in enumerate(reader, start=1):
        if len(row) not in (6, 7, 8, 9):
            raise ValueError(
                f"Assignment line {index} must contain 6 to 9 comma-separated values: "
                "Class,Standard,Section,Subject,Teacher,Lectures[,Type[,AllowedRooms[,DailyMax]]]."
            )

        class_name, standard, section, subject, teacher, lecture_raw = [item.strip() for item in row[:6]]
        assignment_type_raw = row[6].strip() if len(row) >= 7 else "THEORY"
        allowed_rooms_raw = row[7].strip() if len(row) >= 8 else ""
        daily_max_raw = row[8].strip() if len(row) == 9 else ""

        if not all([class_name, standard, section, subject, teacher, lecture_raw]):
            raise ValueError(f"Assignment line {index} has empty required values.")

        lecture_count = parse_integer_field(
            lecture_raw,
            f"Lecture count on assignment line {index}",
            minimum=1,
        )

        assignment_type = assignment_type_raw.upper() if assignment_type_raw else "THEORY"
        is_lab = assignment_type in {"LAB", "PRACTICAL", "P", "LABORATORY"}
        allowed_rooms = parse_allowed_rooms(allowed_rooms_raw)
        base_section, explicit_group = parse_section_group(section)

        if is_lab and explicit_group is not None:
            raise ValueError(
                f"Assignment line {index} uses grouped section '{section}' for LAB. "
                "Enter LAB rows on the base section (for example A) and let the generator auto-split into G1/G2/G3."
            )

        if is_lab and not allowed_rooms:
            raise ValueError(
                f"Assignment line {index} is LAB but has no allowed lab rooms. "
                "Provide AllowedRooms like Lab-1|Lab-2."
            )

        if is_lab and lecture_count % 2 != 0:
            raise ValueError(
                f"Assignment line {index} is LAB and must have even lecture count for double-period contiguous labs."
            )

        subject_daily_max: int | None = None
        if daily_max_raw:
            subject_daily_max = parse_integer_field(
                daily_max_raw,
                f"Daily max on assignment line {index}",
                minimum=1,
            )
            if is_lab and subject_daily_max < 2:
                raise ValueError(
                    f"Assignment line {index} is LAB and daily max must be at least 2."
                )

        if is_lab:
            section_key = build_section_key(class_name, standard, base_section)
            lab_sessions_by_section[section_key] = lab_sessions_by_section.get(section_key, 0) + (lecture_count // 2)
            lab_teachers_by_section.setdefault(section_key, set()).add(teacher)
            lab_allowed_rooms_by_section.setdefault(section_key, set()).update(allowed_rooms)
            lab_subjects_by_section.setdefault(section_key, set()).add(subject)

        payload.append(
            {
                "class_name": class_name,
                "standard": standard,
                "section": section,
                "subject": subject,
                "teacher": teacher,
                "lectures": lecture_count,
                "is_lab": is_lab,
                "allowed_rooms": allowed_rooms,
                "subject_daily_max": subject_daily_max,
            }
        )

    for section_key in sorted(lab_sessions_by_section.keys()):
        lab_subject_count = len(lab_subjects_by_section.get(section_key, set()))
        required_distinct_count = max(1, min(3, lab_subject_count))
        distinct_teacher_count = len(lab_teachers_by_section.get(section_key, set()))
        if distinct_teacher_count < required_distinct_count:
            raise ValueError(
                f"{section_key} has only {distinct_teacher_count} distinct LAB faculty. "
                f"Provide at least {required_distinct_count} distinct faculty for LAB synchronization without faculty conflicts."
            )

        distinct_room_count = len(lab_allowed_rooms_by_section.get(section_key, set()))
        if distinct_room_count < required_distinct_count:
            raise ValueError(
                f"{section_key} has only {distinct_room_count} distinct allowed LAB rooms. "
                f"Provide at least {required_distinct_count} allowed LAB rooms so synchronized LAB groups can be assigned different rooms in the same slot."
            )

    return payload


def parse_section_classrooms(
    section_classrooms_text: str,
    rooms: List[str],
) -> Dict[str, str]:
    lines = split_non_empty_lines(section_classrooms_text)
    if not lines:
        return {}

    room_set = set(rooms)
    mapping: Dict[str, str] = {}

    for index, line in enumerate(lines, start=1):
        row = [value.strip() for value in next(csv.reader([line], skipinitialspace=True))]
        if len(row) != 4:
            raise ValueError(
                f"Section classroom line {index} must be: Class,Standard,Section,HomeRoom"
            )

        class_name, standard, section, home_room = row
        if not all([class_name, standard, section, home_room]):
            raise ValueError(f"Section classroom line {index} has empty values.")

        if home_room not in room_set:
            raise ValueError(
                f"Section classroom line {index} references room '{home_room}' which is not in room list."
            )

        section_key = build_section_key(class_name, standard, section)
        if section_key in mapping and mapping[section_key] != home_room:
            raise ValueError(
                f"Section {section_key} has conflicting home rooms in section classroom mapping."
            )
        mapping[section_key] = home_room

    return mapping


def parse_faculty_daily_limits(
    faculty_daily_limits_text: str,
    max_teaching_periods_per_day: int,
) -> Dict[str, int]:
    lines = split_non_empty_lines(faculty_daily_limits_text)
    if not lines:
        return {}

    limits: Dict[str, int] = {}
    for index, line in enumerate(lines, start=1):
        row = [value.strip() for value in next(csv.reader([line], skipinitialspace=True))]
        if len(row) != 2:
            raise ValueError(
                f"Faculty daily limit line {index} must be: FacultyName,MaxPeriodsPerDay"
            )

        teacher, max_periods_raw = row
        if not teacher:
            raise ValueError(f"Faculty daily limit line {index} has empty faculty name.")

        max_periods = parse_integer_field(
            max_periods_raw,
            f"Max periods on faculty limit line {index}",
            1,
            max_teaching_periods_per_day,
        )

        limits[teacher] = max_periods

    return limits


def validate_lab_allowed_rooms_against_rooms(
    assignment_payload: List[Dict[str, object]],
    rooms: List[str],
) -> None:
    room_set = {room.strip() for room in rooms if room.strip()}
    missing_rows: List[str] = []

    for assignment in assignment_payload:
        if not bool(assignment.get("is_lab", False)):
            continue

        allowed_rooms = [str(room).strip() for room in assignment.get("allowed_rooms", []) if str(room).strip()]
        if not allowed_rooms:
            continue

        if any(room_name in room_set for room_name in allowed_rooms):
            continue

        missing_rows.append(
            f"{assignment.get('class_name', '')},{assignment.get('standard', '')},{assignment.get('section', '')},{assignment.get('subject', '')}"
        )

    if missing_rows:
        preview = "; ".join(missing_rows[:3])
        raise ValueError(
            "LAB room mismatch: some LAB rows use AllowedRooms not present in Rooms list. "
            f"Examples: {preview}. Add matching LAB-* rooms to Rooms, or update AllowedRooms."
        )


def write_generated_output_files(
    days: List[str],
    periods: List[str],
    section_tables: List[Dict[str, object]],
    class_tables: List[Dict[str, object]],
    faculty_tables: List[Dict[str, object]],
    room_tables: List[Dict[str, object]],
    summary: Dict[str, object],
    lunch_break_periods_by_day: Dict[int, Set[int]],
) -> List[str]:
    locked_files: List[str] = []
    for exporter, positional_args, keyword_args, filename in (
        (
            export_multi_timetable_to_excel,
            (days, periods, section_tables, OUTPUT_XLSX_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_XLSX_FILE.name,
        ),
        (
            export_multi_timetable_to_csv,
            (days, periods, section_tables, OUTPUT_CSV_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_CSV_FILE.name,
        ),
        (
            export_multi_timetable_to_json,
            (days, periods, section_tables, OUTPUT_JSON_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day, "summary": summary},
            OUTPUT_JSON_FILE.name,
        ),
        (
            export_faculty_timetable_to_excel,
            (days, periods, faculty_tables, OUTPUT_FACULTY_XLSX_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_FACULTY_XLSX_FILE.name,
        ),
        (
            export_class_timetable_to_excel,
            (days, periods, class_tables, OUTPUT_CLASS_XLSX_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_CLASS_XLSX_FILE.name,
        ),
        (
            export_room_timetable_to_excel,
            (days, periods, room_tables, OUTPUT_ROOM_XLSX_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_ROOM_XLSX_FILE.name,
        ),
        (
            export_faculty_timetable_to_csv,
            (days, periods, faculty_tables, OUTPUT_FACULTY_CSV_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_FACULTY_CSV_FILE.name,
        ),
        (
            export_class_timetable_to_csv,
            (days, periods, class_tables, OUTPUT_CLASS_CSV_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_CLASS_CSV_FILE.name,
        ),
        (
            export_room_timetable_to_csv,
            (days, periods, room_tables, OUTPUT_ROOM_CSV_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day},
            OUTPUT_ROOM_CSV_FILE.name,
        ),
        (
            export_faculty_timetable_to_json,
            (days, periods, faculty_tables, OUTPUT_FACULTY_JSON_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day, "summary": summary},
            OUTPUT_FACULTY_JSON_FILE.name,
        ),
        (
            export_class_timetable_to_json,
            (days, periods, class_tables, OUTPUT_CLASS_JSON_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day, "summary": summary},
            OUTPUT_CLASS_JSON_FILE.name,
        ),
        (
            export_room_timetable_to_json,
            (days, periods, room_tables, OUTPUT_ROOM_JSON_FILE),
            {"lunch_break_periods": lunch_break_periods_by_day, "summary": summary},
            OUTPUT_ROOM_JSON_FILE.name,
        ),
    ):
        try:
            exporter(*positional_args, **keyword_args)
        except OSError:
            locked_files.append(filename)

    if locked_files:
        return [
            f"Could not save output file(s): {', '.join(locked_files)}. "
            "Close any open timetable files in Excel or another application, then regenerate."
        ]
    return []



def generate_outputs(
    assignment_payload: List[Dict[str, object]],
    rooms: List[str],
    working_days: int,
    periods_per_day: int,
    lunch_break_periods_by_day: Dict[int, Set[int]],
    section_home_rooms: Dict[str, str],
    faculty_daily_default_max: int,
    faculty_daily_limits: Dict[str, int],
    lab_same_day_subject_threshold: int,
    random_seed: int | None,
    locked_section_cells: List[Dict[str, object]] | None = None,
    require_daily_free_period: bool = False,
    write_output_files: bool = True,
):
    days, periods, section_tables, optimization_details = generate_multi_section_timetable(
        assignments=assignment_payload,
        rooms=rooms,
        working_days=working_days,
        periods_per_day=periods_per_day,
        lunch_break_periods=lunch_break_periods_by_day,
        section_home_rooms=section_home_rooms,
        faculty_daily_default_max=faculty_daily_default_max,
        faculty_daily_limits=faculty_daily_limits,
        lab_same_day_subject_threshold=lab_same_day_subject_threshold,
        locked_section_cells=locked_section_cells,
        require_daily_free_period=require_daily_free_period,
        random_seed=random_seed,
    )

    validation_issues = validate_multi_section_timetable(
        section_tables,
        assignment_payload,
        lunch_break_periods=lunch_break_periods_by_day,
        faculty_daily_default_max=faculty_daily_default_max,
        faculty_daily_limits=faculty_daily_limits,
        require_daily_free_period=require_daily_free_period,
    )

    summary = build_multi_timetable_summary(
        days,
        periods,
        section_tables,
        room_names=rooms,
        lunch_break_periods=lunch_break_periods_by_day,
        optimization=optimization_details,
    )
    faculty_tables = build_faculty_timetable_tables(
        days,
        periods,
        section_tables,
        lunch_break_periods=lunch_break_periods_by_day,
    )
    class_tables = build_class_timetable_tables(section_tables)
    room_tables = build_room_timetable_tables(
        days,
        periods,
        section_tables,
        room_names=rooms,
        lunch_break_periods=lunch_break_periods_by_day,
    )

    if write_output_files:
        validation_issues.extend(
            write_generated_output_files(
                days,
                periods,
                section_tables,
                class_tables,
                faculty_tables,
                room_tables,
                summary,
                lunch_break_periods_by_day,
            )
        )

    return days, periods, section_tables, class_tables, faculty_tables, room_tables, summary, validation_issues


def generate_version_label() -> str:
    base_label = datetime.now(timezone.utc).strftime("VER-%Y%m%d-%H%M%S-%f")
    candidate_label = base_label
    suffix = 1
    while TimetableVersion.query.filter_by(version_label=candidate_label).first() is not None:
        candidate_label = f"{base_label}-{suffix}"
        suffix += 1
    return candidate_label


def persist_timetable_version(
    days: List[str],
    periods: List[str],
    section_tables: List[Dict[str, object]],
    summary: Dict[str, object],
    constraint_settings: Dict[str, object],
    generation_scope_description: str,
    validation_issues: List[str] | None = None,
) -> TimetableVersion:
    optimization_score: float | None = None
    optimization_data = summary.get("optimization")
    if isinstance(optimization_data, dict):
        score_value = optimization_data.get("score")
        if isinstance(score_value, (int, float)):
            optimization_score = float(score_value)

    if optimization_score is None:
        utilization_value = summary.get("utilization_percent")
        if isinstance(utilization_value, (int, float)):
            optimization_score = float(utilization_value)

    version_payload: Dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "periods": periods,
        "section_tables": section_tables,
        "summary": summary,
        "constraint_settings": constraint_settings,
        "generation_scope": generation_scope_description,
        "validation_issues": list(validation_issues or []),
    }

    version = TimetableVersion(
        version_label=generate_version_label(),
        status="draft",
        optimization_score=optimization_score,
        summary_json=json.dumps(version_payload),
        created_by_user_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(version)
    db.session.commit()
    return version


def extract_section_slot_map(
    payload: Dict[str, object],
) -> Tuple[Dict[Tuple[str, int, int], Dict[str, str]], Dict[str, Dict[str, str]], List[str], List[str]]:
    slot_map: Dict[Tuple[str, int, int], Dict[str, str]] = {}
    section_meta: Dict[str, Dict[str, str]] = {}

    days_raw = payload.get("days")
    periods_raw = payload.get("periods")
    days = [str(day_name) for day_name in days_raw] if isinstance(days_raw, list) else []
    periods = [str(period_name) for period_name in periods_raw] if isinstance(periods_raw, list) else []

    section_tables = payload.get("section_tables")
    if not isinstance(section_tables, list):
        return slot_map, section_meta, days, periods

    for section_table in section_tables:
        if not isinstance(section_table, dict):
            continue

        section_key = str(section_table.get("section_key", "")).strip()
        if not section_key:
            continue

        section_meta[section_key] = {
            "class_name": str(section_table.get("class_name", "")),
            "standard": str(section_table.get("standard", "")),
            "section": str(section_table.get("section", "")),
        }

        timetable_matrix = section_table.get("timetable")
        if not isinstance(timetable_matrix, list):
            continue

        for day_index, day_row in enumerate(timetable_matrix):
            if not isinstance(day_row, list):
                continue

            for period_index, cell in enumerate(day_row):
                if not isinstance(cell, dict):
                    continue

                slot_map[(section_key, day_index, period_index)] = {
                    "subject": str(cell.get("subject", "")),
                    "teacher": str(cell.get("teacher", "")),
                    "room": str(cell.get("room", "")),
                }

    return slot_map, section_meta, days, periods


def compare_version_payloads(
    payload_a: Dict[str, object],
    payload_b: Dict[str, object],
) -> Dict[str, object]:
    slot_map_a, section_meta_a, days_a, periods_a = extract_section_slot_map(payload_a)
    slot_map_b, section_meta_b, days_b, periods_b = extract_section_slot_map(payload_b)

    days = days_b or days_a
    periods = periods_b or periods_a
    section_meta = section_meta_b or section_meta_a

    all_slot_keys = sorted(
        set(slot_map_a.keys()) | set(slot_map_b.keys()),
        key=lambda key: (key[0], key[1], key[2]),
    )

    changes: List[Dict[str, object]] = []
    changed_count = 0
    added_count = 0
    removed_count = 0
    unchanged_count = 0
    section_change_count: Dict[str, int] = {}

    for section_key, day_index, period_index in all_slot_keys:
        before_value = slot_map_a.get((section_key, day_index, period_index))
        after_value = slot_map_b.get((section_key, day_index, period_index))

        if before_value is not None and after_value is not None and before_value == after_value:
            unchanged_count += 1
            continue

        if before_value is None and after_value is not None:
            change_type = "added"
            added_count += 1
        elif before_value is not None and after_value is None:
            change_type = "removed"
            removed_count += 1
        else:
            change_type = "changed"
            changed_count += 1

        section_change_count[section_key] = section_change_count.get(section_key, 0) + 1

        day_label = days[day_index] if day_index < len(days) else f"Day {day_index + 1}"
        period_label = periods[period_index] if period_index < len(periods) else f"Period {period_index + 1}"

        def _format_slot(value: Dict[str, str] | None) -> str:
            if value is None:
                return "FREE"
            return f"{value['subject']} | {value['teacher']} | {value['room']}"

        changes.append(
            {
                "section_key": section_key,
                "day_index": day_index,
                "period_index": period_index,
                "day_label": day_label,
                "period_label": period_label,
                "change_type": change_type,
                "before": _format_slot(before_value),
                "after": _format_slot(after_value),
            }
        )

    top_section_changes = sorted(
        section_change_count.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return {
        "changed_count": changed_count,
        "added_count": added_count,
        "removed_count": removed_count,
        "unchanged_count": unchanged_count,
        "total_compared_slots": len(all_slot_keys),
        "changes": changes,
        "top_section_changes": top_section_changes,
        "section_meta": section_meta,
    }


def normalize_lunch_break_periods_by_day_from_summary(
    summary: Dict[str, object],
    day_count: int,
    period_count: int,
) -> Dict[int, List[int]]:
    normalized: Dict[int, List[int]] = {
        day_index: []
        for day_index in range(day_count)
    }

    lunch_breaks_raw = summary.get("lunch_break_periods_by_day", {})
    if not isinstance(lunch_breaks_raw, dict):
        return normalized

    parsed_day_keys: List[int] = []
    for raw_day_key in lunch_breaks_raw.keys():
        try:
            parsed_day_keys.append(int(raw_day_key))
        except (TypeError, ValueError):
            continue

    treat_as_one_based = bool(parsed_day_keys) and 0 not in parsed_day_keys

    for day_key, raw_values in lunch_breaks_raw.items():
        try:
            parsed_day = int(day_key)
        except (TypeError, ValueError):
            continue

        day_index = parsed_day - 1 if treat_as_one_based else parsed_day

        if day_index < 0 or day_index >= day_count:
            continue

        if isinstance(raw_values, int):
            candidate_values = [raw_values]
        elif isinstance(raw_values, (list, tuple, set)):
            candidate_values = list(raw_values)
        else:
            candidate_values = []

        parsed_values: List[int] = []
        for raw_value in candidate_values:
            try:
                parsed_period = int(raw_value)
            except (TypeError, ValueError):
                continue
            if 1 <= parsed_period <= period_count:
                parsed_values.append(parsed_period)

        normalized[day_index] = sorted(set(parsed_values))

    return normalized


def collect_room_names_from_section_tables(
    section_tables: List[Dict[str, object]],
    summary: Dict[str, object],
) -> List[str]:
    room_names: Set[str] = set()

    room_stats = summary.get("room_stats", {})
    if isinstance(room_stats, dict):
        room_names.update(str(room_name).strip() for room_name in room_stats.keys())

    for section_table in section_tables:
        if not isinstance(section_table, dict):
            continue

        timetable = section_table.get("timetable")
        if not isinstance(timetable, list):
            continue

        for day_row in timetable:
            if not isinstance(day_row, list):
                continue
            for cell in day_row:
                if isinstance(cell, dict):
                    room_name = str(cell.get("room", "")).strip()
                    if room_name:
                        room_names.add(room_name)

    return sorted(room_name for room_name in room_names if room_name)


def parse_locked_slot_rows(
    raw_text: str,
    section_tables: List[Dict[str, object]],
    days: List[str],
    periods: List[str],
) -> Set[Tuple[str, int, int]]:
    lines = split_non_empty_lines(raw_text)
    if not lines:
        raise ValueError(
            "Provide at least one lock row in format: SectionKey,Day,Period (supports * wildcards)."
        )

    section_keys = {
        str(table.get("section_key", "")).strip()
        for table in section_tables
        if isinstance(table, dict) and str(table.get("section_key", "")).strip()
    }

    day_name_map = {
        day_name.strip().lower(): index
        for index, day_name in enumerate(days)
    }
    for day_name, day_index in list(day_name_map.items()):
        day_name_map.setdefault(day_name[:3], day_index)

    locked_slots: Set[Tuple[str, int, int]] = set()

    for index, line in enumerate(lines, start=1):
        row = [value.strip() for value in next(csv.reader([line], skipinitialspace=True))]
        if len(row) != 3:
            raise ValueError(
                f"Lock row {index} must be: SectionKey,Day,Period"
            )

        section_key, day_raw, period_raw = row
        if section_key not in section_keys:
            raise ValueError(f"Lock row {index} references unknown section '{section_key}'.")

        if day_raw == "*":
            day_indexes = list(range(len(days)))
        else:
            day_token = day_raw.lower()
            if day_token.isdigit():
                parsed_day = int(day_token)
                if parsed_day < 1 or parsed_day > len(days):
                    raise ValueError(f"Lock row {index} day must be between 1 and {len(days)}.")
                day_indexes = [parsed_day - 1]
            elif day_token in day_name_map:
                day_indexes = [day_name_map[day_token]]
            else:
                raise ValueError(
                    f"Lock row {index} day must be a number, day name, or * wildcard."
                )

        if period_raw == "*":
            period_indexes = list(range(len(periods)))
        else:
            if not period_raw.isdigit():
                raise ValueError(f"Lock row {index} period must be a number or * wildcard.")
            parsed_period = int(period_raw)
            if parsed_period < 1 or parsed_period > len(periods):
                raise ValueError(f"Lock row {index} period must be between 1 and {len(periods)}.")
            period_indexes = [parsed_period - 1]

        for day_index in day_indexes:
            for period_index in period_indexes:
                locked_slots.add((section_key, day_index, period_index))

    return locked_slots


def build_locked_cells_from_slots(
    section_tables: List[Dict[str, object]],
    locked_slots: Set[Tuple[str, int, int]],
    lunch_break_periods_by_day: Dict[int, List[int]],
) -> List[Dict[str, object]]:
    table_by_key = {
        str(table.get("section_key", "")).strip(): table
        for table in section_tables
        if isinstance(table, dict)
    }

    locked_cells: List[Dict[str, object]] = []

    for section_key, day_index, period_index in sorted(
        locked_slots,
        key=lambda item: (item[0], item[1], item[2]),
    ):
        if (period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
            continue

        table = table_by_key.get(section_key)
        if table is None:
            continue

        timetable = table.get("timetable")
        if not isinstance(timetable, list) or day_index >= len(timetable):
            continue

        day_row = timetable[day_index]
        if not isinstance(day_row, list) or period_index >= len(day_row):
            continue

        cell = day_row[period_index]
        if not isinstance(cell, dict):
            continue

        locked_cells.append(
            {
                "section_key": section_key,
                "day_index": day_index,
                "period_index": period_index,
                "subject": str(cell.get("subject", "")).strip(),
                "teacher": str(cell.get("teacher", "")).strip(),
                "room": str(cell.get("room", "")).strip(),
                "is_lab": bool(cell.get("is_lab", False)),
                "session_id": str(cell.get("session_id", "")).strip(),
                "session_length": int(cell.get("session_length", 2 if bool(cell.get("is_lab", False)) else 1)),
                "session_part": int(cell.get("session_part", 1)),
            }
        )

    return locked_cells


def rank_scenario_candidate(summary: Dict[str, object], validation_issues: List[str]) -> float:
    optimization = summary.get("optimization", {})
    optimization_score = float(optimization.get("score", 0.0)) if isinstance(optimization, dict) else 0.0
    utilization_score = float(summary.get("utilization_percent", 0.0))
    issue_penalty = float(len(validation_issues)) * 3.0
    return round((optimization_score * 1.25) + utilization_score - issue_penalty, 3)


def build_analytics_payload(prepared_payload: Dict[str, object]) -> Dict[str, object]:
    days = [str(day) for day in prepared_payload.get("days", [])]
    periods = [str(period) for period in prepared_payload.get("periods", [])]
    section_tables = prepared_payload.get("section_tables", [])
    room_tables = prepared_payload.get("room_tables", [])
    summary = prepared_payload.get("summary", {}) if isinstance(prepared_payload.get("summary"), dict) else {}
    lunch_break_periods_by_day = prepared_payload.get("lunch_break_periods_by_day", {})

    room_heatmap_rows: List[Dict[str, object]] = []
    room_heatmap_peak = 0
    for room_table in room_tables:
        room_name = str(room_table.get("room", "")).strip()
        timetable = room_table.get("timetable")
        if not room_name or not isinstance(timetable, list):
            continue

        day_counts: List[int] = []
        total_count = 0
        for day_index, day_row in enumerate(timetable):
            if not isinstance(day_row, list):
                day_counts.append(0)
                continue

            day_count = 0
            for period_index, cell in enumerate(day_row):
                if (period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
                    continue
                if isinstance(cell, dict) and "conflicts" not in cell:
                    day_count += 1
            day_counts.append(day_count)
            total_count += day_count

        room_heatmap_peak = max(room_heatmap_peak, max(day_counts) if day_counts else 0)
        room_heatmap_rows.append(
            {
                "room": room_name,
                "day_counts": day_counts,
                "total": total_count,
            }
        )

    room_heatmap_rows.sort(key=lambda row: int(row["total"]), reverse=True)

    teacher_loads_dict = summary.get("teacher_loads", {}) if isinstance(summary.get("teacher_loads"), dict) else {}
    teacher_load_items = [(str(name), int(load)) for name, load in teacher_loads_dict.items()]
    load_values = [load for _, load in teacher_load_items]
    mean_load = (sum(load_values) / len(load_values)) if load_values else 0.0
    variance = (
        sum((load - mean_load) ** 2 for load in load_values) / len(load_values)
        if load_values
        else 0.0
    )
    std_dev = math.sqrt(variance)
    coefficient_var = (std_dev / mean_load) * 100 if mean_load > 0 else 0.0
    fairness_score = max(0.0, round(100.0 - coefficient_var, 2))

    teacher_load_items.sort(key=lambda item: item[1], reverse=True)

    subject_day_counts: Dict[str, List[int]] = {}
    day_period_loads: List[List[int]] = [[0 for _ in periods] for _ in days]
    period_peak_counts: List[int] = [0 for _ in periods]

    for section_table in section_tables:
        timetable = section_table.get("timetable")
        if not isinstance(timetable, list):
            continue

        for day_index, day_row in enumerate(timetable):
            if not isinstance(day_row, list):
                continue
            for period_index, cell in enumerate(day_row):
                if (period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
                    continue
                if not isinstance(cell, dict) or "conflicts" in cell:
                    continue

                subject_name = str(cell.get("subject", "")).strip()
                if subject_name:
                    if subject_name not in subject_day_counts:
                        subject_day_counts[subject_name] = [0 for _ in days]
                    subject_day_counts[subject_name][day_index] += 1

                day_period_loads[day_index][period_index] += 1
                period_peak_counts[period_index] += 1

    subject_distribution_rows = sorted(
        (
            {
                "subject": subject_name,
                "day_counts": counts,
                "total": sum(counts),
            }
            for subject_name, counts in subject_day_counts.items()
        ),
        key=lambda row: int(row["total"]),
        reverse=True,
    )

    max_day_period_load = max((max(row) for row in day_period_loads), default=0)
    peak_period_index = 0
    peak_period_value = 0
    for index, value in enumerate(period_peak_counts):
        if value > peak_period_value:
            peak_period_index = index
            peak_period_value = value

    return {
        "days": days,
        "periods": periods,
        "room_heatmap_rows": room_heatmap_rows,
        "room_heatmap_peak": room_heatmap_peak,
        "teacher_load_items": teacher_load_items,
        "fairness_score": fairness_score,
        "mean_load": round(mean_load, 2),
        "std_dev": round(std_dev, 2),
        "subject_distribution_rows": subject_distribution_rows[:20],
        "day_period_loads": day_period_loads,
        "max_day_period_load": max_day_period_load,
        "period_peak_counts": period_peak_counts,
        "peak_period_label": periods[peak_period_index] if periods else "",
        "peak_period_value": peak_period_value,
        "summary": summary,
    }


def escape_ics_text(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    escaped = escaped.replace(";", "\\;").replace(",", "\\,")
    escaped = escaped.replace("\n", "\\n")
    return escaped


def build_ics_calendar_text(
    version: TimetableVersion,
    days: List[str],
    periods: List[str],
    section_tables: List[Dict[str, object]],
    lunch_break_periods_by_day: Dict[int, List[int]],
    faculty_filter: str = "",
    section_filter: str = "",
) -> str:
    period_duration_minutes_raw = os.environ.get("TIMETABLE_ICS_PERIOD_MINUTES", "60").strip()
    day_start_hour_raw = os.environ.get("TIMETABLE_ICS_DAY_START_HOUR", "9").strip()

    try:
        period_duration_minutes = max(30, int(period_duration_minutes_raw))
    except ValueError:
        period_duration_minutes = 60

    try:
        day_start_hour = max(0, min(20, int(day_start_hour_raw)))
    except ValueError:
        day_start_hour = 9

    effective = version.effective_from or datetime.now(timezone.utc)
    effective_date = effective.date()
    monday_date = effective_date - timedelta(days=effective_date.weekday())
    generated_at = datetime.now(timezone.utc)

    normalized_faculty_filter = faculty_filter.strip().lower()
    normalized_section_filter = section_filter.strip()

    events: List[str] = []
    seen_lab_sessions: Set[Tuple[str, str, int]] = set()

    for section_table in section_tables:
        section_key = str(section_table.get("section_key", "")).strip()
        if normalized_section_filter and section_key != normalized_section_filter:
            continue

        timetable = section_table.get("timetable")
        if not isinstance(timetable, list):
            continue

        for day_index, day_row in enumerate(timetable):
            if not isinstance(day_row, list):
                continue

            for period_index, cell in enumerate(day_row):
                if (period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
                    continue
                if not isinstance(cell, dict):
                    continue

                teacher_name = str(cell.get("teacher", "")).strip()
                if normalized_faculty_filter and teacher_name.lower() != normalized_faculty_filter:
                    continue

                is_lab = bool(cell.get("is_lab", False))
                session_length = int(cell.get("session_length", 1) or 1)
                session_part = int(cell.get("session_part", 1) or 1)
                session_id = str(cell.get("session_id", "")).strip()

                if is_lab and session_length > 1:
                    if session_part != 1:
                        continue
                    marker = (section_key, session_id or f"{day_index}:{period_index}", day_index)
                    if marker in seen_lab_sessions:
                        continue
                    seen_lab_sessions.add(marker)

                start_date = monday_date + timedelta(days=day_index)
                start_dt = datetime(
                    year=start_date.year,
                    month=start_date.month,
                    day=start_date.day,
                    hour=day_start_hour,
                    tzinfo=timezone.utc,
                ) + timedelta(minutes=period_index * period_duration_minutes)

                end_dt = start_dt + timedelta(minutes=session_length * period_duration_minutes)

                subject_name = str(cell.get("subject", "")).strip()
                room_name = str(cell.get("room", "")).strip()
                class_name = str(cell.get("class_name", "")).strip()
                standard = str(cell.get("standard", "")).strip()
                section_name = str(cell.get("section", "")).strip()

                summary_text = subject_name
                if class_name or standard or section_name:
                    summary_text = (
                        f"{subject_name} | {class_name} Std {standard} Sec {section_name}".strip()
                    )

                description_lines = [
                    f"Subject: {subject_name}",
                    f"Faculty: {teacher_name}",
                    f"Section: {section_key}",
                ]
                if room_name:
                    description_lines.append(f"Room: {room_name}")
                if is_lab:
                    description_lines.append("Type: LAB")

                uid = f"{uuid.uuid4()}@timetable-generator"
                events.extend(
                    [
                        "BEGIN:VEVENT",
                        f"UID:{uid}",
                        f"DTSTAMP:{generated_at.strftime('%Y%m%dT%H%M%SZ')}",
                        f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%SZ')}",
                        f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%SZ')}",
                        f"SUMMARY:{escape_ics_text(summary_text)}",
                        f"DESCRIPTION:{escape_ics_text('\\n'.join(description_lines))}",
                        f"LOCATION:{escape_ics_text(room_name)}",
                        "END:VEVENT",
                    ]
                )

    calendar_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Automatic Timetable Generator//EN",
        "CALSCALE:GREGORIAN",
    ]
    calendar_lines.extend(events)
    calendar_lines.append("END:VCALENDAR")
    return "\r\n".join(calendar_lines) + "\r\n"


def prepare_timetable_payload_for_render(payload: Dict[str, object]) -> Dict[str, object]:
    days_raw = payload.get("days")
    periods_raw = payload.get("periods")
    section_tables_raw = payload.get("section_tables")
    summary_raw = payload.get("summary")

    if not isinstance(days_raw, list) or not isinstance(periods_raw, list) or not isinstance(section_tables_raw, list):
        raise ValueError("Timetable payload is incomplete and cannot be rendered.")

    days = [str(day_name) for day_name in days_raw]
    periods = [str(period_name) for period_name in periods_raw]
    section_tables = section_tables_raw

    if not days or not periods:
        raise ValueError("Timetable payload does not include valid day/period headers.")

    summary_seed = summary_raw if isinstance(summary_raw, dict) else {}
    lunch_break_periods_by_day = normalize_lunch_break_periods_by_day_from_summary(
        summary_seed,
        len(days),
        len(periods),
    )
    lunch_break_period_sets = {
        day_index: set(period_list)
        for day_index, period_list in lunch_break_periods_by_day.items()
    }

    room_names = collect_room_names_from_section_tables(section_tables, summary_seed)

    optimization_payload = summary_seed.get("optimization")
    optimization = optimization_payload if isinstance(optimization_payload, dict) else None

    summary = build_multi_timetable_summary(
        days,
        periods,
        section_tables,
        room_names=room_names,
        lunch_break_periods=lunch_break_period_sets,
        optimization=optimization,
    )

    if isinstance(summary_seed, dict):
        for key, value in summary_seed.items():
            if key not in summary:
                summary[key] = value

    summary["lunch_break_periods_by_day"] = {
        str(day_index): list(period_list)
        for day_index, period_list in lunch_break_periods_by_day.items()
    }

    class_tables = build_class_timetable_tables(section_tables)
    faculty_tables = build_faculty_timetable_tables(
        days,
        periods,
        section_tables,
        lunch_break_periods=lunch_break_periods_by_day,
    )
    room_tables = build_room_timetable_tables(
        days,
        periods,
        section_tables,
        room_names=room_names,
        lunch_break_periods=lunch_break_periods_by_day,
    )

    return {
        "days": days,
        "periods": periods,
        "section_tables": section_tables,
        "class_tables": class_tables,
        "faculty_tables": faculty_tables,
        "room_tables": room_tables,
        "summary": summary,
        "lunch_break_periods_by_day": lunch_break_periods_by_day,
    }


def find_section_table_by_key(
    section_tables: List[Dict[str, object]],
    section_key: str,
) -> Dict[str, object] | None:
    for section_table in section_tables:
        if not isinstance(section_table, dict):
            continue
        if str(section_table.get("section_key", "")).strip() == section_key:
            return section_table
    return None


def find_lab_pair_period_index(day_row: List[object], period_index: int) -> int | None:
    if period_index < 0 or period_index >= len(day_row):
        return None

    cell = day_row[period_index]
    if not isinstance(cell, dict):
        return None

    if not bool(cell.get("is_lab", False)):
        return None

    if int(cell.get("session_length", 1)) != 2:
        return None

    session_part = int(cell.get("session_part", 0))
    if session_part == 1:
        pair_period_index = period_index + 1
    elif session_part == 2:
        pair_period_index = period_index - 1
    else:
        return None

    if pair_period_index < 0 or pair_period_index >= len(day_row):
        return None

    pair_cell = day_row[pair_period_index]
    if not isinstance(pair_cell, dict):
        return None

    if not bool(pair_cell.get("is_lab", False)):
        return None

    if int(pair_cell.get("session_length", 1)) != 2:
        return None

    if {session_part, int(pair_cell.get("session_part", 0))} != {1, 2}:
        return None

    session_id = str(cell.get("session_id", "")).strip()
    pair_session_id = str(pair_cell.get("session_id", "")).strip()
    if not session_id or not pair_session_id or session_id != pair_session_id:
        return None

    return pair_period_index


def resolve_faculty_slot_matches(
    section_tables: List[Dict[str, object]],
    faculty_name: str,
    day_index: int,
    period_index: int,
) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []

    for section_table in section_tables:
        if not isinstance(section_table, dict):
            continue

        timetable = section_table.get("timetable")
        if not isinstance(timetable, list) or day_index >= len(timetable):
            continue

        day_row = timetable[day_index]
        if not isinstance(day_row, list) or period_index >= len(day_row):
            continue

        cell = day_row[period_index]
        if not isinstance(cell, dict):
            continue

        teacher_name = str(cell.get("teacher", "")).strip()
        if teacher_name != faculty_name:
            continue

        matches.append(
            {
                "section_key": str(section_table.get("section_key", "")).strip(),
                "subject": str(cell.get("subject", "")).strip(),
                "room": str(cell.get("room", "")).strip(),
            }
        )

    return matches


def collect_manual_edit_conflicts(
    section_tables: List[Dict[str, object]],
    target_slots: Set[Tuple[str, int, int]],
    lunch_break_periods_by_day: Dict[int, List[int]],
    days: List[str],
    periods: List[str],
) -> List[str]:
    section_map = {
        str(section_table.get("section_key", "")).strip(): section_table
        for section_table in section_tables
        if isinstance(section_table, dict)
    }

    issues: Set[str] = set()

    for section_key, day_index, period_index in target_slots:
        section_table = section_map.get(section_key)
        if section_table is None:
            issues.add(f"Target section {section_key} was not found while validating edit.")
            continue

        timetable = section_table.get("timetable")
        if not isinstance(timetable, list) or day_index >= len(timetable):
            issues.add(f"Edited slot is out of range for section {section_key}.")
            continue

        day_row = timetable[day_index]
        if not isinstance(day_row, list) or period_index >= len(day_row):
            issues.add(f"Edited period is out of range for section {section_key}.")
            continue

        cell = day_row[period_index]
        if cell is None:
            continue

        if not isinstance(cell, dict):
            issues.add(f"Edited slot in {section_key} contains invalid data.")
            continue

        day_label = days[day_index] if day_index < len(days) else f"Day {day_index + 1}"
        period_label = periods[period_index] if period_index < len(periods) else f"Period {period_index + 1}"

        if (period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
            issues.add(
                f"Cannot schedule a lecture in {section_key} at {day_label}, {period_label} because it is a lunch-break slot."
            )

        teacher_name = str(cell.get("teacher", "")).strip()
        room_name = str(cell.get("room", "")).strip()
        subject_name = str(cell.get("subject", "")).strip()

        if not teacher_name or not room_name or not subject_name:
            issues.add(
                f"Edited slot in {section_key} at {day_label}, {period_label} must include subject, faculty, and room."
            )
            continue

        for other_section in section_tables:
            if not isinstance(other_section, dict):
                continue

            other_section_key = str(other_section.get("section_key", "")).strip()
            if other_section_key == section_key:
                continue

            other_timetable = other_section.get("timetable")
            if not isinstance(other_timetable, list) or day_index >= len(other_timetable):
                continue

            other_day_row = other_timetable[day_index]
            if not isinstance(other_day_row, list) or period_index >= len(other_day_row):
                continue

            other_cell = other_day_row[period_index]
            if not isinstance(other_cell, dict):
                continue

            other_subject = str(other_cell.get("subject", "")).strip()
            other_teacher = str(other_cell.get("teacher", "")).strip()
            other_room = str(other_cell.get("room", "")).strip()

            if teacher_name and teacher_name == other_teacher:
                issues.add(
                    f"Faculty conflict at {day_label}, {period_label}: {teacher_name} is already assigned to {other_section_key} ({other_subject})."
                )

            if room_name and room_name == other_room:
                issues.add(
                    f"Room conflict at {day_label}, {period_label}: {room_name} is already used by {other_section_key} ({other_subject})."
                )

    return sorted(issues)


def auto_apply_absence_substitutions(
    section_tables: List[Dict[str, object]],
    assignment_payload: List[Dict[str, object]],
    absent_faculty: str,
    day_index: int,
    period_index: int | None,
    lunch_break_periods_by_day: Dict[int, List[int]],
    faculty_daily_default_max: int,
    faculty_daily_limits: Dict[str, int],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[str]]:
    updated_section_tables = json.loads(json.dumps(section_tables))
    issues: List[str] = []
    substitutions: List[Dict[str, object]] = []

    if not updated_section_tables:
        return updated_section_tables, substitutions, ["No section data available for substitution."]

    period_count = 0
    if isinstance(updated_section_tables[0].get("timetable"), list) and updated_section_tables[0]["timetable"]:
        first_day = updated_section_tables[0]["timetable"][0]
        if isinstance(first_day, list):
            period_count = len(first_day)

    max_teaching_periods_for_day = max(1, period_count - len(lunch_break_periods_by_day.get(day_index, [])))

    teacher_subjects: Dict[str, Set[str]] = {}
    for assignment in assignment_payload:
        teacher_name = str(assignment.get("teacher", "")).strip()
        subject_name = str(assignment.get("subject", "")).strip()
        if not teacher_name or not subject_name:
            continue
        teacher_subjects.setdefault(teacher_name, set()).add(subject_name)

    candidate_teachers: Set[str] = set(teacher_subjects.keys())
    teacher_usage_by_slot: Dict[Tuple[int, int], Set[str]] = {}
    teacher_day_load: Dict[Tuple[str, int], int] = {}
    teacher_total_load: Dict[str, int] = {}

    for section_table in updated_section_tables:
        timetable = section_table.get("timetable")
        if not isinstance(timetable, list):
            continue

        for row_day_index, day_row in enumerate(timetable):
            if not isinstance(day_row, list):
                continue
            for row_period_index, cell in enumerate(day_row):
                if not isinstance(cell, dict):
                    continue
                if (row_period_index + 1) in lunch_break_periods_by_day.get(row_day_index, []):
                    continue

                teacher_name = str(cell.get("teacher", "")).strip()
                if not teacher_name:
                    continue

                candidate_teachers.add(teacher_name)
                teacher_usage_by_slot.setdefault((row_day_index, row_period_index), set()).add(teacher_name)
                teacher_day_load[(teacher_name, row_day_index)] = teacher_day_load.get((teacher_name, row_day_index), 0) + 1
                teacher_total_load[teacher_name] = teacher_total_load.get(teacher_name, 0) + 1

    processed_lab_markers: Set[Tuple[str, str]] = set()

    for section_table in updated_section_tables:
        section_key = str(section_table.get("section_key", "")).strip()
        timetable = section_table.get("timetable")
        if not isinstance(timetable, list) or day_index >= len(timetable):
            continue

        day_row = timetable[day_index]
        if not isinstance(day_row, list):
            continue

        for current_period_index in range(len(day_row)):
            if period_index is not None and current_period_index != period_index:
                continue

            if (current_period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
                continue

            cell = day_row[current_period_index]
            if not isinstance(cell, dict):
                continue

            current_teacher = str(cell.get("teacher", "")).strip()
            if current_teacher != absent_faculty:
                continue

            is_lab = bool(cell.get("is_lab", False))
            session_length = int(cell.get("session_length", 1) or 1)
            session_part = int(cell.get("session_part", 1) or 1)
            session_id = str(cell.get("session_id", "")).strip()

            block_start_period = current_period_index
            if is_lab and session_length > 1 and session_part == 2:
                block_start_period = current_period_index - 1

            if block_start_period < 0 or block_start_period + session_length > len(day_row):
                issues.append(
                    f"Cannot substitute {absent_faculty} in {section_key} period {current_period_index + 1}: invalid LAB block."
                )
                continue

            if is_lab and session_length > 1:
                marker = (section_key, session_id or f"{day_index}:{block_start_period}")
                if marker in processed_lab_markers:
                    continue
                processed_lab_markers.add(marker)

            block_slots = [
                (day_index, block_start_period + offset)
                for offset in range(session_length)
            ]
            if any((slot[1] + 1) in lunch_break_periods_by_day.get(day_index, []) for slot in block_slots):
                issues.append(
                    f"Cannot substitute {absent_faculty} in {section_key}: selected block intersects lunch break."
                )
                continue

            subject_name = str(cell.get("subject", "")).strip()
            room_name = str(cell.get("room", "")).strip()
            section_label = f"{section_key} (day {day_index + 1}, period {block_start_period + 1})"

            candidates: List[Tuple[Tuple[int, int, int, str], str]] = []
            for candidate_name in sorted(candidate_teachers):
                if candidate_name == absent_faculty:
                    continue

                if any(candidate_name in teacher_usage_by_slot.get(slot, set()) for slot in block_slots):
                    continue

                candidate_limit = faculty_daily_limits.get(candidate_name, faculty_daily_default_max)
                candidate_limit = max(1, min(candidate_limit, max_teaching_periods_for_day))
                projected_load = teacher_day_load.get((candidate_name, day_index), 0) + len(block_slots)
                if projected_load > candidate_limit:
                    continue

                same_subject_penalty = 0 if subject_name in teacher_subjects.get(candidate_name, set()) else 1
                rank = (
                    same_subject_penalty,
                    teacher_day_load.get((candidate_name, day_index), 0),
                    teacher_total_load.get(candidate_name, 0),
                    candidate_name,
                )
                candidates.append((rank, candidate_name))

            if not candidates:
                issues.append(
                    f"No substitute found for {absent_faculty} at {section_label}."
                )
                continue

            candidates.sort(key=lambda item: item[0])
            replacement_teacher = candidates[0][1]

            for slot_day_index, slot_period_index in block_slots:
                current_cell = day_row[slot_period_index]
                if not isinstance(current_cell, dict):
                    continue
                current_cell["teacher"] = replacement_teacher

                slot_key = (slot_day_index, slot_period_index)
                teacher_usage = teacher_usage_by_slot.setdefault(slot_key, set())
                if absent_faculty in teacher_usage:
                    teacher_usage.remove(absent_faculty)
                teacher_usage.add(replacement_teacher)

            teacher_day_load[(absent_faculty, day_index)] = max(
                0,
                teacher_day_load.get((absent_faculty, day_index), 0) - len(block_slots),
            )
            teacher_total_load[absent_faculty] = max(
                0,
                teacher_total_load.get(absent_faculty, 0) - len(block_slots),
            )
            teacher_day_load[(replacement_teacher, day_index)] = teacher_day_load.get((replacement_teacher, day_index), 0) + len(block_slots)
            teacher_total_load[replacement_teacher] = teacher_total_load.get(replacement_teacher, 0) + len(block_slots)

            substitutions.append(
                {
                    "section_key": section_key,
                    "day_index": day_index,
                    "period_index": block_start_period,
                    "subject": subject_name,
                    "room": room_name,
                    "old_teacher": absent_faculty,
                    "new_teacher": replacement_teacher,
                    "is_lab": is_lab,
                    "duration": session_length,
                }
            )

    return updated_section_tables, substitutions, issues


def build_manual_edit_cell(
    section_table: Dict[str, object],
    subject: str,
    teacher: str,
    room: str,
    is_lab: bool,
    session_length: int,
    session_part: int,
    session_id: str,
    is_locked: bool = False,
) -> Dict[str, object]:
    return {
        "class_name": str(section_table.get("class_name", "")).strip(),
        "standard": str(section_table.get("standard", "")).strip(),
        "section": str(section_table.get("section", "")).strip(),
        "section_key": str(section_table.get("section_key", "")).strip(),
        "subject": subject,
        "teacher": teacher,
        "room": room,
        "is_lab": is_lab,
        "is_locked": is_locked,
        "session_length": session_length,
        "session_part": session_part,
        "session_id": session_id,
    }


def _export_redirect_fallback() -> Response:
    referrer = request.referrer or ""
    if referrer:
        return redirect(referrer)
    return redirect(url_for("dashboard"))


def _build_export_filename(version: TimetableVersion, extension: str) -> str:
    safe_label = "".join(
        character.lower() if character.isalnum() else "-"
        for character in str(version.version_label or "")
    ).strip("-")
    if not safe_label:
        safe_label = f"version-{version.id}"
    return f"timetable-{safe_label}.{extension}"


def _normalize_export_targets(raw_values: List[str], csv_fallback: str) -> List[str]:
    values: List[str] = []
    for raw_value in raw_values:
        cleaned = str(raw_value or "").strip()
        if cleaned:
            values.append(cleaned)

    if csv_fallback.strip():
        values.extend(
            token.strip()
            for token in csv_fallback.split(",")
            if token.strip()
        )

    deduped: List[str] = []
    seen: Set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _extract_export_cards(
    payload: Dict[str, object],
    view_kind: str,
    selection_mode: str,
    selected_targets: List[str],
) -> Tuple[List[Dict[str, object]], List[str], List[str], Dict[int, List[int]], str]:
    days_raw = payload.get("days")
    periods_raw = payload.get("periods")
    section_tables = payload.get("section_tables")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

    if not isinstance(days_raw, list) or not isinstance(periods_raw, list) or not isinstance(section_tables, list):
        return [], [], [], {}, "Selected timetable payload is incomplete for export."

    days = [str(day_name) for day_name in days_raw]
    periods = [str(period_name) for period_name in periods_raw]
    lunch_break_periods_by_day = normalize_lunch_break_periods_by_day_from_summary(
        summary,
        len(days),
        len(periods),
    )
    lunch_sets = {
        day_index: set(period_values)
        for day_index, period_values in lunch_break_periods_by_day.items()
    }

    cards: List[Dict[str, object]] = []
    normalized_kind = (view_kind or "all").strip().lower()
    normalized_mode = (selection_mode or "all").strip().lower()
    selected_set = set(selected_targets)

    if normalized_kind in {"all", "section"}:
        for section_table in section_tables:
            if not isinstance(section_table, dict):
                continue
            section_key = str(section_table.get("section_key", "")).strip()
            if not section_key:
                continue
            if normalized_kind == "section" and normalized_mode != "all" and section_key not in selected_set:
                continue
            cards.append(
                {
                    "identifier": section_key,
                    "kind": "section",
                    "title": (
                        f"Section: {section_key} | "
                        f"{str(section_table.get('class_name', '')).strip()} | "
                        f"Std {str(section_table.get('standard', '')).strip()} | "
                        f"Sec {str(section_table.get('section', '')).strip()}"
                    ),
                    "timetable": section_table.get("timetable"),
                }
            )

    if normalized_kind == "class":
        class_tables = build_class_timetable_tables(section_tables)
        for class_table in class_tables:
            class_key = str(class_table.get("class_key", "")).strip()
            if not class_key:
                continue
            if normalized_mode != "all" and class_key not in selected_set:
                continue
            class_name = str(class_table.get("class_name", "")).strip()
            standard = str(class_table.get("standard", "")).strip()
            sections = class_table.get("sections") if isinstance(class_table.get("sections"), list) else []
            for section_entry in sections:
                if not isinstance(section_entry, dict):
                    continue
                section_label = str(section_entry.get("section", "")).strip()
                cards.append(
                    {
                        "identifier": class_key,
                        "kind": "class",
                        "title": f"Class: {class_name} | Std {standard} | Section {section_label}",
                        "timetable": section_entry.get("timetable"),
                    }
                )

    if normalized_kind == "faculty":
        faculty_tables = build_faculty_timetable_tables(
            days,
            periods,
            section_tables,
            lunch_break_periods=lunch_sets,
        )
        for faculty_table in faculty_tables:
            teacher_name = str(faculty_table.get("teacher", "")).strip()
            if not teacher_name:
                continue
            if normalized_mode != "all" and teacher_name not in selected_set:
                continue
            cards.append(
                {
                    "identifier": teacher_name,
                    "kind": "faculty",
                    "title": f"Faculty: {teacher_name}",
                    "timetable": faculty_table.get("timetable"),
                }
            )

    if normalized_kind == "room":
        room_tables = build_room_timetable_tables(
            days,
            periods,
            section_tables,
            lunch_break_periods=lunch_sets,
        )
        for room_table in room_tables:
            room_name = str(room_table.get("room", "")).strip()
            if not room_name:
                continue
            if normalized_mode != "all" and room_name not in selected_set:
                continue
            cards.append(
                {
                    "identifier": room_name,
                    "kind": "room",
                    "title": f"Room: {room_name}",
                    "timetable": room_table.get("timetable"),
                }
            )

    if normalized_mode in {"single", "multiple"} and not selected_set:
        return [], [], [], {}, "Select at least one target timetable for export."

    if not cards:
        return [], [], [], {}, "No timetable cards matched the selected export filters."

    return cards, days, periods, lunch_break_periods_by_day, ""


def _format_export_cell_text(cell: object, day_index: int, period_number: int, lunch_by_day: Dict[int, List[int]]) -> str:
    if period_number in lunch_by_day.get(day_index, []):
        return "Lunch Break"

    if not isinstance(cell, dict):
        return "Free Slot"

    if "conflicts" in cell:
        return "Conflict"

    if cell.get("lab_group_details"):
        return "LAB Group Session"

    subject_name = str(cell.get("subject", "")).strip() or "Untitled"
    teacher_name = str(cell.get("teacher", "")).strip()
    room_name = str(cell.get("room", "")).strip()
    is_lab = bool(cell.get("is_lab", False))
    first_line = subject_name + (" (LAB)" if is_lab else "")
    lines = [first_line]
    if teacher_name:
        lines.append(teacher_name)
    if room_name:
        lines.append(room_name)
    return "\n".join(lines)


def _build_pdf_for_cards(
    version: TimetableVersion,
    cards: List[Dict[str, object]],
    days: List[str],
    periods: List[str],
    lunch_break_periods_by_day: Dict[int, List[int]],
) -> Tuple[bytes | None, str]:
    if not REPORTLAB_AVAILABLE:
        return None, "PDF export requires reportlab. Install dependencies from requirements.txt and retry."

    try:
        colors = REPORTLAB_MODULES["colors"]
        A4 = REPORTLAB_MODULES["A4"]
        landscape = REPORTLAB_MODULES["landscape"]
        get_sample_style_sheet = REPORTLAB_MODULES["getSampleStyleSheet"]
        PageBreak = REPORTLAB_MODULES["PageBreak"]
        Paragraph = REPORTLAB_MODULES["Paragraph"]
        SimpleDocTemplate = REPORTLAB_MODULES["SimpleDocTemplate"]
        Spacer = REPORTLAB_MODULES["Spacer"]
        Table = REPORTLAB_MODULES["Table"]
        TableStyle = REPORTLAB_MODULES["TableStyle"]
    except KeyError:
        return None, "PDF export dependencies are partially loaded. Restart the app after installing requirements."

    output_buffer = io.BytesIO()
    document = SimpleDocTemplate(
        output_buffer,
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
    )
    styles = get_sample_style_sheet()
    content: List[object] = []

    content.append(Paragraph(f"Timetable Export - {version.version_label}", styles["Title"]))
    content.append(
        Paragraph(
            f"Status: {version.status.upper()} | Effective: {format_effective_timestamp(version.effective_from)}",
            styles["Normal"],
        )
    )
    content.append(Paragraph(f"Cards exported: {len(cards)}", styles["Normal"]))
    content.append(Spacer(1, 10))

    table_width = 790
    first_col_width = 72
    period_col_width = max(58, (table_width - first_col_width) / max(1, len(periods)))

    for card_index, card in enumerate(cards):
        matrix = card.get("timetable")
        if not isinstance(matrix, list):
            continue

        content.append(Paragraph(str(card.get("title", "Timetable")), styles["Heading3"]))

        table_data: List[List[str]] = [["Day"] + periods]
        for day_index, day_name in enumerate(days):
            day_row = matrix[day_index] if day_index < len(matrix) and isinstance(matrix[day_index], list) else []
            row_cells: List[str] = [day_name]
            for period_index, _period_label in enumerate(periods):
                cell = day_row[period_index] if period_index < len(day_row) else None
                row_cells.append(
                    _format_export_cell_text(
                        cell,
                        day_index,
                        period_index + 1,
                        lunch_break_periods_by_day,
                    )
                )
            table_data.append(row_cells)

        card_grid = Table(
            table_data,
            colWidths=[first_col_width] + [period_col_width] * len(periods),
            repeatRows=1,
        )
        card_grid.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f2fb")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aac2d8")),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#f3f9ff")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("LEADING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        content.append(card_grid)

        if card_index < len(cards) - 1:
            content.append(PageBreak())

    document.build(content)
    output_buffer.seek(0)
    return output_buffer.getvalue(), ""


def _build_jpg_for_card(
    card: Dict[str, object],
    days: List[str],
    periods: List[str],
    lunch_break_periods_by_day: Dict[int, List[int]],
) -> Tuple[bytes | None, str]:
    if not PILLOW_AVAILABLE:
        return None, "JPG export requires Pillow (PIL). Install Pillow to enable image exports."

    try:
        Image = PILLOW_MODULES["Image"]
        ImageDraw = PILLOW_MODULES["ImageDraw"]
        ImageFont = PILLOW_MODULES["ImageFont"]
    except KeyError:
        return None, "JPG export dependencies are partially loaded. Restart the app after installing Pillow."

    matrix = card.get("timetable")
    if not isinstance(matrix, list):
        return None, "Selected timetable card is not renderable as JPG."

    cell_width = 210
    day_col_width = 120
    header_height = 56
    row_height = 120
    title_height = 70

    width = day_col_width + (cell_width * len(periods)) + 2
    height = title_height + header_height + (row_height * len(days)) + 2

    image = Image.new("RGB", (width, height), "white")
    drawer = ImageDraw.Draw(image)

    try:
        title_font = ImageFont.truetype("arial.ttf", 20)
        header_font = ImageFont.truetype("arial.ttf", 13)
        cell_font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()

    drawer.text((12, 12), str(card.get("title", "Timetable")), fill=(30, 45, 70), font=title_font)

    top = title_height
    drawer.rectangle((0, top, width - 1, top + header_height), fill=(232, 242, 251), outline=(160, 190, 220))
    drawer.text((12, top + 18), "Day", fill=(20, 35, 55), font=header_font)
    for period_index, period_label in enumerate(periods):
        x0 = day_col_width + (period_index * cell_width)
        drawer.rectangle((x0, top, x0 + cell_width, top + header_height), outline=(160, 190, 220))
        drawer.text((x0 + 10, top + 18), str(period_label), fill=(20, 35, 55), font=header_font)

    for day_index, day_name in enumerate(days):
        y0 = top + header_height + (day_index * row_height)
        drawer.rectangle((0, y0, day_col_width, y0 + row_height), fill=(243, 249, 255), outline=(160, 190, 220))
        drawer.text((10, y0 + 10), day_name, fill=(20, 35, 55), font=header_font)

        day_row = matrix[day_index] if day_index < len(matrix) and isinstance(matrix[day_index], list) else []
        for period_index, _period_label in enumerate(periods):
            x0 = day_col_width + (period_index * cell_width)
            x1 = x0 + cell_width
            y1 = y0 + row_height
            drawer.rectangle((x0, y0, x1, y1), outline=(170, 190, 210))

            cell = day_row[period_index] if period_index < len(day_row) else None
            cell_text = _format_export_cell_text(
                cell,
                day_index,
                period_index + 1,
                lunch_break_periods_by_day,
            )
            text_lines = [line for line in cell_text.split("\n") if line.strip()]
            for line_index, line in enumerate(text_lines[:4]):
                drawer.text(
                    (x0 + 8, y0 + 8 + (line_index * 24)),
                    line[:30],
                    fill=(35, 45, 60),
                    font=cell_font,
                )

    output_buffer = io.BytesIO()
    image.save(output_buffer, format="JPEG", quality=90)
    output_buffer.seek(0)
    return output_buffer.getvalue(), ""


def resolve_export_version(version_id_raw: str) -> Tuple[TimetableVersion | None, str]:
    role_code = get_current_role_code()
    normalized_version_id = str(version_id_raw or "").strip()

    if normalized_version_id:
        try:
            version_id = int(normalized_version_id)
        except ValueError:
            return None, "Invalid version identifier for export."

        version = db.session.get(TimetableVersion, version_id)
        if version is None:
            return None, "Requested timetable version was not found."
    else:
        version = (
            TimetableVersion.query.filter_by(status="published")
            .order_by(TimetableVersion.id.desc())
            .first()
        )
        if version is None:
            return None, "No published timetable is available to export."

    if version.status != "published" and role_code not in {"ADMIN", "HOD"}:
        return None, "Only published timetable exports are allowed for your role."

    payload = version.summary()
    if not isinstance(payload.get("section_tables"), list):
        return None, "Selected timetable version does not contain exportable schedule data."

    return version, ""


def build_pdf_for_version(version: TimetableVersion) -> Tuple[bytes | None, str]:
    payload = version.summary()
    cards, days, periods, lunch_break_periods_by_day, error = _extract_export_cards(
        payload,
        view_kind="all",
        selection_mode="all",
        selected_targets=[],
    )
    if error:
        return None, error
    return _build_pdf_for_cards(version, cards, days, periods, lunch_break_periods_by_day)


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        now_epoch = time.time()
        rate_limit_keys = get_login_rate_limit_keys(username)

        prune_login_rate_limit_buckets(now_epoch)
        retry_after_seconds = get_login_retry_after_seconds(rate_limit_keys, now_epoch)
        if retry_after_seconds > 0:
            flash(
                f"Too many sign-in attempts. Try again in {retry_after_seconds} seconds.",
                "warning",
            )
            return render_template("login.html")

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password) or not user.is_active:
            record_login_failure(rate_limit_keys, now_epoch)
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        clear_login_failures(rate_limit_keys)
        login_user(user)
        flash("Signed in successfully.", "success")
        next_url = request.args.get("next", "").strip()
        return redirect(next_url or url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout() -> str:
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password() -> str:
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return render_template("change_password.html")

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return render_template("change_password.html")

        if new_password == current_password:
            flash("New password must be different from current password.", "danger")
            return render_template("change_password.html")

        password_policy_error = validate_password_policy(new_password)
        if password_policy_error:
            flash(password_policy_error, "danger")
            return render_template("change_password.html")

        current_user.set_password(new_password)
        current_user.must_change_password = False
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("change_password.html")


def build_personal_widgets(
    published_version: TimetableVersion | None,
    role_code: str,
) -> Dict[str, object]:
    widgets: Dict[str, object] = {
        "today_label": "",
        "tomorrow_label": "",
        "today_classes": 0,
        "free_periods": 0,
        "tomorrow_changes": 0,
        "room_utilization": 0.0,
        "today_rows": [],
        "message": "No published timetable available.",
    }

    if published_version is None:
        return widgets

    payload = published_version.summary()
    days_raw = payload.get("days")
    periods_raw = payload.get("periods")
    section_tables = payload.get("section_tables")
    summary = payload.get("summary")
    if not isinstance(days_raw, list) or not isinstance(periods_raw, list) or not isinstance(section_tables, list):
        widgets["message"] = "Published timetable payload is incomplete."
        return widgets

    days = [str(day_name) for day_name in days_raw]
    periods = [str(period_name) for period_name in periods_raw]
    if not days or not periods:
        widgets["message"] = "Published timetable payload is incomplete."
        return widgets

    now_utc = datetime.now(timezone.utc)
    today_index = now_utc.weekday() % len(days)
    tomorrow_index = (today_index + 1) % len(days)
    widgets["today_label"] = days[today_index]
    widgets["tomorrow_label"] = days[tomorrow_index]

    lunch_by_day = {}
    if isinstance(summary, dict):
        lunch_by_day = summary.get("lunch_break_periods_by_day", {}) or {}

    today_lunch_periods = lunch_by_day.get(str(today_index + 1), []) if isinstance(lunch_by_day, dict) else []
    teaching_periods_today = max(0, len(periods) - len(today_lunch_periods) if isinstance(today_lunch_periods, list) else len(periods))

    def parse_section_key_parts(section_key: str) -> Tuple[str, str, str]:
        normalized_key = str(section_key).strip()
        if not normalized_key:
            return "", "", ""

        parts = [part.strip() for part in normalized_key.split("|")]
        if len(parts) < 3:
            return "", "", ""

        class_name = parts[0]
        standard_part = parts[1]
        section_part = parts[2]

        standard = standard_part[4:].strip() if standard_part.lower().startswith("std ") else standard_part
        section = section_part[4:].strip() if section_part.lower().startswith("sec ") else section_part
        return class_name, standard, section

    def standard_rank(standard_text: str) -> int:
        match = re.search(r"\d+", str(standard_text))
        if match is None:
            return -1
        return int(match.group(0))

    user_records: Dict[Tuple[int, int], Dict[str, str]] = {}
    today_rows: List[Dict[str, str]] = []

    faculty_aliases = {
        str(current_user.full_name or "").strip().lower(),
        str(current_user.username or "").strip().lower(),
    }
    if role_code == "FACULTY":
        normalized_user_name = str(current_user.full_name or "").strip()
        normalized_username = str(current_user.username or "").strip()
        if normalized_username:
            linked_profile = FacultyProfile.query.filter_by(employee_code=normalized_username).first()
            if linked_profile and linked_profile.full_name:
                faculty_aliases.add(str(linked_profile.full_name).strip().lower())
        if normalized_user_name:
            linked_by_name = FacultyProfile.query.filter_by(full_name=normalized_user_name).first()
            if linked_by_name and linked_by_name.employee_code:
                faculty_aliases.add(str(linked_by_name.employee_code).strip().lower())

    student_section_key = ""
    student_class_name = str(current_user.profile_class_name or "").strip()
    student_standard = str(current_user.profile_standard or "").strip()
    student_section = str(current_user.profile_section_code or "").strip()
    if role_code == "STUDENT" and student_class_name and student_standard and student_section:
        student_section_key = build_section_key(student_class_name, student_standard, student_section)

    if role_code == "STUDENT" and student_class_name and student_section:
        parsed_sections: List[Dict[str, str]] = []
        available_section_keys: Set[str] = set()

        for table in section_tables:
            if not isinstance(table, dict):
                continue
            section_key = str(table.get("section_key", "")).strip()
            if not section_key:
                continue

            class_name = str(table.get("class_name", "")).strip()
            standard = str(table.get("standard", "")).strip()
            section_code = str(table.get("section", "")).strip()
            if not class_name or not standard or not section_code:
                class_name, standard, section_code = parse_section_key_parts(section_key)
            if not class_name or not section_code:
                continue

            parsed_sections.append(
                {
                    "section_key": section_key,
                    "class_name": class_name,
                    "standard": standard,
                    "section": section_code,
                }
            )
            available_section_keys.add(section_key)

        if student_section_key and student_section_key not in available_section_keys:
            matching_sections = [
                item
                for item in parsed_sections
                if str(item.get("class_name", "")).strip().lower() == student_class_name.lower()
                and str(item.get("section", "")).strip().lower() == student_section.lower()
            ]
            if matching_sections:
                matching_sections.sort(
                    key=lambda item: (
                        standard_rank(str(item.get("standard", ""))),
                        str(item.get("standard", "")).lower(),
                    ),
                    reverse=True,
                )
                selected = matching_sections[0]
                selected_standard = str(selected.get("standard", "")).strip()
                selected_section_key = str(selected.get("section_key", "")).strip()
                if selected_standard and selected_standard != student_standard:
                    current_user.profile_standard = selected_standard
                    db.session.commit()
                    widgets["message"] = (
                        "Student profile auto-linked to latest semester standard "
                        f"({selected_standard}) for your class/section."
                    )
                student_standard = selected_standard or student_standard
                student_section_key = selected_section_key

    for table in section_tables:
        if not isinstance(table, dict):
            continue
        section_key = str(table.get("section_key", ""))
        matrix = table.get("timetable")
        if not isinstance(matrix, list):
            continue

        if role_code == "STUDENT" and student_section_key and section_key != student_section_key:
            continue

        for day_index, row in enumerate(matrix):
            if not isinstance(row, list):
                continue
            for period_index, cell in enumerate(row):
                if not isinstance(cell, dict):
                    continue

                if role_code == "FACULTY":
                    teacher_name = str(cell.get("teacher", "")).strip().lower()
                    if teacher_name not in faculty_aliases:
                        continue

                if role_code == "STUDENT" and student_section_key and section_key != student_section_key:
                    continue

                subject_name = str(cell.get("subject", "")).strip()
                room_name = str(cell.get("room", "")).strip()
                teacher_name = str(cell.get("teacher", "")).strip()
                user_records[(day_index, period_index)] = {
                    "subject": subject_name,
                    "room": room_name,
                    "teacher": teacher_name,
                    "period": periods[period_index] if period_index < len(periods) else f"Period {period_index + 1}",
                }

                if day_index == today_index:
                    today_rows.append(
                        {
                            "period": periods[period_index] if period_index < len(periods) else f"Period {period_index + 1}",
                            "period_order": period_index,
                            "subject": subject_name,
                            "room": room_name,
                            "teacher": teacher_name,
                        }
                    )

    today_classes = sum(
        1
        for (day_index, _period_index) in user_records.keys()
        if day_index == today_index
    )
    widgets["today_classes"] = today_classes
    widgets["free_periods"] = max(0, teaching_periods_today - today_classes)

    tomorrow_changes = 0
    for period_index in range(len(periods)):
        today_cell = user_records.get((today_index, period_index))
        tomorrow_cell = user_records.get((tomorrow_index, period_index))
        if today_cell == tomorrow_cell:
            continue
        if today_cell is None and tomorrow_cell is None:
            continue
        tomorrow_changes += 1
    widgets["tomorrow_changes"] = tomorrow_changes

    room_stats = summary.get("room_stats", {}) if isinstance(summary, dict) else {}
    if isinstance(room_stats, dict) and room_stats:
        utilization_values = [
            float(room_data.get("utilization_percent", 0.0))
            for room_data in room_stats.values()
            if isinstance(room_data, dict)
        ]
        if utilization_values:
            widgets["room_utilization"] = round(sum(utilization_values) / len(utilization_values), 2)

    today_rows_sorted = sorted(today_rows, key=lambda item: int(item.get("period_order", 0)))
    widgets["today_rows"] = [
        {
            "period": str(item.get("period", "")),
            "subject": str(item.get("subject", "")),
            "room": str(item.get("room", "")),
            "teacher": str(item.get("teacher", "")),
        }
        for item in today_rows_sorted[:8]
    ]

    if role_code == "FACULTY":
        widgets["message"] = "Personalized faculty view based on your configured profile and aliases."
    elif role_code == "STUDENT":
        if student_section_key:
            if not widgets.get("message"):
                widgets["message"] = f"Personalized student view for {student_section_key}."
        else:
            widgets["message"] = "Set student class/standard/section in User Management for personalized widgets."
    else:
        widgets["message"] = "Administrative overview based on published timetable."

    return widgets


def build_export_options(
    section_tables: List[Dict[str, object]],
    class_tables: List[Dict[str, object]],
    faculty_tables: List[Dict[str, object]],
    room_tables: List[Dict[str, object]],
) -> Dict[str, List[Dict[str, str]]]:
    class_options: List[Dict[str, str]] = []
    for class_table in class_tables:
        class_key = str(class_table.get("class_key", "")).strip()
        if not class_key:
            continue
        class_name = str(class_table.get("class_name", "")).strip()
        standard = str(class_table.get("standard", "")).strip()
        class_options.append(
            {
                "value": class_key,
                "label": f"{class_name} | Std {standard}",
            }
        )

    return {
        "section": [
            {
                "value": str(section_table.get("section_key", "")).strip(),
                "label": str(section_table.get("section_key", "")).strip(),
            }
            for section_table in section_tables
            if isinstance(section_table, dict) and str(section_table.get("section_key", "")).strip()
        ],
        "class": class_options,
        "faculty": [
            {
                "value": str(faculty_table.get("teacher", "")).strip(),
                "label": str(faculty_table.get("teacher", "")).strip(),
            }
            for faculty_table in faculty_tables
            if isinstance(faculty_table, dict) and str(faculty_table.get("teacher", "")).strip()
        ],
        "room": [
            {
                "value": str(room_table.get("room", "")).strip(),
                "label": str(room_table.get("room", "")).strip(),
            }
            for room_table in room_tables
            if isinstance(room_table, dict) and str(room_table.get("room", "")).strip()
        ],
    }


@app.route("/dashboard")
@login_required
def dashboard() -> str:
    role_code = get_current_role_code()
    stats = {
        "users": User.query.count(),
        "departments": Department.query.count(),
        "faculty": FacultyProfile.query.count(),
        "rooms": RoomMaster.query.count(),
        "sections": SectionMaster.query.count(),
        "subjects": SubjectMaster.query.count(),
        "assignments_master": AssignmentMaster.query.count(),
    }
    latest_version = TimetableVersion.query.order_by(TimetableVersion.id.desc()).first()
    latest_published_version = (
        TimetableVersion.query.filter_by(status="published")
        .order_by(TimetableVersion.id.desc())
        .first()
    )
    next_scheduled_version = (
        TimetableVersion.query.filter_by(status="scheduled")
        .order_by(TimetableVersion.effective_from.asc(), TimetableVersion.id.asc())
        .first()
    )
    personal_widgets: Dict[str, object] = {
        "today_label": "",
        "tomorrow_label": "",
        "today_classes": 0,
        "free_periods": 0,
        "tomorrow_changes": 0,
        "room_utilization": 0.0,
        "today_rows": [],
        "message": "",
    }
    if role_code not in {"ADMIN", "HOD"}:
        personal_widgets = build_personal_widgets(latest_published_version, role_code)

    return render_template(
        "dashboard.html",
        role_code=role_code,
        stats=stats,
        latest_version=latest_version,
        latest_published_version=latest_published_version,
        next_scheduled_version=next_scheduled_version,
        personal_widgets=personal_widgets,
    )


def build_timetable_view_context(
    version: TimetableVersion,
    role_code: str,
    view_mode: str,
) -> Dict[str, object] | None:
    payload = version.summary()

    days_raw = payload.get("days")
    periods_raw = payload.get("periods")
    section_tables = payload.get("section_tables")
    summary_raw = payload.get("summary")

    if not isinstance(days_raw, list) or not isinstance(periods_raw, list) or not isinstance(section_tables, list):
        return None

    days = [str(day_name) for day_name in days_raw]
    periods = [str(period_name) for period_name in periods_raw]

    summary_defaults = {
        "section_count": 0,
        "class_count": 0,
        "faculty_count": 0,
        "room_count": 0,
        "total_slots": 0,
        "scheduled_slots": 0,
        "utilization_percent": 0,
        "class_stats": {},
        "faculty_stats": {},
        "room_stats": {},
        "section_stats": {},
        "optimization": {},
    }
    summary = dict(summary_defaults)
    if isinstance(summary_raw, dict):
        summary.update(summary_raw)

    lunch_break_periods_by_day = normalize_lunch_break_periods_by_day_from_summary(
        summary,
        len(days),
        len(periods),
    )

    class_tables = build_class_timetable_tables(section_tables)
    faculty_tables = build_faculty_timetable_tables(
        days,
        periods,
        section_tables,
        lunch_break_periods_by_day,
    )
    room_tables = build_room_timetable_tables(
        days,
        periods,
        section_tables,
        lunch_break_periods=lunch_break_periods_by_day,
    )

    export_options = build_export_options(
        section_tables,
        class_tables,
        faculty_tables,
        room_tables,
    )

    validation_issues_raw = payload.get("validation_issues")
    validation_issues = (
        [str(issue) for issue in validation_issues_raw if str(issue).strip()]
        if isinstance(validation_issues_raw, list)
        else []
    )

    show_timetable_metrics = role_code not in {"FACULTY", "STUDENT"}
    metrics_summary: Dict[str, object] = {}
    if show_timetable_metrics:
        metrics_summary = {
            "section_count": summary.get("section_count", 0),
            "class_count": summary.get("class_count", 0),
            "faculty_count": summary.get("faculty_count", 0),
            "room_count": summary.get("room_count", 0),
            "total_slots": summary.get("total_slots", 0),
            "scheduled_slots": summary.get("scheduled_slots", 0),
            "utilization_percent": summary.get("utilization_percent", 0),
        }

    return {
        "days": days,
        "periods": periods,
        "section_tables": section_tables,
        "class_tables": class_tables,
        "faculty_tables": faculty_tables,
        "room_tables": room_tables,
        "periods_per_day": len(periods),
        "lunch_break_periods_by_day": lunch_break_periods_by_day,
        "lunch_break_description": "",
        "summary": summary,
        "constraint_settings": payload.get("constraint_settings", {}),
        "latest_version": version,
        "role_code": role_code,
        "view_mode": view_mode,
        "validation_issues": validation_issues,
        "show_timetable_metrics": show_timetable_metrics,
        "metrics_summary": metrics_summary,
        "export_options": export_options,
    }


@app.get("/timetable/published")
@login_required
def view_published_timetable() -> str:
    role_code = get_current_role_code()
    published_version = (
        TimetableVersion.query.filter_by(status="published")
        .order_by(TimetableVersion.id.desc())
        .first()
    )
    if published_version is None:
        flash("No published timetable is available yet.", "warning")
        return redirect(url_for("dashboard"))

    context = build_timetable_view_context(published_version, role_code, "published")
    if context is None:
        flash("Published timetable data is incomplete. Please publish a fresh version.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("timetable.html", **context)


@app.get("/timetable/upcoming")
@login_required
def view_upcoming_timetable() -> str:
    role_code = get_current_role_code()
    upcoming_version = (
        TimetableVersion.query.filter_by(status="scheduled")
        .order_by(TimetableVersion.effective_from.asc(), TimetableVersion.id.asc())
        .first()
    )
    if upcoming_version is None:
        flash("No upcoming scheduled timetable is available.", "warning")
        return redirect(url_for("dashboard"))

    context = build_timetable_view_context(upcoming_version, role_code, "upcoming")
    if context is None:
        flash("Upcoming timetable data is incomplete.", "danger")
        return redirect(url_for("dashboard"))
    return render_template("timetable.html", **context)


@app.route("/", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def index() -> str:
    role_code = get_current_role_code()
    form_values = load_default_form_values()

    if request.method == "POST":
        form_values = {
            "working_days": request.form.get("working_days", "5").strip(),
            "periods_per_day": request.form.get("periods_per_day", str(DEFAULT_PERIODS_PER_DAY)).strip(),
            "lunch_break_periods": request.form.get("lunch_break_periods", "").strip(),
            "faculty_daily_max_periods": request.form.get("faculty_daily_max_periods", "4").strip(),
            "faculty_daily_free_period": "1" if parse_checkbox_field(request.form.get("faculty_daily_free_period")) else "0",
            "lab_same_day_subject_threshold": request.form.get("lab_same_day_subject_threshold", "3").strip(),
            "scenario_runs": request.form.get("scenario_runs", "1").strip(),
            "rooms": request.form.get("rooms", "").strip(),
            "assignment_source": request.form.get("assignment_source", "manual").strip().lower(),
            "assignments": request.form.get("assignments", "").strip(),
            "section_classrooms": request.form.get("section_classrooms", "").strip(),
            "faculty_daily_limits": request.form.get("faculty_daily_limits", "").strip(),
            "assignment_master_count": str(AssignmentMaster.query.count()),
        }

        if form_values["assignment_source"] not in {"manual", "master"}:
            form_values["assignment_source"] = "manual"
        generation_scope_description = "All Sections"

        try:
            working_days = parse_integer_field(form_values["working_days"], "Working days", 1, 7)
            periods_per_day = parse_integer_field(
                form_values["periods_per_day"],
                "Periods per day",
                1,
                MAX_PERIODS_PER_DAY,
            )

            lunch_break_periods_by_day = parse_lunch_break_periods(
                form_values["lunch_break_periods"],
                periods_per_day,
                working_days,
            )

            max_teaching_periods_per_day = min_teaching_periods_per_day(
                periods_per_day,
                lunch_break_periods_by_day,
                working_days,
            )
            if max_teaching_periods_per_day <= 0:
                raise ValueError("Lunch break periods cannot cover all periods. Keep at least one teaching period.")

            faculty_daily_default_max = parse_integer_field(
                form_values["faculty_daily_max_periods"],
                "Faculty daily max periods",
                1,
                max_teaching_periods_per_day,
            )
            require_daily_free_period = form_values["faculty_daily_free_period"] == "1"
            lab_same_day_subject_threshold = parse_integer_field(
                form_values["lab_same_day_subject_threshold"] or "3",
                "LAB same-day threshold",
                1,
                20,
            )

            scenario_runs = parse_integer_field(
                form_values["scenario_runs"] or "1",
                "Scenario runs",
                1,
                12,
            )

            rooms = split_non_empty_lines(form_values["rooms"])
            if not rooms:
                raise ValueError("Please provide at least one room.")

            assignment_payload, resolved_assignments_text, resolved_assignment_source = resolve_assignment_payload(
                form_values["assignments"],
                form_values.get("assignment_source", "manual"),
            )
            form_values["assignments"] = resolved_assignments_text
            form_values["assignment_source"] = resolved_assignment_source

            section_home_rooms = parse_section_classrooms(form_values["section_classrooms"], rooms)
            faculty_daily_limits = parse_faculty_daily_limits(
                form_values["faculty_daily_limits"],
                max_teaching_periods_per_day,
            )
            validate_lab_allowed_rooms_against_rooms(assignment_payload, rooms)

            scenario_results: List[Dict[str, object]] = []
            days: List[str]
            periods: List[str]
            section_tables: List[Dict[str, object]]
            class_tables: List[Dict[str, object]]
            faculty_tables: List[Dict[str, object]]
            room_tables: List[Dict[str, object]]
            summary: Dict[str, object]
            validation_issues: List[str]

            if scenario_runs > 1:
                seed_base = random.randint(1, 900000)
                successful_scenarios: List[Dict[str, object]] = []

                for scenario_index in range(scenario_runs):
                    scenario_seed = seed_base + scenario_index
                    try:
                        (
                            scenario_days,
                            scenario_periods,
                            scenario_section_tables,
                            scenario_class_tables,
                            scenario_faculty_tables,
                            scenario_room_tables,
                            scenario_summary,
                            scenario_issues,
                        ) = generate_outputs(
                            assignment_payload=assignment_payload,
                            rooms=rooms,
                            working_days=working_days,
                            periods_per_day=periods_per_day,
                            lunch_break_periods_by_day=lunch_break_periods_by_day,
                            section_home_rooms=section_home_rooms,
                            faculty_daily_default_max=faculty_daily_default_max,
                            faculty_daily_limits=faculty_daily_limits,
                            lab_same_day_subject_threshold=lab_same_day_subject_threshold,
                            random_seed=scenario_seed,
                            require_daily_free_period=require_daily_free_period,
                            write_output_files=False,
                        )

                        scenario_rank = rank_scenario_candidate(scenario_summary, scenario_issues)
                        successful_scenarios.append(
                            {
                                "seed": scenario_seed,
                                "rank": scenario_rank,
                                "days": scenario_days,
                                "periods": scenario_periods,
                                "section_tables": scenario_section_tables,
                                "class_tables": scenario_class_tables,
                                "faculty_tables": scenario_faculty_tables,
                                "room_tables": scenario_room_tables,
                                "summary": scenario_summary,
                                "issues": scenario_issues,
                            }
                        )
                        scenario_results.append(
                            {
                                "seed": scenario_seed,
                                "status": "ok",
                                "rank": scenario_rank,
                                "score": scenario_summary.get("optimization", {}).get("score", 0),
                                "utilization_percent": scenario_summary.get("utilization_percent", 0),
                                "issue_count": len(scenario_issues),
                            }
                        )
                    except ValueError as scenario_error:
                        scenario_results.append(
                            {
                                "seed": scenario_seed,
                                "status": "failed",
                                "reason": str(scenario_error),
                            }
                        )

                if not successful_scenarios:
                    raise ValueError("All scenario runs failed. Review diagnostics and retry.")

                successful_scenarios.sort(key=lambda item: float(item["rank"]), reverse=True)
                best_scenario = successful_scenarios[0]

                days = [str(day) for day in best_scenario["days"]]
                periods = [str(period) for period in best_scenario["periods"]]
                section_tables = list(best_scenario["section_tables"])
                class_tables = list(best_scenario["class_tables"])
                faculty_tables = list(best_scenario["faculty_tables"])
                room_tables = list(best_scenario["room_tables"])
                summary = dict(best_scenario["summary"])
                validation_issues = list(best_scenario["issues"])
                validation_issues.extend(
                    write_generated_output_files(
                        days,
                        periods,
                        section_tables,
                        class_tables,
                        faculty_tables,
                        room_tables,
                        summary,
                        lunch_break_periods_by_day,
                    )
                )

                summary["scenario_compare"] = {
                    "runs": scenario_runs,
                    "best_seed": best_scenario["seed"],
                    "best_rank": best_scenario["rank"],
                }
            else:
                days, periods, section_tables, class_tables, faculty_tables, room_tables, summary, validation_issues = generate_outputs(
                    assignment_payload=assignment_payload,
                    rooms=rooms,
                    working_days=working_days,
                    periods_per_day=periods_per_day,
                    lunch_break_periods_by_day=lunch_break_periods_by_day,
                    section_home_rooms=section_home_rooms,
                    faculty_daily_default_max=faculty_daily_default_max,
                    faculty_daily_limits=faculty_daily_limits,
                    lab_same_day_subject_threshold=lab_same_day_subject_threshold,
                    random_seed=None,
                    require_daily_free_period=require_daily_free_period,
                    write_output_files=True,
                )

            for issue in validation_issues:
                flash(issue, "warning")

            lunch_break_description = format_lunch_break_description(days, lunch_break_periods_by_day)

            constraint_settings = {
                "faculty_daily_default_max": faculty_daily_default_max,
                "faculty_daily_limits": faculty_daily_limits,
                "assignment_source": resolved_assignment_source,
                "require_daily_free_period": require_daily_free_period,
                "lab_same_day_subject_threshold": lab_same_day_subject_threshold,
                "scenario_runs": scenario_runs,
            }

            latest_version = persist_timetable_version(
                days=days,
                periods=periods,
                section_tables=section_tables,
                summary=summary,
                constraint_settings=constraint_settings,
                generation_scope_description=generation_scope_description,
                validation_issues=validation_issues,
            )

            log_audit_event(
                action="TIMETABLE_GENERATED",
                target_type="TIMETABLE_VERSION",
                target_id=str(latest_version.id),
                details={
                    "version_label": latest_version.version_label,
                    "assignment_source": resolved_assignment_source,
                    "scheduled_slots": summary.get("scheduled_slots", 0),
                    "utilization_percent": summary.get("utilization_percent", 0),
                    "scenario_runs": scenario_runs,
                },
            )
            db.session.commit()

            if scenario_runs > 1:
                flash("Scenario comparison completed. Best run selected automatically.", "success")
            else:
                flash("Timetable generated successfully.", "success")

            return render_template(
                "timetable.html",
                days=days,
                periods=periods,
                section_tables=section_tables,
                class_tables=class_tables,
                faculty_tables=faculty_tables,
                room_tables=room_tables,
                export_options=build_export_options(section_tables, class_tables, faculty_tables, room_tables),
                periods_per_day=periods_per_day,
                lunch_break_periods_by_day={
                    day_index: sorted(periods_set)
                    for day_index, periods_set in lunch_break_periods_by_day.items()
                },
                lunch_break_description=lunch_break_description,
                summary=summary,
                constraint_settings=constraint_settings,
                latest_version=latest_version,
                role_code=role_code,
                view_mode="generated",
                validation_issues=validation_issues,
                scenario_results=scenario_results,
                edit_locked=False,
            )
        except ValueError as error:
            flash(str(error), "danger")

            for issue in build_generation_failure_diagnostics(
                form_values,
                generation_scope_description,
            ):
                flash(issue, "warning")

            for suggestion in build_generation_fix_suggestions(
                form_values,
                generation_scope_description,
            ):
                flash(suggestion, "info")

    return render_template(
        "index.html",
        form_values=form_values,
        default_periods_per_day=DEFAULT_PERIODS_PER_DAY,
        max_periods_per_day=MAX_PERIODS_PER_DAY,
    )


@app.get("/timetable/export/pdf")
@login_required
def export_timetable_pdf() -> Response:
    version, error_message = resolve_export_version(request.args.get("version_id", ""))
    if version is None:
        flash(error_message, "danger")
        return _export_redirect_fallback()

    view_kind = request.args.get("view_kind", "all").strip().lower() or "all"
    selection_mode = request.args.get("selection_mode", "all").strip().lower() or "all"
    export_format = request.args.get("export_format", "pdf").strip().lower() or "pdf"
    selected_targets = _normalize_export_targets(
        request.args.getlist("selected_target"),
        request.args.get("selected_targets", ""),
    )

    if view_kind not in {"all", "section", "class", "faculty", "room"}:
        flash("Invalid export category.", "danger")
        return _export_redirect_fallback()

    if selection_mode not in {"all", "single", "multiple"}:
        flash("Invalid export selection mode.", "danger")
        return _export_redirect_fallback()

    if export_format not in {"pdf", "jpg"}:
        flash("Export format must be PDF or JPG.", "danger")
        return _export_redirect_fallback()

    payload = version.summary()
    cards, days, periods, lunch_break_periods_by_day, extract_error = _extract_export_cards(
        payload,
        view_kind=view_kind,
        selection_mode=selection_mode,
        selected_targets=selected_targets,
    )
    if extract_error:
        flash(extract_error, "warning")
        return _export_redirect_fallback()

    if selection_mode == "single" and len(selected_targets) != 1:
        flash("Single export mode requires exactly one selected target.", "warning")
        return _export_redirect_fallback()

    if export_format == "jpg" and len(cards) != 1:
        flash("JPG export is available only for a single timetable card.", "warning")
        return _export_redirect_fallback()

    file_bytes: bytes | None = None
    build_error = ""
    download_extension = "pdf"
    mime_type = "application/pdf"

    if export_format == "jpg":
        file_bytes, build_error = _build_jpg_for_card(
            cards[0],
            days,
            periods,
            lunch_break_periods_by_day,
        )
        download_extension = "jpg"
        mime_type = "image/jpeg"
    else:
        file_bytes, build_error = _build_pdf_for_cards(
            version,
            cards,
            days,
            periods,
            lunch_break_periods_by_day,
        )

    if file_bytes is None:
        flash(build_error or "Failed to build export file.", "warning")
        return _export_redirect_fallback()

    try:
        log_audit_event(
            action="TIMETABLE_EXPORTED",
            target_type="TIMETABLE_VERSION",
            target_id=str(version.id),
            details={
                "version_label": version.version_label,
                "status": version.status,
                "view_kind": view_kind,
                "selection_mode": selection_mode,
                "selected_targets": selected_targets,
                "export_format": export_format,
                "cards_exported": len(cards),
            },
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    return send_file(
        io.BytesIO(file_bytes),
        mimetype=mime_type,
        as_attachment=True,
        download_name=_build_export_filename(version, download_extension),
    )


@app.route("/api/timetable/latest")
@login_required
def latest_timetable_api():
    if not OUTPUT_JSON_FILE.exists():
        return jsonify({"message": "Generate a timetable first."}), 404

    with OUTPUT_JSON_FILE.open("r", encoding="utf-8") as timetable_file:
        payload = json.load(timetable_file)

    return jsonify(payload)


@app.route("/api/timetable/class/latest")
@login_required
def latest_class_timetable_api():
    if not OUTPUT_CLASS_JSON_FILE.exists():
        return jsonify({"message": "Generate a timetable first."}), 404

    with OUTPUT_CLASS_JSON_FILE.open("r", encoding="utf-8") as timetable_file:
        payload = json.load(timetable_file)

    return jsonify(payload)


@app.route("/api/timetable/room/latest")
@login_required
def latest_room_timetable_api():
    if not OUTPUT_ROOM_JSON_FILE.exists():
        return jsonify({"message": "Generate a timetable first."}), 404

    with OUTPUT_ROOM_JSON_FILE.open("r", encoding="utf-8") as timetable_file:
        payload = json.load(timetable_file)

    return jsonify(payload)


@app.route("/api/timetable/faculty/latest")
@login_required
def latest_faculty_timetable_api():
    if not OUTPUT_FACULTY_JSON_FILE.exists():
        return jsonify({"message": "Generate a timetable first."}), 404

    with OUTPUT_FACULTY_JSON_FILE.open("r", encoding="utf-8") as timetable_file:
        payload = json.load(timetable_file)

    return jsonify(payload)


@app.get("/admin/versions")
@roles_required("ADMIN", "HOD")
def list_timetable_versions() -> str:
    versions = TimetableVersion.query.order_by(TimetableVersion.id.desc()).limit(100).all()
    return render_template(
        "versions_compare.html",
        versions=versions,
        selected_a="",
        selected_b="",
        version_a=None,
        version_b=None,
        compare_result=None,
    )


@app.get("/admin/versions/compare")
@roles_required("ADMIN", "HOD")
def compare_timetable_versions() -> str:
    versions = TimetableVersion.query.order_by(TimetableVersion.id.desc()).limit(100).all()
    selected_a = request.args.get("version_a", "").strip()
    selected_b = request.args.get("version_b", "").strip()

    version_a = None
    version_b = None
    compare_result = None

    if not selected_a or not selected_b:
        flash("Select two versions to compare.", "warning")
        return render_template(
            "versions_compare.html",
            versions=versions,
            selected_a=selected_a,
            selected_b=selected_b,
            version_a=version_a,
            version_b=version_b,
            compare_result=compare_result,
        )

    try:
        version_a_id = int(selected_a)
        version_b_id = int(selected_b)
    except ValueError:
        flash("Version IDs must be numeric.", "danger")
        return render_template(
            "versions_compare.html",
            versions=versions,
            selected_a=selected_a,
            selected_b=selected_b,
            version_a=version_a,
            version_b=version_b,
            compare_result=compare_result,
        )

    if version_a_id == version_b_id:
        flash("Please choose two different versions.", "warning")
        return render_template(
            "versions_compare.html",
            versions=versions,
            selected_a=selected_a,
            selected_b=selected_b,
            version_a=version_a,
            version_b=version_b,
            compare_result=compare_result,
        )

    version_a = db.session.get(TimetableVersion, version_a_id)
    version_b = db.session.get(TimetableVersion, version_b_id)
    if version_a is None or version_b is None:
        flash("One or both selected versions were not found.", "danger")
        return render_template(
            "versions_compare.html",
            versions=versions,
            selected_a=selected_a,
            selected_b=selected_b,
            version_a=version_a,
            version_b=version_b,
            compare_result=compare_result,
        )

    payload_a = version_a.summary()
    payload_b = version_b.summary()
    if not isinstance(payload_a.get("section_tables"), list) or not isinstance(payload_b.get("section_tables"), list):
        flash("Selected version payload does not contain comparable timetable snapshots.", "danger")
    else:
        compare_result = compare_version_payloads(payload_a, payload_b)

    return render_template(
        "versions_compare.html",
        versions=versions,
        selected_a=selected_a,
        selected_b=selected_b,
        version_a=version_a,
        version_b=version_b,
        compare_result=compare_result,
    )


@app.get("/admin/versions/<int:version_id>/view")
@roles_required("ADMIN", "HOD")
def view_timetable_version(version_id: int) -> str:
    role_code = get_current_role_code()
    version = db.session.get(TimetableVersion, version_id)
    if version is None:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("list_timetable_versions"))

    context = build_timetable_view_context(version, role_code, "version")
    if context is None:
        flash("Selected version does not contain renderable timetable data.", "danger")
        return redirect(url_for("list_timetable_versions"))

    return render_template("timetable.html", **context)


@app.post("/admin/versions/<int:version_id>/manual-edit")
@roles_required("ADMIN", "HOD")
def manual_edit_timetable_version(version_id: int) -> str:
    source_version = db.session.get(TimetableVersion, version_id)
    if source_version is None:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("list_timetable_versions"))

    if source_version.status != "draft":
        flash("Manual edit is allowed only for draft versions.", "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    payload = source_version.summary()
    try:
        prepared_payload = prepare_timetable_payload_for_render(payload)
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    days = [str(day_name) for day_name in prepared_payload["days"]]
    periods = [str(period_name) for period_name in prepared_payload["periods"]]
    lunch_break_periods_by_day = {
        int(day_index): [int(period_number) for period_number in period_numbers]
        for day_index, period_numbers in prepared_payload["lunch_break_periods_by_day"].items()
    }
    section_tables = json.loads(json.dumps(prepared_payload["section_tables"]))

    try:
        day_number = parse_integer_field(request.form.get("day_index", "").strip(), "Day", 1, len(days))
        period_number = parse_integer_field(
            request.form.get("period_index", "").strip(),
            "Period",
            1,
            len(periods),
        )
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    day_index = day_number - 1
    period_index = period_number - 1

    day_label = days[day_index] if day_index < len(days) else f"Day {day_number}"
    period_label = periods[period_index] if period_index < len(periods) else f"Period {period_number}"

    if period_number in lunch_break_periods_by_day.get(day_index, []):
        flash(f"Cannot edit {day_label}, {period_label} because it is a lunch-break slot.", "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    edit_source = request.form.get("edit_source", "section").strip().lower()
    if edit_source not in {"section", "faculty"}:
        edit_source = "section"

    target_section_key = ""
    faculty_name = request.form.get("faculty_name", "").strip()
    if edit_source == "faculty":
        if not faculty_name:
            flash("Select a faculty name when editing through faculty timetable.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        slot_matches = resolve_faculty_slot_matches(
            section_tables,
            faculty_name,
            day_index,
            period_index,
        )

        if not slot_matches:
            flash(
                f"No allocation exists for faculty {faculty_name} at {day_label}, {period_label} in this version.",
                "danger",
            )
            return redirect(url_for("view_timetable_version", version_id=version_id))

        if len(slot_matches) > 1:
            flash(
                f"Cannot edit via faculty slot because {faculty_name} has multiple allocations at {day_label}, {period_label}.",
                "danger",
            )
            for match in slot_matches[:8]:
                flash(
                    f"Conflict detail: {match['section_key']} -> {match['subject']} in {match['room'] or 'N/A'}",
                    "warning",
                )
            return redirect(url_for("view_timetable_version", version_id=version_id))

        target_section_key = str(slot_matches[0].get("section_key", "")).strip()
    else:
        target_section_key = request.form.get("section_key", "").strip()

    if not target_section_key:
        flash("Choose a section to edit.", "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    target_section = find_section_table_by_key(section_tables, target_section_key)
    if target_section is None:
        flash("Selected section was not found in this timetable version.", "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    timetable = target_section.get("timetable")
    if not isinstance(timetable, list) or day_index >= len(timetable):
        flash("Selected day does not exist in the target section timetable.", "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    day_row = timetable[day_index]
    if not isinstance(day_row, list) or period_index >= len(day_row):
        flash("Selected period does not exist in the target section timetable.", "danger")
        return redirect(url_for("view_timetable_version", version_id=version_id))

    edit_action = request.form.get("edit_action", "theory").strip().lower()
    if edit_action not in {"clear", "theory", "lab_double", "move", "lock_slot", "unlock_slot"}:
        edit_action = "theory"

    target_slots: Set[Tuple[str, int, int]] = set()
    edited_subject = ""
    edited_teacher = ""
    edited_room = ""
    move_from_section_key = ""
    move_from_day_label = ""
    move_from_period_label = ""
    should_validate_conflicts = True

    if edit_action == "move":
        move_from_section_key = request.form.get("source_section_key", "").strip()
        if not move_from_section_key:
            flash("Move action requires a source section slot.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        try:
            source_day_number = parse_integer_field(
                request.form.get("source_day_index", "").strip(),
                "Source day",
                1,
                len(days),
            )
            source_period_number = parse_integer_field(
                request.form.get("source_period_index", "").strip(),
                "Source period",
                1,
                len(periods),
            )
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        source_day_index = source_day_number - 1
        source_period_index = source_period_number - 1
        move_from_day_label = days[source_day_index] if source_day_index < len(days) else f"Day {source_day_number}"
        move_from_period_label = (
            periods[source_period_index]
            if source_period_index < len(periods)
            else f"Period {source_period_number}"
        )

        if source_period_number in lunch_break_periods_by_day.get(source_day_index, []):
            flash(
                f"Cannot move from {move_from_day_label}, {move_from_period_label} because it is a lunch-break slot.",
                "danger",
            )
            return redirect(url_for("view_timetable_version", version_id=version_id))

        source_section = find_section_table_by_key(section_tables, move_from_section_key)
        if source_section is None:
            flash("Source section was not found in this timetable version.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        source_timetable = source_section.get("timetable")
        if not isinstance(source_timetable, list) or source_day_index >= len(source_timetable):
            flash("Source day does not exist in source section timetable.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        source_day_row = source_timetable[source_day_index]
        if not isinstance(source_day_row, list) or source_period_index >= len(source_day_row):
            flash("Source period does not exist in source section timetable.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        source_cell = source_day_row[source_period_index]
        if not isinstance(source_cell, dict):
            flash("Source slot is empty. Select an occupied slot to move.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        source_is_lab = bool(source_cell.get("is_lab", False))
        source_session_length = int(source_cell.get("session_length", 1) or 1)
        source_session_part = int(source_cell.get("session_part", 1) or 1)

        source_slot_indexes: Set[int] = {source_period_index}
        if source_is_lab and source_session_length == 2:
            source_pair_period = find_lab_pair_period_index(source_day_row, source_period_index)
            if source_pair_period is None:
                flash("Source LAB slot is incomplete and cannot be moved safely.", "danger")
                return redirect(url_for("view_timetable_version", version_id=version_id))
            source_slot_indexes.add(source_pair_period)
            if source_session_part == 2:
                source_period_index = source_pair_period

        for source_slot_index in source_slot_indexes:
            source_slot_cell = source_day_row[source_slot_index]
            if isinstance(source_slot_cell, dict) and bool(source_slot_cell.get("is_locked", False)):
                locked_period_label = (
                    periods[source_slot_index]
                    if source_slot_index < len(periods)
                    else f"Period {source_slot_index + 1}"
                )
                flash(
                    f"Cannot move from {move_from_day_label}, {locked_period_label} because the slot is locked.",
                    "danger",
                )
                return redirect(url_for("view_timetable_version", version_id=version_id))

        target_day_row = day_row
        target_period_indexes: List[int] = [period_index]
        if source_is_lab and source_session_length == 2:
            second_target_period = period_index + 1
            if second_target_period >= len(periods):
                flash("LAB block move requires two contiguous target periods.", "danger")
                return redirect(url_for("view_timetable_version", version_id=version_id))
            if (second_target_period + 1) in lunch_break_periods_by_day.get(day_index, []):
                flash("LAB block move cannot overlap lunch break periods.", "danger")
                return redirect(url_for("view_timetable_version", version_id=version_id))
            target_period_indexes.append(second_target_period)

        for target_period in target_period_indexes:
            target_cell = target_day_row[target_period]
            if not isinstance(target_cell, dict):
                continue

            if bool(target_cell.get("is_locked", False)):
                target_period_label = periods[target_period] if target_period < len(periods) else f"Period {target_period + 1}"
                flash(
                    f"Cannot move slot to {day_label}, {target_period_label} because target is locked.",
                    "danger",
                )
                return redirect(url_for("view_timetable_version", version_id=version_id))

            can_overwrite_from_source = (
                target_section_key == move_from_section_key
                and day_index == source_day_index
                and target_period in source_slot_indexes
            )
            if not can_overwrite_from_source:
                target_period_label = periods[target_period] if target_period < len(periods) else f"Period {target_period + 1}"
                flash(
                    f"Cannot move slot to {day_label}, {target_period_label} because target is already occupied.",
                    "danger",
                )
                return redirect(url_for("view_timetable_version", version_id=version_id))

        edited_subject = str(source_cell.get("subject", "")).strip()
        edited_teacher = str(source_cell.get("teacher", "")).strip()
        edited_room = str(source_cell.get("room", "")).strip()
        if not edited_subject or not edited_teacher or not edited_room:
            flash("Source slot must include subject, faculty, and room to move.", "danger")
            return redirect(url_for("view_timetable_version", version_id=version_id))

        for source_slot_index in source_slot_indexes:
            source_day_row[source_slot_index] = None

        new_session_id = f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        for target_offset, target_period in enumerate(target_period_indexes):
            target_day_row[target_period] = build_manual_edit_cell(
                target_section,
                edited_subject,
                edited_teacher,
                edited_room,
                is_lab=source_is_lab and source_session_length == 2,
                session_length=2 if source_is_lab and source_session_length == 2 else 1,
                session_part=(target_offset + 1) if source_is_lab and source_session_length == 2 else 1,
                session_id=new_session_id,
            )
            target_slots.add((target_section_key, day_index, target_period))
    else:
        target_slots = {(target_section_key, day_index, period_index)}
        existing_pair_period = find_lab_pair_period_index(day_row, period_index)
        if existing_pair_period is not None:
            target_slots.add((target_section_key, day_index, existing_pair_period))

        target_cell = day_row[period_index] if period_index < len(day_row) else None
        target_is_locked = bool(target_cell.get("is_locked", False)) if isinstance(target_cell, dict) else False
        pair_is_locked = False
        if existing_pair_period is not None:
            pair_cell = day_row[existing_pair_period]
            pair_is_locked = bool(pair_cell.get("is_locked", False)) if isinstance(pair_cell, dict) else False

        if edit_action in {"clear", "theory", "lab_double"} and (target_is_locked or pair_is_locked):
            flash(
                f"Cannot modify {target_section_key} at {day_label}, {period_label} because the slot is locked.",
                "danger",
            )
            return redirect(url_for("view_timetable_version", version_id=version_id))

        if edit_action in {"lock_slot", "unlock_slot"}:
            if not isinstance(target_cell, dict):
                flash("Only occupied slots can be locked or unlocked.", "danger")
                return redirect(url_for("view_timetable_version", version_id=version_id))

            desired_locked_state = edit_action == "lock_slot"
            target_cell["is_locked"] = desired_locked_state
            if existing_pair_period is not None:
                pair_cell = day_row[existing_pair_period]
                if isinstance(pair_cell, dict):
                    pair_cell["is_locked"] = desired_locked_state

            should_validate_conflicts = False
            edited_subject = str(target_cell.get("subject", "")).strip()
            edited_teacher = str(target_cell.get("teacher", "")).strip()
            edited_room = str(target_cell.get("room", "")).strip()
            target_slots = set()

        elif edit_action == "clear":
            day_row[period_index] = None
            if existing_pair_period is not None:
                day_row[existing_pair_period] = None
        else:
            edited_subject = request.form.get("subject", "").strip()
            edited_teacher = request.form.get("teacher", "").strip()
            edited_room = request.form.get("room", "").strip()

            if not edited_subject or not edited_teacher or not edited_room:
                flash("Subject, faculty, and room are required for theory/lab edits.", "danger")
                return redirect(url_for("view_timetable_version", version_id=version_id))

            if existing_pair_period is not None:
                day_row[existing_pair_period] = None

            if edit_action == "lab_double":
                second_period_index = period_index + 1
                if second_period_index >= len(periods):
                    flash("LAB block requires two contiguous periods. Select a starting period before the last period.", "danger")
                    return redirect(url_for("view_timetable_version", version_id=version_id))

                if (second_period_index + 1) in lunch_break_periods_by_day.get(day_index, []):
                    flash("LAB block cannot overlap lunch break periods.", "danger")
                    return redirect(url_for("view_timetable_version", version_id=version_id))

                second_cell = day_row[second_period_index]
                second_pair_period = find_lab_pair_period_index(day_row, second_period_index)

                can_overwrite_second = second_cell is None or second_period_index == existing_pair_period
                if not can_overwrite_second:
                    flash(
                        f"Cannot create LAB block at {day_label}, {period_label}: next slot is already occupied.",
                        "danger",
                    )
                    return redirect(url_for("view_timetable_version", version_id=version_id))

                if second_pair_period is not None and second_pair_period != period_index:
                    flash(
                        f"Cannot create LAB block at {day_label}, {period_label}: next slot belongs to another LAB session.",
                        "danger",
                    )
                    return redirect(url_for("view_timetable_version", version_id=version_id))

                session_id = f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                day_row[period_index] = build_manual_edit_cell(
                    target_section,
                    edited_subject,
                    edited_teacher,
                    edited_room,
                    is_lab=True,
                    session_length=2,
                    session_part=1,
                    session_id=session_id,
                )
                day_row[second_period_index] = build_manual_edit_cell(
                    target_section,
                    edited_subject,
                    edited_teacher,
                    edited_room,
                    is_lab=True,
                    session_length=2,
                    session_part=2,
                    session_id=session_id,
                )
                target_slots.add((target_section_key, day_index, second_period_index))
            else:
                session_id = f"manual-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                day_row[period_index] = build_manual_edit_cell(
                    target_section,
                    edited_subject,
                    edited_teacher,
                    edited_room,
                    is_lab=False,
                    session_length=1,
                    session_part=1,
                    session_id=session_id,
                    is_locked=False,
                )

    if should_validate_conflicts:
        conflict_messages = collect_manual_edit_conflicts(
            section_tables,
            target_slots,
            lunch_break_periods_by_day,
            days,
            periods,
        )
        if conflict_messages:
            flash("Manual edit was rejected due to timetable conflicts:", "danger")
            for issue in conflict_messages[:12]:
                flash(issue, "warning")
            if len(conflict_messages) > 12:
                flash(f"{len(conflict_messages) - 12} additional conflicts were omitted from this preview.", "warning")
            return redirect(url_for("view_timetable_version", version_id=version_id))

    updated_payload = dict(payload)
    updated_payload["days"] = days
    updated_payload["periods"] = periods
    updated_payload["section_tables"] = section_tables

    prepared_updated = prepare_timetable_payload_for_render(updated_payload)
    updated_summary = prepared_updated["summary"]

    edit_note = request.form.get("edit_note", "").strip()
    edit_details = {
        "source_version_id": source_version.id,
        "source_version_label": source_version.version_label,
        "edit_source": edit_source,
        "target_section_key": target_section_key,
        "day": day_label,
        "period": period_label,
        "action": edit_action,
        "subject": edited_subject,
        "teacher": edited_teacher,
        "room": edited_room,
        "note": edit_note,
        "edited_by": current_user.full_name if current_user.is_authenticated else "System",
        "edited_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    if edit_action == "move":
        edit_details["move_from_section_key"] = move_from_section_key
        edit_details["move_from_day"] = move_from_day_label
        edit_details["move_from_period"] = move_from_period_label

    existing_edit_log = payload.get("manual_edit_log")
    manual_edit_log: List[Dict[str, object]] = []
    if isinstance(existing_edit_log, list):
        for item in existing_edit_log:
            if isinstance(item, dict):
                manual_edit_log.append(item)
    manual_edit_log.append(edit_details)

    constraint_settings = payload.get("constraint_settings")
    if not isinstance(constraint_settings, dict):
        constraint_settings = {}

    updated_payload["summary"] = updated_summary
    updated_payload["constraint_settings"] = constraint_settings
    updated_payload["validation_issues"] = []
    updated_payload["manual_edit_log"] = manual_edit_log
    source_version.summary_json = json.dumps(updated_payload)

    log_audit_event(
        action="TIMETABLE_MANUAL_EDIT",
        target_type="TIMETABLE_VERSION",
        target_id=str(source_version.id),
        details=edit_details,
    )
    db.session.commit()

    flash(
        f"Manual edit saved in version {source_version.version_label}. "
        "All class/faculty/room/section views are synchronized from this updated snapshot.",
        "success",
    )
    return redirect(url_for("view_timetable_version", version_id=source_version.id))


@app.route("/admin/versions/<int:version_id>/approve", methods=["POST"])
@roles_required("ADMIN", "HOD")
def approve_timetable_version(version_id: int) -> str:
    version = db.session.get(TimetableVersion, version_id)
    if version is None:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))

    if version.status != "draft":
        flash(f"Version is already {version.status}. Cannot approve.", "warning")
        return redirect(url_for("dashboard"))

    approval_comment = request.form.get("approval_comment", "").strip()
    version.status = "approved"
    version.approved_by_user_id = current_user.id
    version.approved_at = datetime.now(timezone.utc)
    version.approval_comment = approval_comment or None

    sent, notify_status = notify_users_for_version_event(
        version,
        "Approved",
        approval_comment,
    )

    log_audit_event(
        action="VERSION_APPROVED",
        target_type="TIMETABLE_VERSION",
        target_id=str(version.id),
        details={
            "version_label": version.version_label,
            "comment": approval_comment,
            "email_sent": sent,
            "email_status": notify_status,
            "change_summary": version.notification_summary or "",
        },
    )
    db.session.commit()

    flash(f"Timetable version {version.version_label} has been approved.", "success")
    if not sent:
        flash(f"Approval email notification skipped/failed: {notify_status}", "warning")
    return redirect(url_for("dashboard"))


@app.route("/admin/versions/<int:version_id>/reject", methods=["POST"])
@roles_required("ADMIN", "HOD")
def reject_timetable_version(version_id: int) -> str:
    version = db.session.get(TimetableVersion, version_id)
    if version is None:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))

    if version.status not in {"draft", "approved"}:
        flash(f"Cannot reject version in {version.status} state.", "warning")
        return redirect(url_for("dashboard"))

    rejection_comment = request.form.get("rejection_comment", "").strip()
    version.status = "rejected"
    version.rejected_by_user_id = current_user.id
    version.rejected_at = datetime.now(timezone.utc)
    version.rejection_comment = rejection_comment or None

    sent, notify_status = notify_users_for_version_event(
        version,
        "Rejected",
        rejection_comment,
    )

    log_audit_event(
        action="VERSION_REJECTED",
        target_type="TIMETABLE_VERSION",
        target_id=str(version.id),
        details={
            "version_label": version.version_label,
            "comment": rejection_comment,
            "email_sent": sent,
            "email_status": notify_status,
            "change_summary": version.notification_summary or "",
        },
    )
    db.session.commit()

    flash(f"Timetable version {version.version_label} has been rejected.", "info")
    if not sent:
        flash(f"Rejection email notification skipped/failed: {notify_status}", "warning")
    return redirect(url_for("dashboard"))


@app.route("/admin/versions/<int:version_id>/publish", methods=["POST"])
@roles_required("ADMIN")
def publish_timetable_version(version_id: int) -> str:
    version = db.session.get(TimetableVersion, version_id)
    if version is None:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))

    if version.status == "published":
        flash(f"Version {version.version_label} is already published.", "info")
        return redirect(url_for("dashboard"))

    if version.status not in {"approved", "scheduled"}:
        flash(f"Can only publish approved versions. Current status: {version.status}.", "danger")
        return redirect(url_for("dashboard"))

    go_live_date_raw = request.form.get("go_live_date", "").strip()
    publish_comment = request.form.get("publish_comment", "").strip()

    effective_from: datetime | None = None
    if go_live_date_raw:
        try:
            parsed_date = datetime.strptime(go_live_date_raw, "%Y-%m-%d")
            effective_from = parsed_date.replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Go-live date must be in YYYY-MM-DD format.", "danger")
            return redirect(url_for("dashboard"))

    now_utc = datetime.now(timezone.utc)
    version.publish_comment = publish_comment or None

    if effective_from is not None and effective_from > now_utc:
        version.status = "scheduled"
        version.effective_from = effective_from
        version.published_by_user_id = current_user.id

        sent, notify_status = notify_users_for_version_event(
            version,
            "Scheduled",
            publish_comment,
        )

        log_audit_event(
            action="VERSION_SCHEDULED",
            target_type="TIMETABLE_VERSION",
            target_id=str(version.id),
            details={
                "version_label": version.version_label,
                "effective_from": format_effective_timestamp(effective_from),
                "comment": publish_comment,
                "email_sent": sent,
                "email_status": notify_status,
                "change_summary": version.notification_summary or "",
            },
        )
        db.session.commit()

        flash(
            f"Timetable version {version.version_label} scheduled for activation on {format_effective_timestamp(effective_from)}.",
            "success",
        )
        if not sent:
            flash(f"Schedule email notification skipped/failed: {notify_status}", "warning")
        return redirect(url_for("dashboard"))

    TimetableVersion.query.filter_by(status="published").update({"status": "archived"})

    version.status = "published"
    version.effective_from = now_utc
    version.published_by_user_id = current_user.id
    version.published_at = now_utc
    version.activated_at = now_utc

    export_error = ""
    try:
        exported, export_status = publish_version_outputs(version)
        if not exported:
            export_error = export_status
    except Exception as error:
        export_error = str(error)

    sent, notify_status = notify_users_for_version_event(
        version,
        "Published",
        publish_comment,
    )

    log_audit_event(
        action="VERSION_PUBLISHED",
        target_type="TIMETABLE_VERSION",
        target_id=str(version.id),
        details={
            "version_label": version.version_label,
            "effective_from": format_effective_timestamp(version.effective_from),
            "comment": publish_comment,
            "email_sent": sent,
            "email_status": notify_status,
            "export_error": export_error,
            "change_summary": version.notification_summary or "",
        },
    )
    db.session.commit()

    if export_error:
        flash(f"Version published but export failed: {export_error}", "warning")

    flash(f"Timetable version {version.version_label} has been published and is now visible to all users.", "success")
    if not sent:
        flash(f"Publish email notification skipped/failed: {notify_status}", "warning")
    return redirect(url_for("dashboard"))


@app.get("/admin/audit")
@roles_required("ADMIN", "HOD")
def view_audit_logs() -> str:
    entries = (
        AuditLog.query.order_by(AuditLog.id.desc())
        .limit(500)
        .all()
    )
    rows = []
    for item in entries:
        rows.append(
            {
                "id": item.id,
                "timestamp": item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "-",
                "actor": item.actor.full_name if item.actor else "System",
                "role": item.actor_role_code,
                "action": item.action,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "details": json.dumps(item.details(), ensure_ascii=True),
            }
        )

    return render_template("audit_logs.html", rows=rows)


@app.route("/admin/users", methods=["GET", "POST"])
@roles_required("ADMIN")
def manage_users() -> str:
    roles = Role.query.order_by(Role.code.asc()).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role_code = request.form.get("role_code", "").strip().upper()
        profile_class_name = request.form.get("profile_class_name", "").strip()
        profile_standard = request.form.get("profile_standard", "").strip()
        profile_section_code = request.form.get("profile_section_code", "").strip().upper()

        if not username or not full_name or not password or not role_code:
            flash("Username, full name, password, and role are required.", "danger")
            return redirect(url_for("manage_users"))

        password_policy_error = validate_password_policy(password)
        if password_policy_error:
            flash(password_policy_error, "danger")
            return redirect(url_for("manage_users"))

        if User.query.filter_by(username=username).first() is not None:
            flash("Username already exists.", "danger")
            return redirect(url_for("manage_users"))

        if email and User.query.filter_by(email=email).first() is not None:
            flash("Email already exists.", "danger")
            return redirect(url_for("manage_users"))

        role = Role.query.filter_by(code=role_code).first()
        if role is None:
            flash("Invalid role selected.", "danger")
            return redirect(url_for("manage_users"))

        user = User(
            username=username,
            full_name=full_name,
            email=email or None,
            profile_class_name=profile_class_name or None,
            profile_standard=profile_standard or None,
            profile_section_code=profile_section_code or None,
            role_id=role.id,
            is_active=True,
            must_change_password=True,
        )
        user.set_password(password)
        db.session.add(user)

        log_audit_event(
            action="USER_CREATED",
            target_type="USER",
            target_id=username,
            details={
                "role_code": role_code,
                "email": email,
                "profile_class_name": profile_class_name,
                "profile_standard": profile_standard,
                "profile_section_code": profile_section_code,
            },
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Could not create user due to duplicate username or email.", "danger")
            return redirect(url_for("manage_users"))
        flash(f"User {username} created. They must change their password on first login.", "success")
        return redirect(url_for("manage_users"))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=users, roles=roles)


@app.route("/admin/users/<int:user_id>/edit", methods=["POST"])
@roles_required("ADMIN")
def admin_edit_user(user_id: int) -> str:
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("manage_users"))

    username = request.form.get("username", "").strip()
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    role_code = request.form.get("role_code", "").strip().upper()
    profile_class_name = request.form.get("profile_class_name", "").strip()
    profile_standard = request.form.get("profile_standard", "").strip()
    profile_section_code = request.form.get("profile_section_code", "").strip().upper()

    if not username or not full_name or not role_code:
        flash("Username, full name, and role are required.", "danger")
        return redirect(url_for("manage_users"))

    duplicate_user = User.query.filter_by(username=username).first()
    if duplicate_user is not None and duplicate_user.id != user.id:
        flash("Username already exists.", "danger")
        return redirect(url_for("manage_users"))

    if email:
        duplicate_email = User.query.filter_by(email=email).first()
        if duplicate_email is not None and duplicate_email.id != user.id:
            flash("Email already exists.", "danger")
            return redirect(url_for("manage_users"))

    role = Role.query.filter_by(code=role_code).first()
    if role is None:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("manage_users"))

    previous_values = {
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role_code": user.role.code if user.role else None,
        "profile_class_name": user.profile_class_name,
        "profile_standard": user.profile_standard,
        "profile_section_code": user.profile_section_code,
    }

    user.username = username
    user.full_name = full_name
    user.email = email or None
    user.role_id = role.id
    user.profile_class_name = profile_class_name or None
    user.profile_standard = profile_standard or None
    user.profile_section_code = profile_section_code or None

    updated_values = {
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role_code": role.code,
        "profile_class_name": user.profile_class_name,
        "profile_standard": user.profile_standard,
        "profile_section_code": user.profile_section_code,
    }
    changed_fields = {
        key: {"old": previous_values[key], "new": updated_values[key]}
        for key in previous_values
        if previous_values[key] != updated_values[key]
    }

    log_audit_event(
        action="USER_UPDATED",
        target_type="USER",
        target_id=str(user.id),
        details={
            "username": user.username,
            "changes": changed_fields,
        },
    )
    db.session.commit()
    flash(f"User {user.username} updated.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/users/<int:user_id>/toggle-active", methods=["POST"])
@roles_required("ADMIN")
def toggle_user_active(user_id: int) -> str:
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("manage_users"))
    if user.id == current_user.id:
        flash("Cannot deactivate your own account.", "danger")
        return redirect(url_for("manage_users"))
    user.is_active = not user.is_active

    log_audit_event(
        action="USER_TOGGLE_ACTIVE",
        target_type="USER",
        target_id=str(user.id),
        details={
            "username": user.username,
            "new_status": "ACTIVE" if user.is_active else "INACTIVE",
        },
    )
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    flash(f"User {user.username} {status}.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@roles_required("ADMIN")
def admin_reset_password(user_id: int) -> str:
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("manage_users"))
    new_password = request.form.get("new_password", "").strip()
    password_policy_error = validate_password_policy(new_password)
    if password_policy_error:
        flash(password_policy_error, "danger")
        return redirect(url_for("manage_users"))
    user.set_password(new_password)
    user.must_change_password = True

    log_audit_event(
        action="USER_RESET_PASSWORD",
        target_type="USER",
        target_id=str(user.id),
        details={"username": user.username},
    )
    db.session.commit()
    flash(f"Password for {user.username} reset. They must change it on next login.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/master/departments", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def manage_departments() -> str:
    edit_row = None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        if not code or not name:
            flash("Department code and name are required.", "danger")
            return redirect(url_for("manage_departments"))

        current_item = None
        if item_id_raw:
            try:
                current_item = db.session.get(Department, int(item_id_raw))
            except ValueError:
                flash("Invalid department record selected for update.", "danger")
                return redirect(url_for("manage_departments"))

            if current_item is None:
                flash("Department record not found.", "danger")
                return redirect(url_for("manage_departments"))

        duplicate = Department.query.filter_by(code=code).first()
        if duplicate is not None and (current_item is None or duplicate.id != current_item.id):
            flash("Department code already exists.", "danger")
            return redirect(url_for("manage_departments"))

        if current_item is None:
            db.session.add(Department(code=code, name=name))
            flash("Department added.", "success")
        else:
            current_item.code = code
            current_item.name = name
            flash("Department updated.", "success")

        db.session.commit()
        return redirect(url_for("manage_departments"))

    edit_item_id_raw = request.args.get("edit_id", "").strip()
    if edit_item_id_raw:
        try:
            edit_item_id = int(edit_item_id_raw)
        except ValueError:
            flash("Invalid department edit id.", "danger")
            return redirect(url_for("manage_departments"))

        edit_item = db.session.get(Department, edit_item_id)
        if edit_item is None:
            flash("Department record not found for editing.", "danger")
            return redirect(url_for("manage_departments"))

        edit_row = {
            "id": edit_item.id,
            "code": edit_item.code,
            "name": edit_item.name,
        }

    items = Department.query.order_by(Department.code.asc()).all()
    rows = [{"id": item.id, "code": item.code, "name": item.name} for item in items]
    return render_template(
        "master_data.html",
        page_title="Departments",
        create_action=url_for("manage_departments"),
        edit_endpoint="manage_departments",
        delete_endpoint="delete_department",
        columns=[{"key": "id", "label": "ID"}, {"key": "code", "label": "Code"}, {"key": "name", "label": "Name"}],
        fields=[
            {"name": "code", "label": "Code", "type": "text", "required": True},
            {"name": "name", "label": "Name", "type": "text", "required": True},
        ],
        rows=rows,
        edit_row=edit_row,
    )


@app.post("/admin/master/departments/<int:item_id>/delete")
@roles_required("ADMIN", "HOD")
def delete_department(item_id: int):
    item = Department.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Department deleted.", "info")
    return redirect(url_for("manage_departments"))


@app.route("/admin/master/faculty", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def manage_faculty_master() -> str:
    departments = Department.query.order_by(Department.code.asc()).all()
    edit_row = None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        employee_code = request.form.get("employee_code", "").strip()
        department_id_raw = request.form.get("department_id", "").strip()
        max_periods_raw = request.form.get("max_periods_per_day", "").strip()

        if not full_name:
            flash("Faculty full name is required.", "danger")
            return redirect(url_for("manage_faculty_master"))

        current_item = None
        if item_id_raw:
            try:
                current_item = db.session.get(FacultyProfile, int(item_id_raw))
            except ValueError:
                flash("Invalid faculty record selected for update.", "danger")
                return redirect(url_for("manage_faculty_master"))

            if current_item is None:
                flash("Faculty record not found.", "danger")
                return redirect(url_for("manage_faculty_master"))

        if employee_code:
            duplicate = FacultyProfile.query.filter_by(employee_code=employee_code).first()
            if duplicate is not None and (current_item is None or duplicate.id != current_item.id):
                flash("Employee code already exists.", "danger")
                return redirect(url_for("manage_faculty_master"))

        try:
            department_id = int(department_id_raw) if department_id_raw else None
        except ValueError:
            flash("Department must be selected from the provided list.", "danger")
            return redirect(url_for("manage_faculty_master"))

        if department_id is not None and db.session.get(Department, department_id) is None:
            flash("Selected department does not exist.", "danger")
            return redirect(url_for("manage_faculty_master"))

        try:
            max_periods = parse_positive_integer_or_none(max_periods_raw)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("manage_faculty_master"))

        if current_item is None:
            db.session.add(
                FacultyProfile(
                    full_name=full_name,
                    employee_code=employee_code or None,
                    department_id=department_id,
                    max_periods_per_day=max_periods,
                )
            )
            flash("Faculty record added.", "success")
        else:
            current_item.full_name = full_name
            current_item.employee_code = employee_code or None
            current_item.department_id = department_id
            current_item.max_periods_per_day = max_periods
            flash("Faculty record updated.", "success")

        db.session.commit()
        return redirect(url_for("manage_faculty_master"))

    edit_item_id_raw = request.args.get("edit_id", "").strip()
    if edit_item_id_raw:
        try:
            edit_item_id = int(edit_item_id_raw)
        except ValueError:
            flash("Invalid faculty edit id.", "danger")
            return redirect(url_for("manage_faculty_master"))

        edit_item = db.session.get(FacultyProfile, edit_item_id)
        if edit_item is None:
            flash("Faculty record not found for editing.", "danger")
            return redirect(url_for("manage_faculty_master"))

        edit_row = {
            "id": edit_item.id,
            "full_name": edit_item.full_name,
            "employee_code": edit_item.employee_code or "",
            "department_id": str(edit_item.department_id) if edit_item.department_id is not None else "",
            "max_periods_per_day": edit_item.max_periods_per_day or "",
        }

    items = FacultyProfile.query.order_by(FacultyProfile.full_name.asc()).all()
    rows = [
        {
            "id": item.id,
            "full_name": item.full_name,
            "employee_code": item.employee_code or "",
            "department": item.department.code if item.department else "",
            "max_periods_per_day": item.max_periods_per_day or "",
        }
        for item in items
    ]
    return render_template(
        "master_data.html",
        page_title="Faculty Master",
        create_action=url_for("manage_faculty_master"),
        edit_endpoint="manage_faculty_master",
        delete_endpoint="delete_faculty_master",
        columns=[
            {"key": "id", "label": "ID"},
            {"key": "full_name", "label": "Full Name"},
            {"key": "employee_code", "label": "Employee Code"},
            {"key": "department", "label": "Department"},
            {"key": "max_periods_per_day", "label": "Max/Day"},
        ],
        fields=[
            {"name": "full_name", "label": "Full Name", "type": "text", "required": True},
            {"name": "employee_code", "label": "Employee Code", "type": "text", "required": False},
            {
                "name": "department_id",
                "label": "Department",
                "type": "select",
                "required": False,
                "options": [{"value": "", "label": "-- None --"}] + [
                    {"value": str(dep.id), "label": f"{dep.code} - {dep.name}"}
                    for dep in departments
                ],
            },
            {"name": "max_periods_per_day", "label": "Max Periods/Day", "type": "number", "required": False},
        ],
        rows=rows,
        edit_row=edit_row,
    )


@app.post("/admin/master/faculty/<int:item_id>/delete")
@roles_required("ADMIN", "HOD")
def delete_faculty_master(item_id: int):
    item = FacultyProfile.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Faculty record deleted.", "info")
    return redirect(url_for("manage_faculty_master"))


@app.route("/admin/master/rooms", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def manage_rooms_master() -> str:
    edit_row = None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        room_type = request.form.get("room_type", "CLASSROOM").strip().upper() or "CLASSROOM"
        capacity_raw = request.form.get("capacity", "").strip()

        if not code or not name:
            flash("Room code and name are required.", "danger")
            return redirect(url_for("manage_rooms_master"))

        current_item = None
        if item_id_raw:
            try:
                current_item = db.session.get(RoomMaster, int(item_id_raw))
            except ValueError:
                flash("Invalid room record selected for update.", "danger")
                return redirect(url_for("manage_rooms_master"))

            if current_item is None:
                flash("Room record not found.", "danger")
                return redirect(url_for("manage_rooms_master"))

        duplicate = RoomMaster.query.filter_by(code=code).first()
        if duplicate is not None and (current_item is None or duplicate.id != current_item.id):
            flash("Room code already exists.", "danger")
            return redirect(url_for("manage_rooms_master"))

        try:
            capacity = parse_positive_integer_or_none(capacity_raw)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("manage_rooms_master"))

        if current_item is None:
            db.session.add(
                RoomMaster(
                    code=code,
                    name=name,
                    room_type=room_type,
                    capacity=capacity,
                )
            )
            flash("Room record added.", "success")
        else:
            current_item.code = code
            current_item.name = name
            current_item.room_type = room_type
            current_item.capacity = capacity
            flash("Room record updated.", "success")

        db.session.commit()
        return redirect(url_for("manage_rooms_master"))

    edit_item_id_raw = request.args.get("edit_id", "").strip()
    if edit_item_id_raw:
        try:
            edit_item_id = int(edit_item_id_raw)
        except ValueError:
            flash("Invalid room edit id.", "danger")
            return redirect(url_for("manage_rooms_master"))

        edit_item = db.session.get(RoomMaster, edit_item_id)
        if edit_item is None:
            flash("Room record not found for editing.", "danger")
            return redirect(url_for("manage_rooms_master"))

        edit_row = {
            "id": edit_item.id,
            "code": edit_item.code,
            "name": edit_item.name,
            "room_type": edit_item.room_type,
            "capacity": edit_item.capacity or "",
        }

    items = RoomMaster.query.order_by(RoomMaster.code.asc()).all()
    rows = [
        {
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "room_type": item.room_type,
            "capacity": item.capacity or "",
        }
        for item in items
    ]
    return render_template(
        "master_data.html",
        page_title="Rooms Master",
        create_action=url_for("manage_rooms_master"),
        edit_endpoint="manage_rooms_master",
        delete_endpoint="delete_rooms_master",
        columns=[
            {"key": "id", "label": "ID"},
            {"key": "code", "label": "Code"},
            {"key": "name", "label": "Name"},
            {"key": "room_type", "label": "Type"},
            {"key": "capacity", "label": "Capacity"},
        ],
        fields=[
            {"name": "code", "label": "Code", "type": "text", "required": True},
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {
                "name": "room_type",
                "label": "Room Type",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "CLASSROOM", "label": "CLASSROOM"},
                    {"value": "LAB", "label": "LAB"},
                ],
            },
            {"name": "capacity", "label": "Capacity", "type": "number", "required": False},
        ],
        rows=rows,
        edit_row=edit_row,
    )


@app.post("/admin/master/rooms/<int:item_id>/delete")
@roles_required("ADMIN", "HOD")
def delete_rooms_master(item_id: int):
    item = RoomMaster.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Room record deleted.", "info")
    return redirect(url_for("manage_rooms_master"))


@app.route("/admin/master/sections", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def manage_sections_master() -> str:
    edit_row = None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        class_name = request.form.get("class_name", "").strip()
        standard = request.form.get("standard", "").strip()
        section_code = request.form.get("section_code", "").strip().upper()
        home_room = request.form.get("home_room", "").strip().upper()

        if not class_name or not standard or not section_code:
            flash("Class, standard, and section are required.", "danger")
            return redirect(url_for("manage_sections_master"))

        current_item = None
        if item_id_raw:
            try:
                current_item = db.session.get(SectionMaster, int(item_id_raw))
            except ValueError:
                flash("Invalid section record selected for update.", "danger")
                return redirect(url_for("manage_sections_master"))

            if current_item is None:
                flash("Section record not found.", "danger")
                return redirect(url_for("manage_sections_master"))

        duplicate = SectionMaster.query.filter_by(
            class_name=class_name,
            standard=standard,
            section_code=section_code,
        ).first()
        if duplicate is not None and (current_item is None or duplicate.id != current_item.id):
            flash("Section already exists.", "danger")
            return redirect(url_for("manage_sections_master"))

        if current_item is None:
            db.session.add(
                SectionMaster(
                    class_name=class_name,
                    standard=standard,
                    section_code=section_code,
                    home_room=home_room or None,
                )
            )
            flash("Section record added.", "success")
        else:
            current_item.class_name = class_name
            current_item.standard = standard
            current_item.section_code = section_code
            current_item.home_room = home_room or None
            flash("Section record updated.", "success")

        db.session.commit()
        return redirect(url_for("manage_sections_master"))

    edit_item_id_raw = request.args.get("edit_id", "").strip()
    if edit_item_id_raw:
        try:
            edit_item_id = int(edit_item_id_raw)
        except ValueError:
            flash("Invalid section edit id.", "danger")
            return redirect(url_for("manage_sections_master"))

        edit_item = db.session.get(SectionMaster, edit_item_id)
        if edit_item is None:
            flash("Section record not found for editing.", "danger")
            return redirect(url_for("manage_sections_master"))

        edit_row = {
            "id": edit_item.id,
            "class_name": edit_item.class_name,
            "standard": edit_item.standard,
            "section_code": edit_item.section_code,
            "home_room": edit_item.home_room or "",
        }

    items = SectionMaster.query.order_by(
        SectionMaster.class_name.asc(),
        SectionMaster.standard.asc(),
        SectionMaster.section_code.asc(),
    ).all()
    rows = [
        {
            "id": item.id,
            "class_name": item.class_name,
            "standard": item.standard,
            "section_code": item.section_code,
            "home_room": item.home_room or "",
        }
        for item in items
    ]
    return render_template(
        "master_data.html",
        page_title="Sections Master",
        create_action=url_for("manage_sections_master"),
        edit_endpoint="manage_sections_master",
        delete_endpoint="delete_sections_master",
        columns=[
            {"key": "id", "label": "ID"},
            {"key": "class_name", "label": "Class"},
            {"key": "standard", "label": "Standard"},
            {"key": "section_code", "label": "Section"},
            {"key": "home_room", "label": "Home Room"},
        ],
        fields=[
            {"name": "class_name", "label": "Class", "type": "text", "required": True},
            {"name": "standard", "label": "Standard", "type": "text", "required": True},
            {"name": "section_code", "label": "Section", "type": "text", "required": True},
            {"name": "home_room", "label": "Home Room", "type": "text", "required": False},
        ],
        rows=rows,
        edit_row=edit_row,
    )


@app.post("/admin/master/sections/<int:item_id>/delete")
@roles_required("ADMIN", "HOD")
def delete_sections_master(item_id: int):
    item = SectionMaster.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Section record deleted.", "info")
    return redirect(url_for("manage_sections_master"))


@app.route("/admin/master/subjects", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def manage_subjects_master() -> str:
    edit_row = None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        code = request.form.get("code", "").strip().upper()
        name = request.form.get("name", "").strip()
        subject_type = request.form.get("subject_type", "THEORY").strip().upper() or "THEORY"
        weekly_raw = request.form.get("default_weekly_periods", "").strip()
        daily_raw = request.form.get("default_daily_max", "").strip()

        if not code or not name:
            flash("Subject code and name are required.", "danger")
            return redirect(url_for("manage_subjects_master"))

        current_item = None
        if item_id_raw:
            try:
                current_item = db.session.get(SubjectMaster, int(item_id_raw))
            except ValueError:
                flash("Invalid subject record selected for update.", "danger")
                return redirect(url_for("manage_subjects_master"))

            if current_item is None:
                flash("Subject record not found.", "danger")
                return redirect(url_for("manage_subjects_master"))

        duplicate = SubjectMaster.query.filter_by(code=code).first()
        if duplicate is not None and (current_item is None or duplicate.id != current_item.id):
            flash("Subject code already exists.", "danger")
            return redirect(url_for("manage_subjects_master"))

        try:
            weekly_periods = parse_positive_integer_or_none(weekly_raw)
            daily_max = parse_positive_integer_or_none(daily_raw)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("manage_subjects_master"))

        if current_item is None:
            db.session.add(
                SubjectMaster(
                    code=code,
                    name=name,
                    subject_type=subject_type,
                    default_weekly_periods=weekly_periods,
                    default_daily_max=daily_max,
                )
            )
            flash("Subject record added.", "success")
        else:
            current_item.code = code
            current_item.name = name
            current_item.subject_type = subject_type
            current_item.default_weekly_periods = weekly_periods
            current_item.default_daily_max = daily_max
            flash("Subject record updated.", "success")

        db.session.commit()
        return redirect(url_for("manage_subjects_master"))

    edit_item_id_raw = request.args.get("edit_id", "").strip()
    if edit_item_id_raw:
        try:
            edit_item_id = int(edit_item_id_raw)
        except ValueError:
            flash("Invalid subject edit id.", "danger")
            return redirect(url_for("manage_subjects_master"))

        edit_item = db.session.get(SubjectMaster, edit_item_id)
        if edit_item is None:
            flash("Subject record not found for editing.", "danger")
            return redirect(url_for("manage_subjects_master"))

        edit_row = {
            "id": edit_item.id,
            "code": edit_item.code,
            "name": edit_item.name,
            "subject_type": edit_item.subject_type,
            "default_weekly_periods": edit_item.default_weekly_periods or "",
            "default_daily_max": edit_item.default_daily_max or "",
        }

    items = SubjectMaster.query.order_by(SubjectMaster.code.asc()).all()
    rows = [
        {
            "id": item.id,
            "code": item.code,
            "name": item.name,
            "subject_type": item.subject_type,
            "default_weekly_periods": item.default_weekly_periods or "",
            "default_daily_max": item.default_daily_max or "",
        }
        for item in items
    ]
    return render_template(
        "master_data.html",
        page_title="Subjects Master",
        create_action=url_for("manage_subjects_master"),
        edit_endpoint="manage_subjects_master",
        delete_endpoint="delete_subjects_master",
        columns=[
            {"key": "id", "label": "ID"},
            {"key": "code", "label": "Code"},
            {"key": "name", "label": "Name"},
            {"key": "subject_type", "label": "Type"},
            {"key": "default_weekly_periods", "label": "Weekly"},
            {"key": "default_daily_max", "label": "Daily Max"},
        ],
        fields=[
            {"name": "code", "label": "Code", "type": "text", "required": True},
            {"name": "name", "label": "Name", "type": "text", "required": True},
            {
                "name": "subject_type",
                "label": "Subject Type",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "THEORY", "label": "THEORY"},
                    {"value": "LAB", "label": "LAB"},
                ],
            },
            {"name": "default_weekly_periods", "label": "Default Weekly", "type": "number", "required": False},
            {"name": "default_daily_max", "label": "Default Daily Max", "type": "number", "required": False},
        ],
        rows=rows,
        edit_row=edit_row,
    )


@app.post("/admin/master/subjects/<int:item_id>/delete")
@roles_required("ADMIN", "HOD")
def delete_subjects_master(item_id: int):
    item = SubjectMaster.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Subject record deleted.", "info")
    return redirect(url_for("manage_subjects_master"))


@app.route("/admin/master/assignments", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def manage_assignments_master() -> str:
    edit_row = None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        class_name = request.form.get("class_name", "").strip()
        standard = request.form.get("standard", "").strip()
        section_code = request.form.get("section_code", "").strip().upper()
        subject_name = request.form.get("subject_name", "").strip()
        teacher_name = request.form.get("teacher_name", "").strip()
        lectures_raw = request.form.get("lectures", "").strip()
        subject_type_raw = request.form.get("subject_type", "THEORY").strip().upper() or "THEORY"
        allowed_rooms_raw = request.form.get("allowed_rooms", "").strip()
        daily_max_raw = request.form.get("daily_max", "").strip()

        if not all([class_name, standard, section_code, subject_name, teacher_name, lectures_raw]):
            flash("Class, standard, section, subject, faculty, and lectures are required.", "danger")
            return redirect(url_for("manage_assignments_master"))

        try:
            lectures = parse_integer_field(lectures_raw, "Lectures", 1)
            daily_max = parse_positive_integer_or_none(daily_max_raw)
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("manage_assignments_master"))

        subject_type_aliases = {
            "THEORY": "THEORY",
            "T": "THEORY",
            "LAB": "LAB",
            "P": "LAB",
            "PRACTICAL": "LAB",
            "LABORATORY": "LAB",
        }
        subject_type = subject_type_aliases.get(subject_type_raw)
        if subject_type is None:
            flash("Subject type must be THEORY or LAB.", "danger")
            return redirect(url_for("manage_assignments_master"))

        allowed_rooms_list = parse_allowed_rooms(allowed_rooms_raw)
        allowed_rooms = "|".join(allowed_rooms_list)
        is_lab = subject_type == "LAB"

        if is_lab and not allowed_rooms_list:
            flash("LAB assignment must include at least one allowed room.", "danger")
            return redirect(url_for("manage_assignments_master"))

        if is_lab and lectures % 2 != 0:
            flash("LAB assignment lectures must be even for double-period scheduling.", "danger")
            return redirect(url_for("manage_assignments_master"))

        if daily_max is not None and daily_max > lectures:
            flash("Daily max cannot exceed total lectures for the assignment.", "danger")
            return redirect(url_for("manage_assignments_master"))

        if is_lab and daily_max is not None and daily_max < 2:
            flash("LAB assignment daily max must be at least 2.", "danger")
            return redirect(url_for("manage_assignments_master"))

        current_item = None
        if item_id_raw:
            try:
                current_item = db.session.get(AssignmentMaster, int(item_id_raw))
            except ValueError:
                flash("Invalid assignment master record selected for update.", "danger")
                return redirect(url_for("manage_assignments_master"))

            if current_item is None:
                flash("Assignment master record not found.", "danger")
                return redirect(url_for("manage_assignments_master"))

        duplicate = AssignmentMaster.query.filter_by(
            class_name=class_name,
            standard=standard,
            section_code=section_code,
            subject_name=subject_name,
            teacher_name=teacher_name,
        ).first()
        if duplicate is not None and (current_item is None or duplicate.id != current_item.id):
            flash("Assignment row already exists for the same class/section/subject/faculty.", "danger")
            return redirect(url_for("manage_assignments_master"))

        if current_item is None:
            db.session.add(
                AssignmentMaster(
                    class_name=class_name,
                    standard=standard,
                    section_code=section_code,
                    subject_name=subject_name,
                    teacher_name=teacher_name,
                    lectures=lectures,
                    subject_type=subject_type,
                    allowed_rooms=allowed_rooms or None,
                    daily_max=daily_max,
                )
            )
            flash("Assignment master row added.", "success")
        else:
            current_item.class_name = class_name
            current_item.standard = standard
            current_item.section_code = section_code
            current_item.subject_name = subject_name
            current_item.teacher_name = teacher_name
            current_item.lectures = lectures
            current_item.subject_type = subject_type
            current_item.allowed_rooms = allowed_rooms or None
            current_item.daily_max = daily_max
            flash("Assignment master row updated.", "success")

        db.session.commit()
        return redirect(url_for("manage_assignments_master"))

    edit_item_id_raw = request.args.get("edit_id", "").strip()
    if edit_item_id_raw:
        try:
            edit_item_id = int(edit_item_id_raw)
        except ValueError:
            flash("Invalid assignment master edit id.", "danger")
            return redirect(url_for("manage_assignments_master"))

        edit_item = db.session.get(AssignmentMaster, edit_item_id)
        if edit_item is None:
            flash("Assignment master row not found for editing.", "danger")
            return redirect(url_for("manage_assignments_master"))

        edit_row = {
            "id": edit_item.id,
            "class_name": edit_item.class_name,
            "standard": edit_item.standard,
            "section_code": edit_item.section_code,
            "subject_name": edit_item.subject_name,
            "teacher_name": edit_item.teacher_name,
            "lectures": edit_item.lectures,
            "subject_type": edit_item.subject_type,
            "allowed_rooms": edit_item.allowed_rooms or "",
            "daily_max": edit_item.daily_max or "",
        }

    items = AssignmentMaster.query.order_by(
        AssignmentMaster.class_name.asc(),
        AssignmentMaster.standard.asc(),
        AssignmentMaster.section_code.asc(),
        AssignmentMaster.subject_name.asc(),
        AssignmentMaster.teacher_name.asc(),
    ).all()
    rows = [
        {
            "id": item.id,
            "class_name": item.class_name,
            "standard": item.standard,
            "section_code": item.section_code,
            "subject_name": item.subject_name,
            "teacher_name": item.teacher_name,
            "lectures": item.lectures,
            "subject_type": item.subject_type,
            "allowed_rooms": item.allowed_rooms or "",
            "daily_max": item.daily_max or "",
        }
        for item in items
    ]
    return render_template(
        "master_data.html",
        page_title="Assignment Master",
        create_action=url_for("manage_assignments_master"),
        edit_endpoint="manage_assignments_master",
        delete_endpoint="delete_assignments_master",
        columns=[
            {"key": "id", "label": "ID"},
            {"key": "class_name", "label": "Class"},
            {"key": "standard", "label": "Standard"},
            {"key": "section_code", "label": "Section"},
            {"key": "subject_name", "label": "Subject"},
            {"key": "teacher_name", "label": "Faculty"},
            {"key": "lectures", "label": "Lectures"},
            {"key": "subject_type", "label": "Type"},
            {"key": "allowed_rooms", "label": "Allowed Rooms"},
            {"key": "daily_max", "label": "Daily Max"},
        ],
        fields=[
            {"name": "class_name", "label": "Class", "type": "text", "required": True},
            {"name": "standard", "label": "Standard", "type": "text", "required": True},
            {"name": "section_code", "label": "Section", "type": "text", "required": True},
            {"name": "subject_name", "label": "Subject", "type": "text", "required": True},
            {"name": "teacher_name", "label": "Faculty", "type": "text", "required": True},
            {"name": "lectures", "label": "Lectures", "type": "number", "required": True},
            {
                "name": "subject_type",
                "label": "Type",
                "type": "select",
                "required": True,
                "options": [
                    {"value": "THEORY", "label": "THEORY"},
                    {"value": "LAB", "label": "LAB"},
                ],
            },
            {
                "name": "allowed_rooms",
                "label": "Allowed Rooms (LAB)",
                "type": "text",
                "required": False,
            },
            {"name": "daily_max", "label": "Daily Max", "type": "number", "required": False},
        ],
        rows=rows,
        edit_row=edit_row,
    )


@app.post("/admin/master/assignments/<int:item_id>/delete")
@roles_required("ADMIN", "HOD")
def delete_assignments_master(item_id: int):
    item = AssignmentMaster.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Assignment master row deleted.", "info")
    return redirect(url_for("manage_assignments_master"))


# ============================================================================
# PHASE 3: NEW ROUTE ENDPOINTS
# ============================================================================

@app.route("/admin/analytics/<int:version_id>")
@roles_required("ADMIN", "HOD")
def analytics_dashboard(version_id: int) -> str:
    """Display analytics and fairness metrics for a timetable version."""
    role_code = get_current_role_code()
    version = TimetableVersion.query.filter_by(id=version_id).first()
    
    if not version:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))
    
    # Extract payload
    payload = json.loads(version.payload)
    days = payload.get("days", [])
    periods = payload.get("periods", [])
    section_tables = payload.get("section_tables", [])
    class_tables = payload.get("class_tables", [])
    faculty_tables = payload.get("faculty_tables", [])
    room_tables = payload.get("room_tables", [])
    summary = payload.get("summary", {})
    
    # Compute analytics
    prepared = {
        "days": days,
        "periods": periods,
        "section_tables": section_tables,
        "class_tables": class_tables,
        "faculty_tables": faculty_tables,
        "room_tables": room_tables,
        "summary": summary
    }
    analytics = build_analytics_payload(prepared)
    
    return render_template(
        "analytics.html",
        version=version,
        days=days,
        periods=periods,
        analytics=analytics,
        role_code=role_code
    )


@app.route("/export/ics/<int:version_id>")
@login_required
def export_ics(version_id: int):
    """Export timetable as RFC 5545 calendar format."""
    faculty_filter = request.args.get("faculty", "").strip()
    section_filter = request.args.get("section", "").strip()
    
    version = TimetableVersion.query.filter_by(id=version_id).first()
    if not version:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))
    
    # Extract payload
    payload = json.loads(version.payload)
    days = payload.get("days", [])
    periods = payload.get("periods", [])
    section_tables = payload.get("section_tables", [])
    lunch_breaks = payload.get("lunch_break_periods_by_day", {})
    
    # Generate ICS
    ics_text = build_ics_calendar_text(
        version=version,
        days=days,
        periods=periods,
        section_tables=section_tables,
        lunch_break_periods_by_day=lunch_breaks,
        faculty_filter=faculty_filter,
        section_filter=section_filter
    )
    
    # Determine filename
    if faculty_filter:
        filename = f"timetable-{faculty_filter.replace(' ', '_')}-{version.version_label}.ics"
    elif section_filter:
        filename = f"timetable-{section_filter}-{version.version_label}.ics"
    else:
        filename = f"timetable-{version.version_label}.ics"
    
    # Return as attachment
    return send_file(
        io.BytesIO(ics_text.encode("utf-8")),
        mimetype="text/calendar",
        as_attachment=True,
        download_name=filename
    )


@app.route("/admin/absence-substitute/<int:version_id>", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def absence_substitute(version_id: int):
    """Substitute absent faculty with intelligent ranking."""
    role_code = get_current_role_code()
    version = TimetableVersion.query.filter_by(id=version_id).first()
    
    if not version:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))
    
    payload = json.loads(version.payload)
    days_list = payload.get("days", [])
    periods_list = payload.get("periods", [])
    section_tables = payload.get("section_tables", [])
    assignment_payload = payload.get("assignment_payload", [])
    lunch_breaks = payload.get("lunch_break_periods_by_day", {})
    constraint_settings = payload.get("constraint_settings", {})
    
    if request.method == "GET":
        # Show form
        faculty_list = sorted(set(
            assignment["teacher"] 
            for assignment in assignment_payload 
            if assignment.get("teacher")
        ))
        
        return render_template(
            "absence-substitute.html",
            version=version,
            faculty_list=faculty_list,
            days=days_list,
            periods=periods_list,
            role_code=role_code
        )
    
    else:  # POST
        absent_faculty = request.form.get("absent_faculty", "").strip()
        day_str = request.form.get("day", "").strip()
        period_str = request.form.get("period", "").strip()
        
        try:
            day_index = int(day_str) if day_str else None
            period_index = int(period_str) if period_str else None
            
            # Apply substitutions
            updated_tables, subs, issues = auto_apply_absence_substitutions(
                section_tables=section_tables,
                assignment_payload=assignment_payload,
                absent_faculty=absent_faculty,
                day_index=day_index,
                period_index=period_index,
                lunch_break_periods_by_day=lunch_breaks,
                faculty_daily_default_max=int(
                    constraint_settings.get("faculty_daily_default_max", 6)
                ),
                faculty_daily_limits=constraint_settings.get("faculty_daily_limits", {})
            )
            
            # Validate
            validation_issues = validate_multi_section_timetable(
                days=days_list,
                periods=periods_list,
                section_tables=updated_tables,
                class_tables=payload.get("class_tables", []),
                faculty_tables=payload.get("faculty_tables", []),
                room_tables=payload.get("room_tables", []),
                assignment_payload=assignment_payload,
                require_daily_free_period=constraint_settings.get("require_daily_free_period", False)
            )
            
            # Create new draft version
            new_summary = dict(payload.get("summary", {}))
            new_summary["substitutions_applied"] = len(subs)
            
            new_version = persist_timetable_version(
                days=days_list,
                periods=periods_list,
                section_tables=updated_tables,
                summary=new_summary,
                constraint_settings=constraint_settings,
                generation_scope_description="All Sections",
                validation_issues=validation_issues
            )
            
            # Log audit event
            log_audit_event(
                action="FACULTY_SUBSTITUTED",
                target_type="TIMETABLE_VERSION",
                target_id=str(new_version.id),
                details={
                    "source_version_id": version_id,
                    "absent_faculty": absent_faculty,
                    "day": day_index,
                    "period": period_index,
                    "substitutions_count": len(subs)
                }
            )
            db.session.commit()
            
            # Flash results
            flash(f"Successfully substituted {len(subs)} assignment(s).", "success")
            for sub in subs[:5]:  # Show first 5
                flash(
                    f"✓ {sub['original_faculty']} → {sub['new_faculty']} ({sub['subject']})",
                    "info"
                )
            if len(subs) > 5:
                flash(f"... and {len(subs) - 5} more substitutions", "info")
            
            for issue in validation_issues:
                flash(issue, "warning")
            
            return redirect(url_for("view_timetable_version", version_id=new_version.id))
        
        except ValueError as e:
            flash(f"Substitution failed: {str(e)}", "danger")
            return redirect(url_for("absence_substitute", version_id=version_id))


@app.route("/admin/lock-slots/<int:version_id>", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def lock_slots_regenerate(version_id: int):
    """Lock selected cells and regenerate remaining timetable."""
    role_code = get_current_role_code()
    version = TimetableVersion.query.filter_by(id=version_id).first()
    
    if not version:
        flash("Timetable version not found.", "danger")
        return redirect(url_for("dashboard"))
    
    payload = json.loads(version.payload)
    days_list = payload.get("days", [])
    periods_list = payload.get("periods", [])
    section_tables = payload.get("section_tables", [])
    class_tables = payload.get("class_tables", [])
    faculty_tables = payload.get("faculty_tables", [])
    room_tables = payload.get("room_tables", [])
    assignment_payload = payload.get("assignment_payload", [])
    lunch_breaks = payload.get("lunch_break_periods_by_day", {})
    constraint_settings = payload.get("constraint_settings", {})
    
    if request.method == "GET":
        # Show slot selection UI
        return render_template(
            "lock-slots.html",
            version=version,
            days=days_list,
            periods=periods_list,
            section_tables=section_tables,
            role_code=role_code
        )
    
    else:  # POST
        # Parse locked slots from form (CSV format)
        locked_slots_raw = request.form.get("locked_slots", "").strip()
        
        try:
            # Parse slots
            locked_slots = parse_locked_slot_rows(
                raw_text=locked_slots_raw,
                section_tables=section_tables,
                days=days_list,
                periods=periods_list
            )
            
            # Build locked cells
            locked_cells = build_locked_cells_from_slots(
                section_tables=section_tables,
                locked_slots=locked_slots,
                lunch_break_periods_by_day=lunch_breaks
            )
            
            # Regenerate with locked cells
            (
                regen_days, regen_periods, regen_section_tables,
                regen_class_tables, regen_faculty_tables, regen_room_tables,
                regen_summary, validation_issues
            ) = generate_outputs(
                assignment_payload=assignment_payload,
                rooms=constraint_settings.get("rooms", []),
                working_days=len(days_list),
                periods_per_day=len(periods_list),
                lunch_break_periods_by_day=lunch_breaks,
                section_home_rooms=constraint_settings.get("section_home_rooms", {}),
                faculty_daily_default_max=int(
                    constraint_settings.get("faculty_daily_default_max", 6)
                ),
                faculty_daily_limits=constraint_settings.get("faculty_daily_limits", {}),
                lab_same_day_subject_threshold=int(
                    constraint_settings.get("lab_same_day_subject_threshold", 3)
                ),
                locked_section_cells=locked_cells,
                require_daily_free_period=constraint_settings.get("require_daily_free_period", False),
                write_output_files=True
            )
            
            # Create new draft version
            new_version = persist_timetable_version(
                days=regen_days,
                periods=regen_periods,
                section_tables=regen_section_tables,
                summary=regen_summary,
                constraint_settings=constraint_settings,
                generation_scope_description="All Sections (with locked slots)",
                validation_issues=validation_issues
            )
            
            # Log audit event
            log_audit_event(
                action="TIMETABLE_REGENERATED_WITH_LOCKS",
                target_type="TIMETABLE_VERSION",
                target_id=str(new_version.id),
                details={
                    "source_version_id": version_id,
                    "locked_cells_count": len(locked_cells),
                    "scheduled_slots": regen_summary.get("scheduled_slots", 0)
                }
            )
            db.session.commit()
            
            flash(f"Timetable regenerated successfully with {len(locked_cells)} locked cells.", "success")
            return redirect(url_for("view_timetable_version", version_id=new_version.id))
        
        except ValueError as e:
            flash(f"Lock-slot regeneration failed: {str(e)}", "danger")
            return redirect(url_for("lock_slots_regenerate", version_id=version_id))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
