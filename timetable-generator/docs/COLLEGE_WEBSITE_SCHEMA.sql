CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(128) UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    last_login_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    duration_years INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE academic_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(32) NOT NULL UNIQUE,
    academic_year_label VARCHAR(32) NOT NULL,
    term_name VARCHAR(32) NOT NULL,
    starts_on DATE,
    ends_on DATE,
    is_active BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE faculty_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    department_id INTEGER,
    employee_code VARCHAR(32) UNIQUE,
    designation VARCHAR(64),
    max_periods_per_day INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    room_type VARCHAR(32) NOT NULL,
    capacity INTEGER,
    building_name VARCHAR(64),
    floor_label VARCHAR(32),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE room_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL
);

CREATE TABLE room_feature_map (
    room_id INTEGER NOT NULL,
    feature_id INTEGER NOT NULL,
    PRIMARY KEY (room_id, feature_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (feature_id) REFERENCES room_features(id)
);

CREATE TABLE sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    section_code VARCHAR(32) NOT NULL,
    class_name VARCHAR(64) NOT NULL,
    standard_label VARCHAR(64) NOT NULL,
    intake_size INTEGER,
    home_room_id INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (program_id) REFERENCES programs(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (home_room_id) REFERENCES rooms(id)
);

CREATE TABLE student_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(128) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (section_id) REFERENCES sections(id)
);

CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    subject_type VARCHAR(32) NOT NULL,
    default_weekly_periods INTEGER,
    default_daily_max INTEGER,
    requires_lab_room BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE subject_offerings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_term_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    weekly_periods INTEGER NOT NULL,
    daily_max INTEGER,
    is_lab BOOLEAN NOT NULL DEFAULT 0,
    preferred_time_band VARCHAR(32),
    fixed_room_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (academic_term_id) REFERENCES academic_terms(id),
    FOREIGN KEY (section_id) REFERENCES sections(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (fixed_room_id) REFERENCES rooms(id)
);

CREATE TABLE faculty_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_term_id INTEGER NOT NULL,
    faculty_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    allowed_room_list TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (academic_term_id) REFERENCES academic_terms(id),
    FOREIGN KEY (faculty_id) REFERENCES faculty_profiles(id),
    FOREIGN KEY (section_id) REFERENCES sections(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE TABLE faculty_availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_term_id INTEGER NOT NULL,
    faculty_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    period_number INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL,
    note VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (academic_term_id) REFERENCES academic_terms(id),
    FOREIGN KEY (faculty_id) REFERENCES faculty_profiles(id)
);

CREATE TABLE fixed_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_term_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    faculty_id INTEGER,
    room_id INTEGER,
    day_of_week INTEGER NOT NULL,
    period_number INTEGER NOT NULL,
    created_by_user_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (academic_term_id) REFERENCES academic_terms(id),
    FOREIGN KEY (section_id) REFERENCES sections(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (faculty_id) REFERENCES faculty_profiles(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE timetable_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    academic_term_id INTEGER NOT NULL,
    version_label VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    optimization_score DECIMAL(8, 2),
    generated_by_user_id INTEGER,
    approved_by_user_id INTEGER,
    published_by_user_id INTEGER,
    notes TEXT,
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at DATETIME,
    published_at DATETIME,
    FOREIGN KEY (academic_term_id) REFERENCES academic_terms(id),
    FOREIGN KEY (generated_by_user_id) REFERENCES users(id),
    FOREIGN KEY (approved_by_user_id) REFERENCES users(id),
    FOREIGN KEY (published_by_user_id) REFERENCES users(id)
);

CREATE TABLE timetable_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timetable_version_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    faculty_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    period_number INTEGER NOT NULL,
    session_length INTEGER NOT NULL DEFAULT 1,
    session_part INTEGER NOT NULL DEFAULT 1,
    lecture_type VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (timetable_version_id) REFERENCES timetable_versions(id),
    FOREIGN KEY (section_id) REFERENCES sections(id),
    FOREIGN KEY (subject_id) REFERENCES subjects(id),
    FOREIGN KEY (faculty_id) REFERENCES faculty_profiles(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

CREATE TABLE timetable_substitutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timetable_entry_id INTEGER NOT NULL,
    substitute_faculty_id INTEGER NOT NULL,
    substitution_date DATE NOT NULL,
    reason VARCHAR(255),
    created_by_user_id INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (timetable_entry_id) REFERENCES timetable_entries(id),
    FOREIGN KEY (substitute_faculty_id) REFERENCES faculty_profiles(id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    audience_role_code VARCHAR(32),
    title VARCHAR(128) NOT NULL,
    message TEXT NOT NULL,
    channel VARCHAR(32) NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT 0,
    sent_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action_code VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64),
    details TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_sections_program_id ON sections(program_id);
CREATE INDEX idx_sections_department_id ON sections(department_id);
CREATE INDEX idx_subject_offerings_term_section ON subject_offerings(academic_term_id, section_id);
CREATE INDEX idx_faculty_assignments_term_faculty ON faculty_assignments(academic_term_id, faculty_id);
CREATE INDEX idx_faculty_availability_term_faculty ON faculty_availability(academic_term_id, faculty_id);
CREATE INDEX idx_fixed_slots_term_section ON fixed_slots(academic_term_id, section_id);
CREATE INDEX idx_timetable_versions_term_status ON timetable_versions(academic_term_id, status);
CREATE INDEX idx_timetable_entries_version_day_period ON timetable_entries(timetable_version_id, day_of_week, period_number);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);