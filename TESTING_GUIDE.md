# Phase 5: Testing & Validation Guide

## Overview
All backend logic and UI/templates are now complete. This guide will walk you through systematic testing of all 7 features and 4 new routes.

**Status**: ✅ Backend Ready | ✅ UI Complete | ⏳ Testing Needed

---

## 1. Setup & Prerequisites

### Database Check
```bash
# Ensure database is initialized
python -c "from timetable_generator.database import db, Base; print('Database ready')"
```

### Flask App Check
```bash
# Start the Flask development server
python app.py
# Should output: Running on http://127.0.0.1:5000
```

### Browser Check
- Open http://127.0.0.1:5000 in Chrome/Firefox/Edge
- Login with test credentials (ADMIN role recommended)

---

## 2. Testing Checklist by Feature

### FEATURE 1: Form Fields (faculty_daily_free_period + scenario_runs)

**Location**: `/` (Home page, after completing master data)

**Test Case 1.1**: Form Fields Present
- [ ] Navigate to generate timetable form (/)
- [ ] Verify "faculty_daily_free_period" checkbox visible below subject assignments
- [ ] Verify "scenario_runs" number input visible with range 1-12
- [ ] Default values: checkbox checked, scenario_runs = 1

**Test Case 1.2**: Default Values Submitted
- [ ] Fill all required fields (master data)
- [ ] Leave new fields at defaults
- [ ] Click "Generate Timetable"
- [ ] Should succeed with faculty daily free period enabled and 1 scenario

**Test Case 1.3**: Multiple Scenarios
- [ ] Fill all required fields
- [ ] Set `scenario_runs = 3`
- [ ] Uncheck `faculty_daily_free_period`
- [ ] Click "Generate Timetable"
- [ ] Should generate timetable and show scenario results (see below)

**Test Case 1.4**: Checkbox Behavior
- [ ] Check/uncheck `faculty_daily_free_period`
- [ ] Verify checkbox state is preserved on form refresh
- [ ] Generate with box checked → verify theory faculty have max (daily_max-1) classes
- [ ] Generate with box unchecked → verify no such restriction

---

### FEATURE 2: Scenario Comparison with Auto-Selection

**Location**: Timetable display page after generation

**Test Case 2.1**: Single Scenario (Default)
- [ ] Generate with `scenario_runs = 1`
- [ ] Verify "Scenario Comparison Results" table NOT visible
- [ ] Only one versio created in database

**Test Case 2.2**: Multiple Scenarios - Results Table
- [ ] Generate with `scenario_runs = 3`
- [ ] On timetable page, scroll to "Scenario Comparison Results" section
- [ ] Verify table has 3 rows (one per seed)
- [ ] Columns visible: Seed | Status | Rank Score | Optimization Score | Utilization % | Issues

**Test Case 2.3**: Scenario Status Badges
- [ ] All rows should have "Status" column
- [ ] Successful scenarios: Green "✓ OK" badge
- [ ] Failed scenarios: Red "✗ Failed" badge
- [ ] Check that rank scores are only shown for successful scenarios

**Test Case 2.4**: Best Scenario Highlight
- [ ] Highest rank score row should have green background
- [ ] Green row should show "Best Scenario Selected" message above table
- [ ] Message shows: Seed + Rank score

**Test Case 2.5**: Utilization Percentage
- [ ] All successful scenarios show utilization %
- [ ] Values between 0-100
- [ ] Failed scenarios show "—" (dash)

---

### FEATURE 3: Faculty Daily Free-Period Enforcement

**Location**: Scheduler behavior in app.py + timetable verification

**Test Case 3.1**: Policy Enabled
- [ ] Generate with `faculty_daily_free_period = CHECKED`
- [ ] For each theory faculty (not just labs), verify:
  - Open browser console → timetable.html
  - Count their classes per day across all sections/periods
  - Theory faculty should have AT LEAST 1 free period each day
  - E.g., if faculty has 5 max daily, schedule shows ≤4 classes per day

**Test Case 3.2**: Policy Disabled
- [ ] Generate with `faculty_daily_free_period = UNCHECKED`
- [ ] Theory faculty can now have full load per day
- [ ] Verify count increases expected by ~20%

**Test Case 3.3**: Conflict Handling
- [ ] Set high load + faculty capacity constraints
- [ ] Enable free-period policy
- [ ] Generation should not fail (should either succeed or show graceful error)

---

### FEATURE 4: Conflict Fix Suggestions

**Location**: Flash messages after failed generation

**Test Case 4.1**: Trigger a Generation Failure
- [ ] Create impossible constraint scenario:
  - Too many faculty, too few rooms
  - Conflicting lunch break times
  - Duplicate subject assignments
- [ ] Submit generation
- [ ] Expect failure message

