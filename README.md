# Automated Academic Timetable Scheduling System

A simplified Flask-based timetable generator for local college project demos.

## Features

- Input working days, periods, rooms, and faculty assignment rows
- Generate multiple class-standard-section timetables in one run
- Define who teaches which subject for each class/standard/section
- Configure periods per day and optional random seed for reproducible results
- Generate conflict-free schedules with global teacher and room conflict checks
- Enforce fixed lunch-break periods across all sections
- Enforce lab-subject room restrictions (specific lab rooms)
- Enforce contiguous double-period LAB sessions
- Enforce optional per-subject daily max limits per section
- Enforce section home classrooms for non-lab lectures
- Enforce faculty daily max period constraints (default + per-faculty overrides)
- Enforce faculty unavailability slots (day/period blocking)
- Enforce fixed-slot constraints (pin specific subject-teacher sessions to exact day/period)
- Generate directly from Assignment Master rows (manual textarea optional)
- Generate in scoped mode (all sections, single class, or single section)
- Optimize generated timetables with a soft-score model (best of randomized candidates)
- Show generation diagnostics on failure (capacity estimate, lab input checks, and source/scope summary)
- Display timetable in a clean web interface
- Show schedule analytics: utilization, subject load, teacher load, and room usage
- Export timetable to Excel, CSV, and JSON
- Main Excel export now includes formatted sheets: CLASS, FACULTY, LAB, and ROOM
- Export separate class-wise timetable files (Excel, CSV, JSON)
- Export separate room-wise timetable files (Excel, CSV, JSON)
- Export separate faculty-wise timetable files (Excel, CSV, JSON)
- Show a dedicated class timetable view in output UI for confusion-free class lookup
- Show a dedicated room timetable view in output UI for classroom and lab planning
- Show a dedicated faculty timetable view in output UI for confusion-free faculty lookup
- Access latest generated timetable over API at /api/timetable/latest
- Access latest class timetable API at /api/timetable/class/latest
- Access latest room timetable API at /api/timetable/room/latest
- Access latest faculty timetable API at /api/timetable/faculty/latest
- Role-based login (ADMIN/HOD/FACULTY/STUDENT) with seeded admin account
- Database-backed master data modules for departments, faculty, rooms, sections, and subjects
- Database-backed Assignment Master module for class/subject/faculty lecture rows
- Master data pages support create, edit, and delete operations
- Includes `migrate_db.py` for predictable schema upgrades on existing databases
- Timetable version workflow with draft, approve, and publish states
- Save each generation run as a draft `TimetableVersion` snapshot and compare two versions slot-by-slot
- Manual slot editing from saved versions with automatic section/class/faculty/room sync
- Conflict-aware manual edit validation (teacher clash, room clash, lunch slot violation, ambiguous faculty slot edits)
- Every accepted manual edit is saved as a new draft version for review and publish
- Start demo with a single double-click using start_demo.bat

## Large-Scale Preset Included

The default data files are now preloaded for high-volume scheduling:

- Faculty: 65
- Classrooms: 30
- Labs: 20
- Classes: 10
- Sections per class: 3 (A, B, C)
- Subjects per section: 5 theory + 3 labs

Additional preset behavior:

- At least one faculty is assigned across 3 classes (supported by default sample data).
- Lab sessions are scheduled as contiguous double periods.
- Subject daily caps are prefilled to keep scheduling feasible at scale.
- Defaults are tuned for larger runs: 7 working days, 8 periods/day, lunch at period 5.

## Known Working Example (Conflict-Free)

Use this exact setup for a feasible large-scale generation:

- Working days: 7
- Periods per day: 8
- Lunch break periods: 5,5,5,5,5,5,6
- Faculty daily max: 6
- Random seed: 77 (optional, for repeatability)

Use bundled data files as-is:

- data/rooms.csv (30 classrooms + 20 labs)
- data/section_classrooms.csv (10 classes x 3 sections)
- data/assignments.csv (5 theory + 3 labs per section)
- data/faculty_daily_limits.csv (65 faculty limits)

Expected result characteristics with this example:

