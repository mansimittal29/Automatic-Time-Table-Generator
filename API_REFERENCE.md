# Timetable Generator API Reference

This document provides detailed function signatures and usage examples for all new features implemented.

---

## 1. Scheduler Functions (timetable_generator.py)

### 1.1 Main Generation Function

```python
def generate_multi_section_timetable(
    assignment_payload: List[Dict[str, object]],
    rooms: List[str],
    working_days: int,
    periods_per_day: int,
    lunch_break_periods_by_day: Dict[int, Set[int]],
    section_home_rooms: Dict[str, str] | None = None,
    faculty_daily_default_max: int = 6,
    faculty_daily_limits: Dict[str, int] | None = None,
    random_seed: int | None = None,
    locked_section_cells: List[Dict[str, object]] | None = None,
    require_daily_free_period: bool = False,
) -> Tuple[
    List[Dict[str, object]],  # section_tables
    List[Dict[str, object]],  # class_tables
    List[Dict[str, object]],  # faculty_tables
    List[Dict[str, object]],  # room_tables
    Dict[str, object],        # optimization_payload
]
```

**Changes from Previous**:
- **`locked_section_cells`** (NEW): Pre-locked cells from existing version
  - Format: `[{"section_key": "...", "day": 0, "period": 0, "subject": "...", "teacher": "...", "room": "...", "is_lab": bool, "session_id": "..."}, ...]`
  - Optional; default None (no locked cells)
  - Cells are validated for bounds, overlaps, and conflicts
  
- **`require_daily_free_period`** (NEW): Enforce daily free period for theory faculty
  - Type: `bool`
  - Default: `False`
  - When `True`: Reduces daily teaching limit by 1 for faculty with theory load
  - Advisory warnings issued for faculty without actual free period

**Usage Example**:
```python
# Single scenario with locked slots
locked_cells = [
    {
        "section_key": "CS-1",
        "day": 0,
        "period": 2,
        "subject": "DSA",
        "teacher": "Prof. Smith",
        "room": "Lab-1",
        "is_lab": True,
        "session_id": "dsa-lab-1-a"
    }
]

section_tables, class_tables, faculty_tables, room_tables, summary = (
    generate_multi_section_timetable(
        assignment_payload=assignments,
        rooms=["Room-1", "Room-2"],
        working_days=5,
        periods_per_day=6,
        lunch_break_periods_by_day={0: {2}, 1: {2}, 2: {2}, 3: {2}, 4: {2}},
        locked_section_cells=locked_cells,
        require_daily_free_period=True,  # Enforce free periods
        random_seed=42
    )
)
```

---

### 1.2 Validator Function

```python
def validate_multi_section_timetable(
    days: List[str],
    periods: List[str],
    section_tables: List[Dict[str, object]],
    class_tables: List[Dict[str, object]],
    faculty_tables: List[Dict[str, object]],
    room_tables: List[Dict[str, object]],
    assignment_payload: List[Dict[str, object]],
    faculty_daily_limits: Dict[str, int] | None = None,
    require_daily_free_period: bool = False,
) -> List[str]
```

**Changes from Previous**:
- **`require_daily_free_period`** (NEW): Enable advisory checks for daily free periods
  - Type: `bool`
  - Default: `False`
  - When `True`: Issues warnings if theory faculty have no free period on a day

**Returns**: List of validation issues/warnings

**Usage Example**:
```python
issues = validate_multi_section_timetable(
    days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    periods=["9-10", "10-11", "11-12", "12-1", "2-3", "3-4"],
    section_tables=section_tables,
    class_tables=class_tables,
    faculty_tables=faculty_tables,
    room_tables=room_tables,
    assignment_payload=assignments,
    require_daily_free_period=True
)

for issue in issues:
    print(f"⚠️ {issue}")
```

---

## 2. Flask Backend Functions (app.py)

### 2.1 Analytics Computation

```python
def build_analytics_payload(
    prepared_payload: Dict[str, object]
) -> Dict[str, object]
```

