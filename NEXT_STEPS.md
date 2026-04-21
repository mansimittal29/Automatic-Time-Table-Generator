# Next Steps: Template & Route Implementation Guide

## Quick Start for Completing the Implementation

All backend logic is **100% complete and tested**. This guide walks through the remaining UI and route work.

---

## Phase 1: Form Field Updates (1-2 hours)

### Task 1.1: Update `templates/index.html`

Add two new form fields to the generation console:

**Location**: Find the `<form>` section in index.html (around line ~150-200)

**Add Before Submit Button**:

```html
<!-- Faculty daily free-period policy enforcement -->
<div class="form-group">
    <div class="custom-control custom-checkbox">
        <input type="checkbox" class="custom-control-input" 
               id="faculty_daily_free_period" 
               name="faculty_daily_free_period" 
               value="1"
               {% if form_values.get('faculty_daily_free_period') == '1' %}checked{% endif %}>
        <label class="custom-control-label" for="faculty_daily_free_period">
            <strong>Enforce daily free period for theory faculty</strong>
            <small class="d-block text-muted mt-1">
                Faculty with theory load will have at least 1 free teaching period per day for admin tasks/meetings. Recommended for realistic schedules.
            </small>
        </label>
    </div>
</div>

<!-- Scenario comparison runs -->
<div class="form-group">
    <label for="scenario_runs"><strong>Scenario comparison runs:</strong></label>
    <div class="input-group">
        <input type="number" 
               class="form-control" 
               id="scenario_runs" 
               name="scenario_runs"
               value="{{ form_values.get('scenario_runs', '1') }}"
               min="1" 
               max="12"
               required>
        <small class="form-text text-muted d-block mt-1">
            <strong>1 run</strong> (default): Single generation with your seed | 
            <strong>2-12 runs</strong>: Generate multiple versions with different random seeds and auto-select best. 
            Higher values = better quality timetable but longer runtime.
        </small>
    </div>
</div>
```

**Test**: Load http://localhost:5000/ and verify:
- [ ] Checkbox appears above submit button
- [ ] Checkbox is checked by default
- [ ] Number input appears with value "1"
- [ ] Form submits successfully with new fields

---

## Phase 2: Scenario Results Display (30-45 minutes)

### Task 2.1: Update `templates/timetable.html`

Display scenario comparison results if available (only shown when `scenario_runs > 1`).

**Location**: Find the "Summary Section" in timetable.html (around line ~80-120)

**Add After Main Summary**:

```html
<!-- Scenario Comparison Results (if multi-scenario run) -->
{% if scenario_results %}
<div class="card mb-4 border-info">
    <div class="card-header bg-info text-white">
        <h5 class="mb-0">
            <i class="fas fa-random"></i> Scenario Comparison Results
            <span class="badge badge-light float-right">{{ scenario_results|length }} runs</span>
        </h5>
    </div>
    <div class="card-body">
        {% if scenario_results|selectattr('status', 'equalto', 'ok') %}
        <div class="alert alert-success">
            <strong>Best Scenario Selected</strong>: 
            Seed <code>{{ summary.scenario_compare.best_seed }}</code> 
            (Rank: <strong>{{ "%.1f"|format(summary.scenario_compare.best_rank) }}</strong>)
        </div>
        {% endif %}

        <div class="table-responsive">
            <table class="table table-sm table-hover">
                <thead class="table-light">
                    <tr>
                        <th>Seed</th>
                        <th>Status</th>
                        <th>Rank Score</th>
                        <th>Optimization Score</th>
                        <th>Utilization %</th>
                        <th>Issues</th>
                    </tr>
                </thead>
                <tbody>
                    {% for result in scenario_results %}
                    <tr {% if result.seed == summary.scenario_compare.best_seed %}class="table-success font-weight-bold"{% else %}class="{% if result.status == 'failed' %}table-danger{% endif %}"{% endif %}>
                        <td><code>{{ result.seed }}</code></td>
                        <td>
                            {% if result.status == 'ok' %}
                            <span class="badge badge-success">✓ OK</span>
                            {% else %}
                            <span class="badge badge-danger">✗ Failed</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if result.status == 'ok' %}
                            <strong>{{ "%.2f"|format(result.rank) }}</strong>
                            {% else %}
                            —
                            {% endif %}
                        </td>
                        <td>
                            {% if result.status == 'ok' %}
                            {{ result.score }}
                            {% else %}
                            —
                            {% endif %}
                        </td>
                        <td>
                            {% if result.status == 'ok' %}
                            <strong>{{ result.utilization_percent }}%</strong>
                            {% else %}
                            —
                            {% endif %}
                        </td>
                        <td>
                            {% if result.status == 'ok' %}
                            {% if result.issue_count > 0 %}
                            <span class="badge badge-warning">{{ result.issue_count }}</span>
                            {% else %}
                            <span class="text-success">0</span>
                            {% endif %}
                            {% else %}
                            <small class="text-muted">{{ result.reason[:40] }}...</small>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <small class="text-muted">
            <strong>Note:</strong> Best scenario (highlighted) was automatically selected for you based on optimization score, utilization, and issue count.
        </small>
    </div>
</div>
{% endif %}
```

