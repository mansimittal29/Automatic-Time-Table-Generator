# College Timetable Website Blueprint

## Purpose

This document upgrades the timetable-generator project from a standalone demo into a deployable college timetable website roadmap. It maps the major modules that should exist in a final-year project and then in a real campus deployment.

## Current Base

The current project already provides:

- multi-section timetable generation
- conflict-aware scheduling with faculty and room checks
- class-wise outputs
- faculty-wise outputs
- room-wise outputs
- Excel, CSV, and JSON exports
- API endpoints for latest generated timetable data
- result-page search and filtering across class, faculty, room, and section cards

## Target Product Modules

### 1. Identity and Access

- Admin login
- HOD or dean login
- Faculty login
- Student login
- Role-based authorization
- Password reset flow
- Session timeout and secure sign-out

### 2. Academic Master Data

- Departments
- Programs or courses
- Academic years
- Semesters or terms
- Classes and sections
- Subjects
- Subject offerings by term
- Faculty profiles
- Student groups or batches
- Rooms and labs
- Room features and capacities

### 3. Scheduling Inputs

- Faculty assignment mapping
- Faculty daily limits
- Faculty availability and leave blocks
- Preferred subject slots
- Fixed lectures
- Section home classrooms
- Lab room restrictions
- Department-specific scheduling rules

### 4. Timetable Engine

- hard-constraint scheduling
- soft optimization scoring
- versioned timetable generation
- partial regeneration for selected class or section
- draft, approved, and published timetable states
- conflict explanation on failure

### 5. Operational Website Features

- admin dashboard
- dean or HOD dashboard
- faculty portal
- student portal
- room utilization dashboard
- timetable publish and unpublish workflow
- manual timetable edit mode with validation
- substitution timetable for absent faculty
- printable PDF reports
- notifications and change alerts

### 6. Reporting and Analytics

- faculty workload summary
- room utilization summary
- section utilization summary
- daily and weekly load analysis
- optimization score history
- timetable version comparison
- audit log for all changes

## Recommended User Roles

### Admin

- manage all master data
- run timetable generation
- edit drafts
- approve and publish timetable
- override constraints when required
- download all reports

### HOD or Dean

- review department timetable
- verify faculty load
- request changes before publishing
- view department analytics

### Faculty

- view own timetable
- view substitute classes
- mark availability or leave
- view assigned sections and rooms

### Student

- view published section timetable
- view daily schedule
- download PDF or image version

## Page Map

### Public

- landing page
- login page

### Admin

- dashboard
- departments management
- programs management
- subjects management
- faculty management
- rooms management
- sections management
- timetable generation
- timetable history
- publish workflow
- system audit log

### Dean or HOD

- department dashboard
- department timetable review
- faculty load report
- room usage report

### Faculty

- faculty home
- my timetable
- my workload
- leave and availability
- substitution notices

### Student

- student home
- my class timetable
- exam and holiday notice area

## Implementation Phases

### Phase 1. Production Foundation

- database integration
- user accounts and role-based access
- timetable version storage
- draft and publish status
- room-wise, class-wise, faculty-wise views
- search and filtering

### Phase 2. Administrative Operations

- CRUD for master data
- faculty availability input
- room capacity and features
- subject preference rules
- fixed slot management
- timetable history and rollback

### Phase 3. Website Experience

- dedicated portals for student and faculty
- report exports and printable PDFs
- notifications
- substitution timetable
- dashboard analytics

### Phase 4. Institutional Deployment

- deployment on a college server
- backups and recovery
- activity logging
- performance tuning for large datasets
- API integration with ERP or student portal

## Technical Architecture Recommendation

### Backend

- Flask application with blueprints
- SQLAlchemy models
- Flask-Login for authentication
- Alembic or Flask-Migrate for migrations
- background jobs for heavy timetable generation

### Database

- SQLite for development
- PostgreSQL or MySQL for production

### Frontend

- Flask templates for the first deployment stage
- optional React or Vue frontend later if the institution needs a richer portal

### Files and Reports

- export generated timetable versions to Excel, CSV, JSON, and PDF
- keep published outputs versioned by term and release date

## Security and Reliability Requirements

- hashed passwords
- CSRF protection for admin forms
- role checks on every protected route
- audit logs for create, update, delete, publish actions
- regular database backups
- validation on import files and manual edits

## Suggested Next Build Order

1. Add database models and migrations.
2. Add login and role-based dashboard routing.
3. Save generated timetables as versioned records.
4. Add room-wise management pages and room availability rules.
5. Add master-data CRUD panels.
6. Add faculty availability and fixed slot constraints.
7. Add publish workflow and student-facing published timetable pages.
8. Add manual edit mode and audit logs.

## Related File

Database schema starter: docs/COLLEGE_WEBSITE_SCHEMA.sql