**Input** (`prepared_payload`):
```python
{
    "days": ["Monday", "Tuesday", ...],
    "periods": ["09:00", "10:00", ...],
    "section_tables": [...],
    "class_tables": [...],
    "faculty_tables": [...],
    "room_tables": [...],
    "summary": {"scheduled_slots": 150, "utilization_percent": 85, ...}
}
```

**Output**:
```python
{
    "room_heatmap_rows": [
        {"room": "Lab-1", "day": "Monday", "usage_count": 5, "peak": True},
        ...
    ],
    "teacher_load_items": [
        {"teacher": "Prof. Smith", "mean_load": 4.5, "std_dev": 0.8, "detail": "4.5±0.8"},
        ...
    ],
    "fairness_score": 78.5,  # 0-100
    "subject_distribution_rows": [
        {"subject": "DSA", "day_0": 3, "day_1": 2, "day_2": 4, ...},
        ...
    ],
    "day_period_loads": {
        0: [2, 4, 5, 4, 3, 2],  # per-period load on day 0
        1: [2, 4, 5, 4, 3, 2],  # per-period load on day 1
    },
    "period_peak_counts": [
        {"period": "Period 1", "count": 12, "peak": False},
        {"period": "Period 3", "count": 25, "peak": True},  # Busiest
        ...
    ]
}
```

**Fairness Score Formula**:
```
CV = (std_dev / mean) × 100
fairness_score = max(0, 100 - CV)
```
- 0 = completely unfair (huge variance)
- 100 = perfectly fair (no variance)

**Usage Example**:
```python
analytics = build_analytics_payload(prepared_payload)
fairness_score = analytics["fairness_score"]
busiest_period = next((p for p in analytics["period_peak_counts"] if p["peak"]), None)
print(f"Fairness: {fairness_score}%")
print(f"Busiest Period: {busiest_period['period']}")
```

---

### 2.2 ICS Calendar Export

```python
def build_ics_calendar_text(
    version: TimetableVersion,
    days: List[str],
    periods: List[str],
    section_tables: List[Dict[str, object]],
    lunch_break_periods_by_day: Dict[int, Set[int]],
    faculty_filter: str = "",
    section_filter: str = ""
) -> str
```

**Parameters**:
- **`version`**: TimetableVersion ORM object (for metadata)
- **`faculty_filter`**: Faculty name to include (e.g., "Prof. Smith"); empty = all
- **`section_filter`**: Section name to include (e.g., "CS-1"); empty = all

**Configuration via Environment Variables**:
```bash
TIMETABLE_ICS_PERIOD_MINUTES=60        # Duration of each period
TIMETABLE_ICS_DAY_START_HOUR=9         # Start time (9 = 9:00 AM)
```

**Returns**: RFC 5545-compliant VCALENDAR string

**ICS Event Structure**:
```
VEVENT:
  UID: timetable-v{version}-s{section}-d{day}-p{period}-{timestamp}
  DTSTAMP: {timestamp}
  DTSTART: {start datetime}
  DTEND: {end datetime}
  SUMMARY: {subject} - {section}
  DESCRIPTION: {teacher} | {subject_code} | {room}
  LOCATION: {room}
```

**Usage Example**:
```python
# Export CS-1 section calendar
ics_text = build_ics_calendar_text(
    version=timetable_version,
    days=days,
    periods=periods,
    section_tables=section_tables,
    lunch_break_periods_by_day=lunch_break_periods_by_day,
    section_filter="CS-1"
)

# Return to browser
from flask import send_file, io
return send_file(
    io.BytesIO(ics_text.encode("utf-8")),
    mimetype="text/calendar",
    as_attachment=True,
    download_name="timetable-cs1.ics"
)
```

---

### 2.3 Absence Substitution

```python
def auto_apply_absence_substitutions(
    section_tables: List[Dict[str, object]],
    assignment_payload: List[Dict[str, object]],
    absent_faculty: str,
    day_index: int,
    period_index: int | None = None,
    lunch_break_periods_by_day: Dict[int, Set[int]] | None = None,
    faculty_daily_default_max: int = 6,
    faculty_daily_limits: Dict[str, int] | None = None
) -> Tuple[
    List[Dict[str, object]],  # updated_section_tables
    List[Dict[str, object]],  # substitutions_list
    List[str]                 # issues_list
]
```

