from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, g

from ..config import DB_PATH


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(exception: Exception | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)


def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA foreign_keys = ON;")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                guardian TEXT NOT NULL,
                residential_status TEXT NOT NULL,
                program TEXT NOT NULL,
                year INTEGER NOT NULL,
                sem INTEGER NOT NULL,
                attendance_percent INTEGER NOT NULL,
                next_class TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                author TEXT NOT NULL,
                tag1 TEXT,
                tag2 TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS news_posts (
                id INTEGER PRIMARY KEY,
                priority TEXT NOT NULL,
                date_time TEXT NOT NULL,
                heading TEXT NOT NULL,
                body TEXT NOT NULL,
                sender TEXT NOT NULL,
                news_type TEXT NOT NULL,
                tags TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                designation TEXT NOT NULL,
                department TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS weekly_timetable (
                id INTEGER PRIMARY KEY,
                day_of_week INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                subject TEXT NOT NULL,
                room TEXT NOT NULL,
                instructor TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS calendar_items (
                id INTEGER PRIMARY KEY,
                item_date TEXT NOT NULL,
                item_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attendance_heatmap (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                att_date TEXT NOT NULL,
                level INTEGER NOT NULL,
                UNIQUE(student_id, att_date),
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS library_books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                status TEXT NOT NULL,
                due_date TEXT
            );

            CREATE TABLE IF NOT EXISTS library_resources (
                id INTEGER PRIMARY KEY,
                heading TEXT NOT NULL,
                description TEXT NOT NULL,
                pdf_url TEXT NOT NULL,
                uploader TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                tags TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vault_folders (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(student_id, name),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS vault_files (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                folder_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime TEXT,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(folder_id) REFERENCES vault_folders(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exam_results (
                id INTEGER PRIMARY KEY,
                course TEXT NOT NULL,
                exam TEXT NOT NULL,
                score INTEGER NOT NULL,
                max_score INTEGER NOT NULL,
                grade TEXT NOT NULL,
                published_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exam_forms (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                semester_label TEXT NOT NULL,
                status TEXT NOT NULL,
                open_from TEXT,
                open_to TEXT,
                fee INTEGER,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS admit_card_openings (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                semester_label TEXT NOT NULL,
                open_from TEXT,
                open_to TEXT,
                note TEXT,
                program TEXT,
                department TEXT,
                admit_card_url TEXT,
                roll_placeholder TEXT
            );

            CREATE TABLE IF NOT EXISTS exam_form_submissions (
                id INTEGER PRIMARY KEY,
                form_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                submitted_at TEXT NOT NULL,
                student_name TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                program TEXT NOT NULL,
                semester INTEGER NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL,
                guardian TEXT NOT NULL,
                address TEXT NOT NULL,
                category TEXT NOT NULL,
                gender TEXT NOT NULL,
                status TEXT NOT NULL,
                residential_status TEXT NOT NULL,
                UNIQUE(form_id, student_id),
                FOREIGN KEY(form_id) REFERENCES exam_forms(id),
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS admit_cards (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                university TEXT NOT NULL,
                session_label TEXT NOT NULL,
                program_label TEXT NOT NULL,
                college_label TEXT NOT NULL,
                student_name TEXT NOT NULL,
                roll_number TEXT NOT NULL,
                father_name TEXT NOT NULL,
                gender TEXT NOT NULL,
                category TEXT NOT NULL,
                address TEXT NOT NULL,
                exam_center TEXT NOT NULL,
                image_label TEXT,
                issued_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS admit_card_subjects (
                id INTEGER PRIMARY KEY,
                admit_card_id INTEGER NOT NULL,
                sno INTEGER NOT NULL,
                paper_type TEXT NOT NULL,
                subject_code TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                exam_date TEXT,
                exam_time TEXT,
                FOREIGN KEY(admit_card_id) REFERENCES admit_cards(id)
            );

            CREATE TABLE IF NOT EXISTS student_details (
                student_id INTEGER PRIMARY KEY,
                father_name TEXT NOT NULL,
                gender TEXT NOT NULL,
                category TEXT NOT NULL,
                address TEXT NOT NULL,
                exam_roll_number TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS student_profile (
                student_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL,
                batch TEXT NOT NULL,
                department TEXT NOT NULL,
                section TEXT NOT NULL,
                address TEXT NOT NULL,
                emergency_contact_name TEXT NOT NULL,
                emergency_contact_relation TEXT NOT NULL,
                emergency_contact_phone TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS student_dues (
                student_id INTEGER PRIMARY KEY,
                pending_amount INTEGER NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS programs (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                branch TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS student_programs (
                student_id INTEGER PRIMARY KEY,
                program_id INTEGER NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(program_id) REFERENCES programs(id)
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY,
                course_code TEXT NOT NULL,
                course_name TEXT NOT NULL,
                semester INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                UNIQUE(course_code, program_id),
                FOREIGN KEY(program_id) REFERENCES programs(id)
            );

            CREATE TABLE IF NOT EXISTS student_subject_enrollments (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                session_label TEXT NOT NULL,
                UNIQUE(student_id, subject_id, session_label),
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );

            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY,
                session_label TEXT NOT NULL,
                program_id INTEGER NOT NULL,
                semester INTEGER NOT NULL,
                university TEXT NOT NULL,
                college_label TEXT NOT NULL,
                exam_center TEXT NOT NULL,
                status TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                UNIQUE(session_label, program_id, semester),
                FOREIGN KEY(program_id) REFERENCES programs(id)
            );

            CREATE TABLE IF NOT EXISTS exam_timetable (
                id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                paper_type TEXT NOT NULL,
                exam_date TEXT,
                exam_time TEXT,
                UNIQUE(session_id, subject_id),
                FOREIGN KEY(session_id) REFERENCES exam_sessions(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            );

            CREATE TABLE IF NOT EXISTS semester_results (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                semester INTEGER NOT NULL,
                session_label TEXT NOT NULL,
                university TEXT NOT NULL,
                college_label TEXT NOT NULL,
                student_name TEXT NOT NULL,
                student_type TEXT NOT NULL,
                father_name TEXT NOT NULL,
                mother_name TEXT NOT NULL,
                roll_no TEXT NOT NULL,
                enrollment_no TEXT NOT NULL,
                sgpa REAL NOT NULL,
                result_status TEXT NOT NULL,
                declared_on TEXT NOT NULL,
                UNIQUE(student_id, program_id, semester, session_label),
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(program_id) REFERENCES programs(id)
            );

            CREATE TABLE IF NOT EXISTS semester_result_courses (
                id INTEGER PRIMARY KEY,
                result_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                course_code TEXT NOT NULL,
                course_title TEXT NOT NULL,
                ext_theory INTEGER,
                int_theory INTEGER,
                int_pract INTEGER,
                ext_pract INTEGER,
                obt_marks INTEGER,
                total_credit REAL NOT NULL,
                grade TEXT NOT NULL,
                grade_point REAL NOT NULL,
                FOREIGN KEY(result_id) REFERENCES semester_results(id)
            );

            CREATE TABLE IF NOT EXISTS schedule_groups (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                program TEXT,
                department TEXT,
                semester INTEGER,
                created_at TEXT NOT NULL
            );
            """
        )

        cols = {row[1] for row in db.execute("PRAGMA table_info(students)").fetchall()}
        if "password_hash" not in cols:
            db.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")
        if "schedule_id" not in cols:
            db.execute("ALTER TABLE students ADD COLUMN schedule_id INTEGER")

        schedule_cols = {row[1] for row in db.execute("PRAGMA table_info(schedules)").fetchall()}
        if "schedule_id" not in schedule_cols:
            db.execute("ALTER TABLE schedules ADD COLUMN schedule_id INTEGER")

        wt_cols = {row[1] for row in db.execute("PRAGMA table_info(weekly_timetable)").fetchall()}
        if "schedule_id" not in wt_cols:
            db.execute("ALTER TABLE weekly_timetable ADD COLUMN schedule_id INTEGER")

        news_cols = {row[1] for row in db.execute("PRAGMA table_info(news_posts)").fetchall()}
        if "body_is_html" not in news_cols:
            db.execute("ALTER TABLE news_posts ADD COLUMN body_is_html INTEGER NOT NULL DEFAULT 0")
        if "attachment_path" not in news_cols:
            db.execute("ALTER TABLE news_posts ADD COLUMN attachment_path TEXT")
        if "attachment_name" not in news_cols:
            db.execute("ALTER TABLE news_posts ADD COLUMN attachment_name TEXT")
        if "attachment_mime" not in news_cols:
            db.execute("ALTER TABLE news_posts ADD COLUMN attachment_mime TEXT")

        db.commit()

        teachers_count = db.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
        if teachers_count == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.executemany(
                """
                INSERT INTO teachers (name, designation, department, email, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("Dr. R. Mehta", "Professor", "Computer Science", "mehta@example.com", "9876543210", now),
                    ("Prof. S. Sharma", "Assistant Professor", "Information Technology", "sharma@example.com", "9876543211", now),
                ],
            )

        db.commit()
    finally:
        db.close()