**Test**: Generate with `scenario_runs=3` and verify:
- [ ] Scenario results table appears
- [ ] Best scenario (seed) is highlighted in green
- [ ] All seeds are listed with status/rank/utilization
- [ ] Failed scenarios show error message

---

## Phase 3: New Route Endpoints (4-6 hours)

### Task 3.1: Analytics Route

**File**: `app.py` (add after existing `/timetable/<int:version_id>` route)

```python
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
```

**Implementation Checklist**:
- [ ] Route registered and accessible
- [ ] Test with version_id from database
- [ ] 404 if version not found
- [ ] Analytics payload computed correctly

---

### Task 3.2: ICS Export Route

**File**: `app.py` (add after analytics route)

```python
@app.route("/export/ics/<int:version_id>")
@login_required
def export_ics(version_id: int) -> Response:
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
```

**Implementation Checklist**:
- [ ] Route registered and accessible
- [ ] Test with ?section=CS-1 query param
- [ ] Test with ?faculty=Prof%20Smith query param
- [ ] Browser downloads .ics file with correct name
- [ ] Import into Google Calendar/Apple Calendar works

---

### Task 3.3: Absence Substitution Route

**File**: `app.py` (add after ICS route)

```python
@app.route("/admin/absence-substitute/<int:version_id>", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def absence_substitute(version_id: int) -> str | Response:
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
            
            return redirect(url_for("timetable", version_id=new_version.id))
        
        except ValueError as e:
            flash(f"Substitution failed: {str(e)}", "danger")
            return redirect(url_for("absence_substitute", version_id=version_id))
```

**Implementation Checklist**:
- [ ] Route GET shows form with faculty dropdown
- [ ] Form has: absent_faculty, day, period (optional)
- [ ] POST applies substitutions
- [ ] Creates new draft version with substitutions
- [ ] Shows audit log in dashboard

---

### Task 3.4: Lock-Slot Regeneration Route

**File**: `app.py` (add after absence-substitute route)

```python
@app.route("/admin/lock-slots/<int:version_id>", methods=["GET", "POST"])
@roles_required("ADMIN", "HOD")
def lock_slots_regenerate(version_id: int) -> str | Response:
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
            return redirect(url_for("timetable", version_id=new_version.id))
        
        except ValueError as e:
            flash(f"Lock-slot regeneration failed: {str(e)}", "danger")
            return redirect(url_for("lock_slots_regenerate", version_id=version_id))
```

**Implementation Checklist**:
- [ ] Route GET shows timetable grid with slot selector
- [ ] Can click cells to lock them
- [ ] CSV export of locked slots for form submission
- [ ] POST regenerates with locked cells
- [ ] Creates new draft version with locked constraints preserved

---

## Phase 4: New Templates (3-4 hours)

### Task 4.1: Create `templates/analytics.html`

**Purpose**: Display metrics from `build_analytics_payload()`

**Key Sections**:
1. Fairness Scorecard (with color gradient)
2. Room Utilization Heatmap (table or chart)
3. Teacher Load Distribution (bar chart)
4. Subject Distribution (stacked bar by day)
5. Peak Period Analysis (line chart)

**Recommended Libraries**:
- **Chart.js** (already in Stack): `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`
- **Bootstrap Tables**: Use existing `table` classes