**Parameters**:
- **`absent_faculty`**: Name of faculty who is absent (e.g., "Prof. Smith")
- **`day_index`**: Day (0-based); use None to apply to all days
- **`period_index`**: Period (0-based); use None to apply to all periods on the day

**Ranking Criteria**:
1. Same-subject match (faculty with experience teaching the subject)
2. Current day load (prefer less busy faculty today)
3. Total load (prefer lower overall workload)
4. Name (alphabetical tiebreaker)

**Returns**:
```python
(
    updated_section_tables,  # Deep copy with substitutions applied
    [
        {
            "original_faculty": "Prof. Smith",
            "subject": "DSA",
            "section": "CS-1",
            "day": 0,
            "period": 2,
            "new_faculty": "Prof. Jones",
            "reason": "Same-subject match, current_day_load=2"
        },
        ...
    ],
    [
        "No available faculty found for LAB session on day 0 period 2",
        ...
    ]
)
```

**Usage Example**:
```python
updated_tables, subs, issues = auto_apply_absence_substitutions(
    section_tables=section_tables,
    assignment_payload=assignments,
    absent_faculty="Prof. Smith",
    day_index=0,  # Monday
    period_index=None,  # All periods on Monday
    faculty_daily_limits=faculty_daily_limits
)

for sub in subs:
    print(f"✓ {sub['original_faculty']} → {sub['new_faculty']} ({sub['subject']})")

for issue in issues:
    print(f"⚠️ {issue}")

# Save as new draft version
new_version = persist_timetable_version(
    days=days,
    periods=periods,
    section_tables=updated_tables,
    summary={...},
    constraint_settings={...},
)
```

---

### 2.4 Locked Slot Parsing

```python
def parse_locked_slot_rows(
    raw_text: str,
    section_tables: List[Dict[str, object]],
    days: List[str],
    periods: List[str]
) -> Set[Tuple[str, int, int]]
```

**Input Format**:
```csv
SectionKey,Day,Period
CS-1,0,2
CS-1,1,*
CS-2,*,2
CS-3,Monday,3
```

**Wildcard Support**:
- `*` = applies to all values in that dimension
- `CS-1,0,*` = lock all periods on day 0 for CS-1
- `CS-1,*,2` = lock period 2 on all days for CS-1

**Returns**: `Set[(section_key, day_index, period_index), ...]`

**Usage Example**:
```python
locked_slots_csv = """SectionKey,Day,Period
CS-1,0,2
CS-1,0,3
"""

locked_slots = parse_locked_slot_rows(
    raw_text=locked_slots_csv,
    section_tables=section_tables,
    days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    periods=["09-10", "10-11", "11-12", "12-1", "2-3", "3-4"]
)

# Output: {("CS-1", 0, 2), ("CS-1", 0, 3)}
```

---

### 2.5 Locked Cell Builder

```python
def build_locked_cells_from_slots(
    section_tables: List[Dict[str, object]],
    locked_slots: Set[Tuple[str, int, int]],
    lunch_break_periods_by_day: Dict[int, Set[int]]
) -> List[Dict[str, object]]
```

**Returns**: List of cell dictionaries with full metadata:
```python
[
    {
        "section_key": "CS-1",
        "day": 0,
        "period": 2,
        "subject": "DSA",
        "teacher": "Prof. Smith",
        "room": "Lab-1",
        "is_lab": True,
        "session_id": "dsa-lab-1-a"
    },
    ...
]
```

**Usage Example**:
```python
locked_cells = build_locked_cells_from_slots(
    section_tables=section_tables,
    locked_slots={("CS-1", 0, 2), ("CS-1", 0, 3)},
    lunch_break_periods_by_day=lunch_break_periods_by_day
)

# Pass to generation
section_tables, _, _, _, summary = generate_multi_section_timetable(
    ...,
    locked_section_cells=locked_cells
)
```

---

### 2.6 Scenario Ranking

```python
def rank_scenario_candidate(
    summary: Dict[str, object],
    validation_issues: List[str]
) -> float
```