**Test Case 4.2**: Suggestions Displayed
- [ ] Failed generation should show flash message with suggestions
- [ ] Examples: "Add at least 2 rooms", "Reduce faculty daily max", "Check lunch break config"
- [ ] Suggestions should be actionable

---

### FEATURE 5: ICS Calendar Export (RFC 5545)

**Location**: `/export/ics/<version_id>` and button on timetable page

**Test Case 5.1**: Export Button Visible
- [ ] On timetable page, look for "Export Calendar" or similar button
- [ ] Verify button visible for ADMIN/HOD/FACULTY roles

**Test Case 5.2**: Download ICS File
- [ ] Click export button for specific section
- [ ] Browser downloads `.ics` file
- [ ] Filename format: `timetable-[SECTION]-[VERSION_LABEL].ics`
- [ ] File size > 1KB (should contain multiple events)

**Test Case 5.3**: ICS Format Validation
- [ ] Open downloaded .ics file in text editor
- [ ] Verify it contains:
  - `BEGIN:VCALENDAR` and `END:VCALENDAR`
  - `PRODID:-//Timetable Generator//EN` (or similar)
  - `VERSION:2.0`
  - `BEGIN:VEVENT` ... `END:VEVENT` blocks (one per class)
  - Each event has: `DTSTART`, `DTEND`, `SUMMARY`, `LOCATION`

**Test Case 5.4**: Import to Calendar - Google Calendar
- [ ] Go to Google Calendar → Settings → Import & Export
- [ ] Upload the downloaded .ics file
- [ ] Verify all events imported correctly
- [ ] Check 3-5 random events: timing, title, location match timetable

**Test Case 5.5**: Import to Calendar - Outlook/Apple
- [ ] Try importing into Microsoft Outlook or Apple Calendar
- [ ] Verify same validation as Test Case 5.4

**Test Case 5.6**: Faculty Filter
- [ ] Export with filter: `?faculty=Prof%20Smith`
- [ ] Open .ics file
- [ ] Verify only Prof. Smith's classes are included
- [ ] Try other faculty filters

**Test Case 5.7**: Section Filter
- [ ] Export with filter: `?section=CS-1`
- [ ] Verify only CS-1 classes are included

---

### FEATURE 6: Analytics Dashboard with Fairness Metrics

**Location**: `/admin/analytics/<version_id>`

**Test Case 6.1**: Route Accessibility
- [ ] On timetable page, find "Analytics" button/link
- [ ] Click → should navigate to `/admin/analytics/{version_id}`
- [ ] Page should load without errors

**Test Case 6.2**: Fairness Scorecard
- [ ] Verify "Teacher Fairness Score" card visible
- [ ] Score is 0-100 number
- [ ] Color coding: Red (<60), Yellow (60-80), Green (>80)
- [ ] Loading note: "based on teaching load variance"

**Test Case 6.3**: Quick Stats
- [ ] Verify 4 cards visible:
  1. Total Scheduled Slots (number)
  2. Room Utilization % (number)
  3. Total Conflicts (number)
  4. Average Teacher Load (number)
- [ ] All values should be reasonable numbers, not NaN or negative

**Test Case 6.4**: Room Utilization Heatmap
- [ ] Table showing: Room | Days columns | Total column
- [ ] Each cell colored by utilization:
  - Red (≥80%), Yellow (60-79%), Green (40-59%), Light (≤39%)
- [ ] Data should match actual timetable room assignments

**Test Case 6.5**: Teacher Load Distribution
- [ ] Table showing all faculty with:
  - Teacher Name
  - Classes Assigned (count)
  - Subjects (count)
  - Working Days (count)
  - Load Graph (progress bar)
- [ ] Progress bars indicate relative load
- [ ] All faculty from timetable should be listed

**Test Case 6.6**: Peak Period Analysis
- [ ] Table showing periods with:
  - Period name
  - Total Classes
  - Avg Room Utilization %
  - Peak Load %
  - Load Graph
- [ ] Busiest period should be clearly identifiable
- [ ] Load graphs should show variation across periods

**Test Case 6.7**: Subject Distribution
- [ ] Table showing subjects across days
- [ ] Can verify distribution is balanced or identify imbalances

---

### FEATURE 7: Faculty Leave/Substitution Auto-Fill

**Location**: `/admin/absence-substitute/<version_id>`

**Test Case 7.1**: Form Accessibility
- [ ] On timetable page, find "Substitute Faculty" button
- [ ] Click → navigate to absence-substitute page
- [ ] Form loads without errors

**Test Case 7.2**: Faculty Dropdown
- [ ] Dropdown lists all faculty in current timetable
- [ ] Faculty names should be readable
- [ ] Verify at least 5 faculty listed (or all available)