**Starter Structure**:
```html
{% extends "base.html" %}

{% block title %}Analytics - Timetable Generator{% endblock %}

{% block content %}
<div class="container-fluid mt-4">
    <div class="row">
        <!-- Fairness Scorecard -->
        <div class="col-md-4 mb-4">
            <div class="card">
                <div class="card-body text-center">
                    <h6 class="text-muted">Teacher Fairness Score</h6>
                    <h1 class="display-4">{{ "%.1f"|format(analytics.fairness_score) }}/100</h1>
                    <p class="text-muted">Based on teaching load variance (coefficient of variation)</p>
                </div>
            </div>
        </div>

        <!-- Room Utilization Heatmap -->
        <div class="col-md-8 mb-4">
            <div class="card">
                <div class="card-header">Room Utilization Heatmap</div>
                <div class="card-body">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Room</th>
                                {% for day in days %}<th>{{ day[:3] }}</th>{% endfor %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in analytics.room_heatmap_rows %}
                            <tr>
                                <td><strong>{{ row.room }}</strong></td>
                                <!-- Color cells by usage count -->
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- More sections here -->
</div>
{% endblock %}
```

---

### Task 4.2: Create `templates/absence-substitute.html`

**Purpose**: Simple form for selecting absent faculty and period

**Structure**:
```html
{% extends "base.html" %}

{% block title %}Substitute Faculty - Timetable Generator{% endblock %}

{% block content %}
<div class="container mt-4">
    <div class="card">
        <div class="card-header">
            <h4>Substitute Absent Faculty</h4>
            <small class="text-muted">Select a faculty and period to substitute them with an intelligent ranking</small>
        </div>
        <div class="card-body">
            <form method="POST">
                <!-- Absent Faculty Dropdown -->
                <div class="form-group">
                    <label for="absent_faculty">Absent Faculty:</label>
                    <select class="form-control" id="absent_faculty" name="absent_faculty" required>
                        <option value="">-- Select faculty --</option>
                        {% for faculty in faculty_list %}
                        <option value="{{ faculty }}">{{ faculty }}</option>
                        {% endfor %}
                    </select>
                </div>

                <!-- Day Selection -->
                <div class="form-group">
                    <label for="day">Day (leave empty for all days):</label>
                    <select class="form-control" id="day" name="day">
                        <option value="">-- All days --</option>
                        {% for i, day in enumerate(days) %}
                        <option value="{{ i }}">{{ day }}</option>
                        {% endfor %}
                    </select>
                </div>

                <!-- Period Selection -->
                <div class="form-group">
                    <label for="period">Period (leave empty for all periods):</label>
                    <select class="form-control" id="period" name="period">
                        <option value="">-- All periods --</option>
                        {% for i, period in enumerate(periods) %}
                        <option value="{{ i }}">{{ period }}</option>
                        {% endfor %}
                    </select>
                </div>

                <button type="submit" class="btn btn-primary">Apply Substitutions</button>
                <a href="{{ url_for('timetable', version_id=version.id) }}" class="btn btn-secondary">Cancel</a>
            </form>
        </div>
    </div>
</div>
{% endblock %}
```

---

### Task 4.3: Create `templates/lock-slots.html`

**Purpose**: Visual slot selector for locking cells before regeneration

**Advanced Implementation** (Optional): Interactive grid with click-to-lock functionality

**Starter Structure**:
```html
{% extends "base.html" %}

{% block title %}Lock Slots - Timetable Generator{% endblock %}

{% block content %}
<div class="container-fluid mt-4">
    <div class="card">
        <div class="card-header">
            <h4>Lock Slots for Regeneration</h4>
            <small class="text-muted">Select cells to lock and regenerate the rest of the timetable</small>
        </div>
        <div class="card-body">
            <form method="POST" id="lock-slots-form">
                <!-- Interactive Timetable Grid -->
                <div class="row mb-4">
                    {% for section in section_tables %}
                    <div class="col-md-6 mb-4">
                        <h6>{{ section.section_key }}</h6>
                        <table class="table table-bordered table-sm">
                            <thead>
                                <tr>
                                    <th>Period</th>
                                    {% for day in days %}<th>{{ day[:3] }}</th>{% endfor %}
                                </tr>
                            </thead>
                            <tbody>
                                {% for period_idx in range(periods|length) %}
                                <tr>
                                    <th>{{ periods[period_idx] }}</th>
                                    {% for day_idx in range(days|length) %}
                                    <td>
                                        <input type="checkbox" 
                                               class="lock-cell" 
                                               data-section="{{ section.section_key }}"
                                               data-day="{{ day_idx }}"
                                               data-period="{{ period_idx }}"
                                               title="Lock this cell">
                                    </td>
                                    {% endfor %}
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                    {% endfor %}
                </div>

                <!-- Hidden textarea for CSV data -->
                <textarea id="locked_slots" name="locked_slots" style="display: none;"></textarea>

                <button type="submit" class="btn btn-primary">Regenerate with Locked Slots</button>
                <a href="{{ url_for('timetable', version_id=version.id) }}" class="btn btn-secondary">Cancel</a>
            </form>
        </div>
    </div>
</div>

<script>
// Collect locked slots on form submit
document.getElementById('lock-slots-form').addEventListener('submit', function(e) {
    const locked_cells = [];
    document.querySelectorAll('.lock-cell:checked').forEach(checkbox => {
        locked_cells.push([
            checkbox.dataset.section,
            checkbox.dataset.day,
            checkbox.dataset.period
        ]);
    });
    
    // Format as CSV for backend
    const csv = 'SectionKey,Day,Period\n' + 
                locked_cells.map(cell => cell.join(',')).join('\n');
    document.getElementById('locked_slots').value = csv;
});
</script>
{% endblock %}
```