- 30 sections generated
- 0 validation conflicts
- API route /api/timetable/latest returns status 200

One direct assignment row from the working example:

Class-01,Year-1,A,Mathematics,Faculty-01,4,THEORY,,2

One direct lab row from the working example:

Class-01,Year-1,A,Programming Lab,Faculty-19,2,LAB,LAB-01|LAB-02|LAB-03|LAB-04|LAB-05|LAB-06|LAB-07|LAB-08|LAB-09|LAB-10,2

## One-Click Large Demo Example

On the index page, click **Load Large Demo Dataset** to auto-fill a deterministic high-volume demo set.

Loaded dataset shape:

- 40 classes x 3 sections = 120 sections
- 5 theory + 6 lab subjects per section
- 1320 assignment rows total
- 250 rooms total (140 classroom + 110 labs)
- 1320 faculty daily-limit rows
- LAB rows are auto-split into G1/G2/G3 groups and scheduled in the same slot with distinct lab rooms
- Faculty rest rule is active: no back-to-back periods for the same teacher (except the two periods of one LAB block)

## Project Structure

```text
timetable-generator/
|-- app.py
|-- database.py
|-- timetable_generator.py
|-- migrate_db.py
|-- requirements.txt
|-- start_demo.bat
|-- instance/
|   `-- timetable.db
|-- templates/
|   |-- dashboard.html
|   |-- index.html
|   |-- login.html
|   |-- master_data.html
|   |-- timetable.html
|   |-- users.html
|   `-- versions_compare.html
|-- static/
|   |-- style.css
|   `-- script.js
|-- data/
|   |-- assignments.csv
|   |-- assignments_template.csv
|   |-- section_classrooms.csv
|   |-- faculty_daily_limits.csv
|   `-- rooms.csv
`-- output/
   |-- .gitkeep
   |-- timetable.xlsx
   |-- timetable.csv
   |-- timetable.json
   |-- class_timetable.xlsx
   |-- class_timetable.csv
   |-- class_timetable.json
   |-- room_timetable.xlsx
   |-- room_timetable.csv
   |-- room_timetable.json
   |-- faculty_timetable.xlsx
   |-- faculty_timetable.csv
   `-- faculty_timetable.json
```

## Run Instructions (Manual)

1. Open VS Code and open this folder:

   Automatic-Time-Table-Generator/timetable-generator

2. Install dependencies:

   pip install -r requirements.txt

3. Run the server:

   python migrate_db.py
   python app.py

4. Open browser:

   http://127.0.0.1:5000

5. Sign in with seeded admin credentials:

   username: admin
   password: admin123

6. Optional quick preview route (auto-generates sample timetable):

   http://127.0.0.1:5000/demo

## Run Instructions (One-Click Windows Demo)

1. Open folder Automatic-Time-Table-Generator/timetable-generator in File Explorer.
2. Double-click start_demo.bat.
3. Wait for dependency check, migration, and server startup.
4. Browser opens automatically at http://127.0.0.1:5000.

## Input Format (on index page)

- Assignment Source:
   - Manual: uses textarea rows from Faculty Assignment Rows.
   - Master: uses rows from Admin > Assignment Master.
- Rooms: one per line
- Working Days: number from 1 to 7
- Periods Per Day: number from 1 to 10
- Lunch Break Periods: comma-separated period numbers (for example 4 or 3,4)
- Faculty Daily Max: default max periods/day for every faculty
- Random Seed: optional integer for repeatable timetable generation
- Generation Scope: `all`, `class`, or `section`
- Scope Class / Scope Standard / Scope Section: used when generation scope is `class` or `section`
- Faculty Assignment Rows: one row per line in format (required in Manual mode)
   Class,Standard,Section,Subject,Teacher,Lectures[,Type[,AllowedRooms[,DailyMax]]]
- Section Home Classrooms: one row per line in format
   Class,Standard,Section,HomeRoom
- Faculty Daily Limit Overrides: one row per line in format
   FacultyName,MaxPeriodsPerDay
- Faculty Unavailability: one row per line in format
   FacultyName,Day,Period