**Test Case 7.3**: Day/Period Selectors
- [ ] Day dropdown shows all working days (or "All days" option)
- [ ] Period dropdown shows all periods (or "All periods" option)
- [ ] Selecting a day should be optional

**Test Case 7.4**: Substitution - Full Faculty
- [ ] Select a faculty member
- [ ] Leave day/period empty
- [ ] Submit
- [ ] Should create NEW draft version with substitutions
- [ ] Flash message: "Successfully substituted X assignment(s)"
- [ ] Show individual substitutions (e.g., "Prof. Smith → Prof. Johnson (Physics)")

**Test Case 7.5**: Substitution - Specific Day
- [ ] Select a faculty and a specific day
- [ ] Submit
- [ ] Only that day's classes should be substituted
- [ ] Other days' classes remain with original faculty

**Test Case 7.6**: Substitution - Specific Period
- [ ] Select a faculty and specific period
- [ ] Submit
- [ ] Only that period across all days should be substituted

**Test Case 7.7**: Audit Logging
- [ ] Check audit logs in dashboard
- [ ] Find action "FACULTY_SUBSTITUTED"
- [ ] Verify details include: source_version_id, absent_faculty, substitutions_count

---

### FEATURE 4B (Routes): Lock-Slot Regeneration

**Location**: `/admin/lock-slots/<version_id>`

**Test Case 4B.1**: Route Accessibility
- [ ] On timetable page, find "Lock & Regenerate" button
- [ ] Click → navigate to lock-slots page
- [ ] Slot selector grid should load

**Test Case 4B.2**: Slot Selector UI
- [ ] Multiple section timetables displayed (side by side or stacked)
- [ ] Each section shows grid: Periods × Days
- [ ] Each cell has a checkbox
- [ ] Clicking cell should highlight/toggle it
- [ ] Counter shows "Total locked: 0" initially

**Test Case 4B.3**: Lock Selection
- [ ] Click 5-10 random cells across different sections
- [ ] Counter should update: "Total locked: 5" (or actual count)
- [ ] Locked cells should have visual highlight (background color)
- [ ] Clicking again should deselect

**Test Case 4B.4**: Clear All Button
- [ ] Click "Clear All"
- [ ] Confirm dialog appears
- [ ] All checkboxes cleared
- [ ] Counter resets to 0

**Test Case 4B.5**: Submit Without Selection
- [ ] Click "Regenerate with Locked Slots" with no cells selected
- [ ] Alert: "Please select at least one cell to lock"
- [ ] Prevent form submission

**Test Case 4B.6**: Submit With Selections
- [ ] Select 5-10 cells
- [ ] Click "Regenerate with Locked Slots"
- [ ] Form submits
- [ ] New draft version created
- [ ] Flash: "Timetable regenerated successfully with X locked cells"

**Test Case 4B.7**: Locked Cells Preserved
- [ ] Look at new timetable for locked cells
- [ ] Verify locked cells have exact same content as before
- [ ] Other cells changed (regenerated)

**Test Case 4B.8**: Audit Logging
- [ ] Check audit trail
- [ ] Find "TIMETABLE_REGENERATED_WITH_LOCKS" action
- [ ] Details: source_version_id, locked_cells_count, scheduled_slots

---

## 3. Integration Tests (End-to-End Flows)

### Flow A: Generate → Scenario Comparison → Best Auto-Selected
```
1. Fill form with scenario_runs=5
2. Submit
3. Verify 5 scenarios generated
4. Verify best scenario selected (green highlight)
5. Verify only best scenario's timetable displayed
6. Verify rank scores reasonable (0-100)
```

### Flow B: Generate → Analyze Fairness → Improve → Substitute
```
1. Generate timetable
2. Open analytics
3. Note fairness score (e.g., 65)
4. Go to substitution
5. Substitute one heavy-loaded faculty
6. Re-open analytics
7. Verify fairness score improved
```

### Flow C: Generate → Lock Labs → Regenerate Theories
```
1. Generate timetable
2. Identify all lab sessions
3. Lock all lab slots
4. Regenerate (theories will change, labs stay same)
5. Verify lab slots exactly same, theory slots changed
```

### Flow D: Generate → Export → Import to Calendar → Verify
```
1. Generate timetable
2. Export as ICS
3. Import to Google Calendar
4. Verify 10 random events match timetable exactly
5. Verify times, days, locations all correct
```

---

## 4. Browser Compatibility Testing

Test on at least 3 browsers:

| Browser | Version | Form Fields | Analytics | Lock Slots | Status |
|---------|---------|-------------|-----------|-----------|--------|
| Chrome | Latest | [ ] | [ ] | [ ] | |
| Firefox | Latest | [ ] | [ ] | [ ] | |
| Edge | Latest | [ ] | [ ] | [ ] | |
| Safari | Latest | [ ] | [ ] | [ ] | |