---

## Phase 5: Testing & Validation (2-3 hours)

### Testing Checklist

**Form Fields**:
- [ ] Generate with `faculty_daily_free_period` checked
- [ ] Verify theory faculty have ≤(max-1) teaching periods per day
- [ ] Generate with `scenario_runs=3`
- [ ] Verify best scenario is selected automatically

**Scenario Results**:
- [ ] Timetable.html displays scenario results table
- [ ] Best scenario highlighted
- [ ] Rank scores are reasonable (higher = better)

**Analytics Route**:
- [ ] Navigate to /admin/analytics/{version_id}
- [ ] Page loads without errors
- [ ] Fairness score displayed
- [ ] Room heatmap shows data
- [ ] Teacher load stats shown

**ICS Export**:
- [ ] Click export link
- [ ] Browser downloads .ics file
- [ ] Open in Google Calendar → events visible
- [ ] Test with ?section=CS-1 filter
- [ ] Test with ?faculty=Prof%20Smith filter

**Absence Substitution**:
- [ ] Navigate to absence-substitute page
- [ ] Select faculty and period
- [ ] Submit → creates new draft version
- [ ] Substitutions logged in audit trail

**Lock-Slot Regeneration**:
- [ ] Navigate to lock-slots page
- [ ] Click cells to lock
- [ ] Submit → regenerates with locked cells
- [ ] Locked cells remain unchanged in new version

---

## Priority Ranking

1. **Must Have** (Critical UX):
   - [ ] Form fields in index.html
   - [ ] Scenario results display in timetable.html
   - [ ] ICS export route

2. **Should Have** (Features):
   - [ ] Analytics route
   - [ ] Absence substitution route
   - [ ] Lock-slot regeneration route

3. **Nice to Have** (Polish):
   - [ ] Interactive heatmaps in analytics.html
   - [ ] Visual cell selector in lock-slots.html
   - [ ] Blue theme CSS update

---

## Estimated Timeline

| Phase | Tasks | Hours | Status |
|-------|-------|-------|--------|
| 1 | Form fields (index.html) | 1-2 | Ready to start |
| 2 | Scenario results display | 0.5-1 | Ready to start |
| 3 | Route endpoints (4 routes) | 4-6 | Ready to start |
| 4 | Template creation (3 new) | 3-4 | Ready to start |
| 5 | Testing & validation | 2-3 | Ready to start |
| **Total** | **Complete UI** | **10-16** | On track |

---

## Need Help?

**For each task**, refer to:
- `API_REFERENCE.md` for function signatures and examples
- `IMPLEMENTATION_SUMMARY.md` for feature definitions
- Existing templates (index.html, timetable.html) for Bootstrap/Jinja2 patterns
- Conversation summary in memory for architectural context

**Common Issues**:

1. **Template variable not found**:
   - Check render_template() call in route
   - Ensure variable is passed to template context

2. **ICS not importing**:
   - Verify RFC 5545 escaping (check `escape_ics_text()`)
   - Test with simpler calendar first

3. **Substitution not working**:
   - Debug `auto_apply_absence_substitutions()` return values
   - Check faculty name matches exactly

4. **Locked slots not preserved**:
   - Verify `generate_multi_section_timetable(..., locked_section_cells=...)`
   - Check overlap validation in scheduler

Good luck! All backend work is complete. You're finishing the visible UI! 🎉