**Ranking Formula**:
```
score = (optimization_score × 1.25) + utilization_percent - (issue_count × 3.0)
```

**Components**:
- `optimization_score` from summary (soft constraint satisfaction, 0-100)
- `utilization_percent` from summary (% of slots filled)
- `issue_count` = number of validation_issues

**Returns**: Float rank (higher = better)

**Usage Example**:
```python
candidates = [
    {"seed": 1, "summary": {...}, "issues": []},
    {"seed": 2, "summary": {...}, "issues": ["issue1"]},
    {"seed": 3, "summary": {...}, "issues": ["issue1", "issue2"]},
]

for candidate in candidates:
    rank = rank_scenario_candidate(candidate["summary"], candidate["issues"])
    candidate["rank"] = rank

# Sort by rank descending
candidates.sort(key=lambda x: x["rank"], reverse=True)
best = candidates[0]
print(f"Best scenario: seed {best['seed']} with rank {best['rank']}")
```

---

### 2.7 Fix Suggestions

```python
def build_generation_fix_suggestions(
    form_values: Dict[str, str],
    generation_scope_description: str
) -> List[str]
```

**Detected Issues & Suggestions**:
| Issue | Suggestion |
|-------|-----------|
| No rooms | "Add at least one room in Rooms section" |
| No assignments | "Add assignment rows or click 'Load Starter Dataset'" |
| LAB with odd count | "Keep LAB lectures even (2, 4, 6, ...)" |
| Missing AllowedRooms | "Add AllowedRooms to every LAB row" |
| Low capacity | "Capacity is low. Increase rooms, days/periods, or reduce load" |
| All scenarios failed | "Set Scenario Runs > 1 to auto-compare and pick best" |

**Returns**: List of actionable fix suggestions (deduplicated)

**Usage Example**:
```python
try:
    generate_outputs(...)
except ValueError as e:
    flash(str(e), "danger")
    
    suggestions = build_generation_fix_suggestions(form_values, "All Sections")
    for suggestion in suggestions:
        flash(suggestion, "info")  # Show in UI as info-level message
```

---

### 2.8 Enhanced generate_outputs

```python
def generate_outputs(
    assignment_payload: List[Dict[str, object]],
    rooms: List[str],
    working_days: int,
    periods_per_day: int,
    lunch_break_periods_by_day: Dict[int, Set[int]],
    section_home_rooms: Dict[str, str] | None = None,
    faculty_daily_default_max: int = 6,
    faculty_daily_limits: Dict[str, int] | None = None,
    random_seed: int | None = None,
    locked_section_cells: List[Dict[str, object]] | None = None,
    require_daily_free_period: bool = False,
    write_output_files: bool = True
) -> Tuple[
    List[str],                # days
    List[str],                # periods
    List[Dict[str, object]],  # section_tables
    List[Dict[str, object]],  # class_tables
    List[Dict[str, object]],  # faculty_tables
    List[Dict[str, object]],  # room_tables
    Dict[str, object],        # summary
    List[str]                 # validation_issues
]
```

**Changes from Previous**:
- **`locked_section_cells`** (NEW): Pre-locked cells
- **`require_daily_free_period`** (NEW): Daily free period policy
- **`write_output_files`** (NEW): Control file writes (default True)
  - When `True`: Creates XLSX, CSV, JSON exports
  - When `False`: Skips file writes (for scenario comparison)

**Usage Example**:
```python
# Single generation with files
days, periods, section_tables, ..., summary, issues = generate_outputs(
    assignment_payload=assignments,
    rooms=rooms,
    working_days=5,
    periods_per_day=6,
    lunch_break_periods_by_day=lunch_breaks,
    require_daily_free_period=True,
    write_output_files=True  # Default
)

# Scenario comparison without intermediate files
results = []
for i in range(3):
    days, periods, ..., summary, issues = generate_outputs(
        ...,
        random_seed=100 + i,
        write_output_files=False  # Prevent spam
    )
    rank = rank_scenario_candidate(summary, issues)
    results.append({"seed": 100+i, "rank": rank, "summary": summary})

best = max(results, key=lambda x: x["rank"])
# Now write files for best
write_generated_output_files(days, periods, section_tables, ..., best["summary"], lunch_breaks)
```