- Fixed Slot Constraints: one row per line in format
   Class,Standard,Section,Subject,Teacher,Day,StartPeriod[,Duration[,Room]]

Example row:

Class-01,Year-1,A,Mathematics,Faculty-01,4,THEORY,,2

Example LAB row:

Class-01,Year-1,A,Programming Lab,Faculty-19,2,LAB,LAB-01|LAB-02|LAB-03|LAB-04|LAB-05|LAB-06|LAB-07|LAB-08|LAB-09|LAB-10,2

Example Section Home Classroom row:

Class-01,Year-1,A,CR-101

Example Faculty Daily Override row:

Faculty-01,7

Example Faculty Unavailability row:

Faculty-01,Tuesday,3

Example Fixed Slot row:

Class-01,Year-1,A,Mathematics,Faculty-01,2,1

Rules:

- LAB rows must have even lecture counts because LAB sessions are placed as contiguous 2-period blocks.
- `DailyMax` is optional; if omitted, the app computes a default daily cap from total lectures and working days.
- For fixed slots, `Day` can be day number (1-7) or day name (Monday-Sunday).
- `Duration` in fixed slots defaults to assignment session duration (THEORY=1, LAB=2) and must match assignment type when supplied.

## Export Endpoints

- /timetable/export/pdf

Notes:

- Excel/CSV/JSON exports are written to the `output/` folder during generation/publish steps.
- PDF export supports `?version_id=<id>` to export a specific saved version.

## API Endpoints

- /api/timetable/latest
- /api/timetable/class/latest
- /api/timetable/room/latest
- /api/timetable/faculty/latest

## Admin Workflow Routes

- /login
- /dashboard
- /timetable/published
- /timetable/upcoming
- /admin/versions
- /admin/versions/compare
- /admin/versions/<id>/view
- /admin/versions/<id>/manual-edit
- /admin/versions/<id>/approve
- /admin/versions/<id>/reject
- /admin/versions/<id>/publish
- /admin/audit
- /admin/users
- /admin/master/departments
- /admin/master/faculty
- /admin/master/rooms
- /admin/master/sections
- /admin/master/subjects
- /admin/master/assignments

## Security Defaults

The app now includes secure-by-default protections without changing normal user flow:

- Same-origin checks for state-changing requests (POST/PUT/PATCH/DELETE)
- Secure session cookie defaults (`HttpOnly`, `SameSite=Lax`)
- Login throttling for repeated failed sign-in attempts
- Minimum password policy for new/reset/changed passwords (default 10+ chars)

Optional environment variables:

- `TIMETABLE_COOKIE_SECURE=1` (recommended for HTTPS deployments)
- `TIMETABLE_TRUSTED_ORIGINS=https://your-domain.example`
- `TIMETABLE_MIN_PASSWORD_LENGTH=10`
- `TIMETABLE_LOGIN_WINDOW_SECONDS=900`
- `TIMETABLE_LOGIN_MAX_FAILURES=5`
- `TIMETABLE_LOGIN_LOCK_SECONDS=600`

## Security UI Integration

For a complete guide to security features in the user interface:
- **[SECURITY_UI_GUIDE.md](SECURITY_UI_GUIDE.md)** - UI integration, real-time validation, customization

Features include:
- Password policy requirements displayed on login and change-password forms
- Real-time validation feedback during password entry
- Admin interface for user and password management with policy enforcement
- Reusable security info component for admin pages

## Testing

Run lightweight tests locally:

1. `pip install -r requirements-dev.txt`
2. `pytest -q`

CI is included at `.github/workflows/ci.yml`.

## College Website Expansion Assets

- docs/COLLEGE_WEBSITE_BLUEPRINT.md
- docs/COLLEGE_WEBSITE_SCHEMA.sql

## Notes

- This project is intentionally independent from the legacy PHP/MySQL code in the repository.
- SQLite database is auto-created at instance/timetable.db when app starts.
- Use `python migrate_db.py` after pulling schema/model changes to upgrade an existing local DB safely.
- Change default admin credentials with env vars: TIMETABLE_ADMIN_USERNAME, TIMETABLE_ADMIN_PASSWORD, TIMETABLE_ADMIN_NAME.