---

## 5. Performance Testing

### Test Case P1: Large Dataset
- [ ] Master data with 50+ faculty, 20+ rooms, 100+ sections
- [ ] Generate with scenario_runs=10
- [ ] Should complete in < 2 minutes
- [ ] All features still responsive

### Test Case P2: Analytics Response
- [ ] On large timetable, open analytics
- [ ] Page should load and render in < 3 seconds
- [ ] Heatmap should be responsive to scrolling

### Test Case P3: ICS Export Size
- [ ] Export large timetable (500+ events)
- [ ] .ics file size should be < 10MB
- [ ] Calendar import should not timeout

---

## 6. Error Handling Tests

### Test Case E1: Invalid Version ID
- [ ] Try `/admin/analytics/99999`
- [ ] Should show "Timetable version not found" and redirect

### Test Case E2: Missing Required Fields (Substitution)
- [ ] Submit substitution form with no faculty selected
- [ ] Should show validation error

### Test Case E3: No Master Data
- [ ] Try to generate with incomplete assignments
- [ ] Should show helpful error message with suggestions

### Test Case E4: Concurrent Regeneration
- [ ] Lock slots and submit
- [ ] Immediately submit again
- [ ] Should handle gracefully (queue or lock or show message)

---

## 7. Database Integrity Tests

### Test Case D1: Version Creation
- [ ] Generate timetable
- [ ] Check database: TimetableVersion row created
- [ ] payload column contains valid JSON
- [ ] summary column contains valid JSON

### Test Case D2: Audit Logging
- [ ] Generate, export, substitute, lock-regen
- [ ] Check AuditLog table
- [ ] Verify all 4 actions logged with correct details

### Test Case D3: Data Persistence
- [ ] Generate version 1
- [ ] Generate version 2 (with scenario)
- [ ] Generate version 3 (lock-regen from version 2)
- [ ] Verify all 3 versions exist independently
- [ ] Verify no data corruption between versions

---

## 8. Security Tests

### Test Case S1: RBAC - Analytics
- [ ] Login as STUDENT
- [ ] Try to access `/admin/analytics/1`
- [ ] Should redirect to login or show 403

### Test Case S2: RBAC - Substitution
- [ ] Login as FACULTY
- [ ] Try to access substitution form
- [ ] Should redirect or show 403

### Test Case S3: RBAC - Lock Slots
- [ ] Login as non-admin
- [ ] Try to access lock-slots
- [ ] Should show permission error

### Test Case S4: Version ID Tampering
- [ ] Login as User A (limited access)
- [ ] Try to access `/admin/analytics/{version_id}` from User B's timetable
- [ ] Should show "not found" or redirect (no data leak)

---

## 9. Checklist Summary

### Phase 1: Form Fields
- [ ] Fields render
- [ ] Defaults work
- [ ] Values submitted correctly
- [ ] Free-period policy enforced

### Phase 2: Scenario Comparison
- [ ] Table appears for multi-scenario
- [ ] Best scenario highlighted
- [ ] All scenarios shown
- [ ] Status badges correct

### Phase 3: Routes 
- [ ] Analytics route accessible
- [ ] ICS export works
- [ ] Substitution form submits
- [ ] Lock-slots form submits

### Phase 4: Templates
- [ ] analytics.html renders with all sections
- [ ] absence-substitute.html form functional
- [ ] lock-slots.html grid interactive

### Phase 5: Integration
- [ ] Full end-to-end flow works
- [ ] No console errors
- [ ] All audit logs created
- [ ] Database data persists

---

## 10. Sign-Off Checklist

When all tests pass, confirm:

- [ ] All form fields working
- [ ] Scenario comparison functional
- [ ] Faculty daily free-period enforced
- [ ] All 4 routes accessible
- [ ] All 3 templates rendering
- [ ] No Python errors in console
- [ ] No JavaScript errors in browser
- [ ] Database operations logged
- [ ] RBAC enforced
- [ ] Performance acceptable

**Status**: Ready for Production ✨

---

## Notes for Testing

1. **Test Master Data**: Use the sample CSV files in `/data/` folder
2. **Clear Cache**: Between tests, clear browser cache to avoid stale data
3. **Check Console**: Open browser DevTools → Console tab → watch for JS errors
4. **Check Terminal**: Monitor Flask terminal for Python errors/warnings
5. **Database Reset**: If needed, delete database and re-initialize: `python migrate_db.py`

**Questions?** Refer to:
- API_REFERENCE.md for function signatures
- IMPLEMENTATION_SUMMARY.md for feature details
- README.md for general setup