---

## 3. Form Field Integration

### 3.1 New Form Fields

**In `index.html` HTML form**:

```html
<!-- Faculty daily free-period policy -->
<div class="form-group">
    <label>
        <input type="checkbox" name="faculty_daily_free_period" value="1" 
               {% if form_values.get('faculty_daily_free_period') == '1' %}checked{% endif %}>
        Enforce daily free period for theory faculty (recommended)
    </label>
    <small class="form-text text-muted">
        Faculty with theory load will have at least 1 free period per day for admin/meetings.
    </small>
</div>

<!-- Scenario runs for comparison -->
<div class="form-group">
    <label for="scenario_runs">Number of scenario runs (auto-select best):</label>
    <input type="number" id="scenario_runs" name="scenario_runs" 
           value="{{ form_values.get('scenario_runs', '1') }}" 
           min="1" max="12" class="form-control">
    <small class="form-text text-muted">
        1 = single generation | 2-12 = run multiple scenarios with different random seeds and auto-select best.
    </small>
</div>
```

### 3.2 Form Defaults (in Python)

```python
{
    ...
    "faculty_daily_free_period": "1",  # Enabled by default
    "scenario_runs": "1",               # Single run by default
    ...
}
```

---

## 4. HTTP Response Examples

### 4.1 ICS Export Response

```http
HTTP/1.1 200 OK
Content-Type: text/calendar
Content-Disposition: attachment; filename=timetable-cs1-20250110.ics

BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Timetable Generator//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:timetable-v42-scs1-d0-p2-20250110t100000z
DTSTAMP:20250110T100000Z
DTSTART:20250113T110000Z
DTEND:20250113T120000Z
SUMMARY:DSA - CS-1
DESCRIPTION:Prof. Smith | CS101 | Lab-1
LOCATION:Lab-1
END:VEVENT
...
END:VCALENDAR
```

---

## 5. Database Schema Changes

**No schema changes required**. New data is stored in existing columns:
- `TimetableVersion.constraint_settings` (JSON): Now includes:
  - `"require_daily_free_period": True/False`
  - `"scenario_runs": 1-12`
- `TimetableVersion.summary` (JSON): Now includes:
  - `"scenario_compare": {"runs": 3, "best_seed": 42, "best_rank": 85.5}` (if multi-scenario)

---

## 6. Error Handling

### 6.1 Locked Slot Errors

```python
ValueError: "Locked slot (CS-1, 0, 2) overlaps with fixed slot (CS-1, 0, 2)"
ValueError: "Locked slot (CS-1, 5, 0) is lunch break on day 5"
ValueError: "Section 'CS-99' in locked slots does not exist"
```

### 6.2 Scenario Errors

```python
ValueError: "All scenario runs failed. Review diagnostics and retry."
ValueError: "Scenario seed 42: No valid placement found for DSA in CS-1"
```

### 6.3 Substitution Errors

```python
"No available faculty found for DSA on day 0 period 2 (all candidates busy)"
"Faculty 'Prof. NonExistent' not found in assignment payload"
```

---

## 7. Migration Guide (from Previous Version)

**All changes are backward compatible**. No migration needed.

**Enabling new features**:

1. **Locked Slots** (opt-in):
   - Pass `locked_section_cells=[...]` to `generate_multi_section_timetable()`
   - Or leave empty/None (default) to use existing behavior

2. **Daily Free Period** (opt-in):
   - Pass `require_daily_free_period=True` to generation functions
   - Or omit (default False) to use existing behavior

3. **Scenario Comparison** (opt-in):
   - Set form input `scenario_runs > 1`
   - Or leave at default 1 (existing single-generation behavior)

4. **Analytics** (new route):
   - Only available for new `/admin/analytics/<version_id>` route
   - Existing routes unaffected

---

**API Reference Version**: 1.0  
**Last Updated**: 2025  
**Status**: Stable (no breaking changes planned)
