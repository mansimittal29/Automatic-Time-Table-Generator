from __future__ import annotations

import os
import sys
import uuid
import json
from pathlib import Path

import pytest

TEST_DB_FILE = Path(__file__).resolve().parent / f"test_{uuid.uuid4().hex}.db"
os.environ["TIMETABLE_DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE.as_posix()}"
os.environ.setdefault("TIMETABLE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("TIMETABLE_ADMIN_USERNAME", "admin")
os.environ.setdefault("TIMETABLE_ADMIN_PASSWORD", "admin123")
os.environ.setdefault("TIMETABLE_ADMIN_NAME", "Test Admin")

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as timetable_app


@pytest.fixture(autouse=True)
def reset_database():
    timetable_app._LOGIN_RATE_LIMIT_BUCKETS.clear()
    with timetable_app.app.app_context():
        timetable_app.db.drop_all()
        timetable_app.db.create_all()
        timetable_app.ensure_seed_data(
            admin_username=os.environ["TIMETABLE_ADMIN_USERNAME"],
            admin_password=os.environ["TIMETABLE_ADMIN_PASSWORD"],
            admin_full_name=os.environ["TIMETABLE_ADMIN_NAME"],
        )
    yield


@pytest.fixture()
def client():
    timetable_app.app.config.update(TESTING=True)
    with timetable_app.app.test_client() as test_client:
        yield test_client


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Portal Sign In" in response.data


def test_dashboard_redirects_when_not_authenticated(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in {301, 302, 303, 307, 308}
    assert "/login" in response.headers["Location"]


def test_cross_origin_post_is_blocked(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": "invalid"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert b"Blocked cross-origin request" in response.data


def test_login_rate_limit_blocks_after_repeated_failures(client):
    for _ in range(timetable_app.LOGIN_RATE_LIMIT_MAX_FAILURES):
        response = client.post("/login", data={"username": "admin", "password": "invalid"})
        assert response.status_code == 200

    blocked = client.post("/login", data={"username": "admin", "password": "invalid"})
    assert blocked.status_code == 200
    assert b"Too many sign-in attempts" in blocked.data


def test_student_dashboard_auto_links_latest_semester(client):
    with timetable_app.app.app_context():
        student_role = timetable_app.Role.query.filter_by(code="STUDENT").first()
        assert student_role is not None

        student_user = timetable_app.User(
            username="st2026001",
            full_name="Student One",
            role_id=student_role.id,
            is_active=True,
            must_change_password=False,
            profile_class_name="Class-01",
            profile_standard="Year-1",
            profile_section_code="A",
        )
        student_user.set_password("StrongPass123")
        timetable_app.db.session.add(student_user)

        payload = {
            "days": ["Monday"],
            "periods": ["P1"],
            "section_tables": [
                {
                    "section_key": "Class-01 | Std Year-2 | Sec A",
                    "class_name": "Class-01",
                    "standard": "Year-2",
                    "section": "A",
                    "timetable": [[{"subject": "Math", "teacher": "Faculty-01", "room": "CR-101"}]],
                }
            ],
            "summary": {},
        }
        published_version = timetable_app.TimetableVersion(
            version_label="V-SEM-AUTO-1",
            status="published",
            summary_json=json.dumps(payload),
        )
        timetable_app.db.session.add(published_version)
        timetable_app.db.session.commit()

    login_response = client.post(
        "/login",
        data={"username": "st2026001", "password": "StrongPass123"},
        follow_redirects=True,
    )
    assert login_response.status_code == 200

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert b"Today&#39;s Schedule" in dashboard_response.data

    with timetable_app.app.app_context():
        refreshed_user = timetable_app.User.query.filter_by(username="st2026001").first()
        assert refreshed_user is not None
        assert refreshed_user.profile_standard == "Year-2"
