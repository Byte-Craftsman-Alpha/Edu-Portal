import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = _table_columns(conn, table)
    payload = {k: v for k, v in row.items() if k in cols}
    if not payload:
        return
    keys = list(payload.keys())
    placeholders = ", ".join(["?"] * len(keys))
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
    conn.execute(sql, [payload[k] for k in keys])


def _ensure_rows(conn: sqlite3.Connection, table: str, rows: list[dict], min_rows: int = 4) -> None:
    existing = _count(conn, table)
    if existing >= min_rows:
        return
    needed = min_rows - existing
    for row in rows[:needed]:
        _insert(conn, table, row)


def _get_ids(conn: sqlite3.Connection, table: str) -> list[int]:
    return [int(r[0]) for r in conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall()]


def _get_student_ids(conn: sqlite3.Connection) -> list[int]:
    return [int(r[0]) for r in conn.execute("SELECT id FROM students ORDER BY id").fetchall()]


def seed(db_path: Path) -> None:
    # Import the app and run init_db() so schema/migrations stay in sync.
    import app as edu_app  # type: ignore

    edu_app.DB_PATH = db_path
    edu_app.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        now = datetime.utcnow()

        # schedule_groups: ensure at least 4 groups
        _ensure_rows(
            conn,
            "schedule_groups",
            [
                {
                    "name": "Default Schedule",
                    "program": None,
                    "department": None,
                    "semester": None,
                    "created_at": _now_iso(),
                },
                {
                    "name": "B.Tech CSE - Sem 4 (Section A)",
                    "program": "B.Tech",
                    "department": "Computer Science",
                    "semester": 4,
                    "created_at": _now_iso(),
                },
                {
                    "name": "B.Tech CSE - Sem 4 (Section B)",
                    "program": "B.Tech",
                    "department": "Computer Science",
                    "semester": 4,
                    "created_at": _now_iso(),
                },
                {
                    "name": "BCA - Sem 2",
                    "program": "BCA",
                    "department": "Computer Applications",
                    "semester": 2,
                    "created_at": _now_iso(),
                },
            ],
            min_rows=4,
        )

        # Assign students across schedule groups (if schedule_id exists)
        student_cols = _table_columns(conn, "students")
        if "schedule_id" in student_cols:
            conn.execute("UPDATE students SET schedule_id = 1 WHERE schedule_id IS NULL OR schedule_id = 0")
            conn.execute("UPDATE students SET schedule_id = 2 WHERE id = 2")
            conn.execute("UPDATE students SET schedule_id = 3 WHERE id = 3")
            conn.execute("UPDATE students SET schedule_id = 4 WHERE id = 4")

        # teachers
        _ensure_rows(
            conn,
            "teachers",
            [
                {
                    "name": "Dr. A. Mehta",
                    "designation": "Associate Professor",
                    "department": "Computer Science",
                    "email": "amehta@institute.edu",
                    "phone": "9876543001",
                    "created_at": _now_iso(),
                },
                {
                    "name": "Prof. S. Sharma",
                    "designation": "Assistant Professor",
                    "department": "Computer Science",
                    "email": "ssharma@institute.edu",
                    "phone": "9876543002",
                    "created_at": _now_iso(),
                },
                {
                    "name": "Dr. R. Singh",
                    "designation": "Lab Incharge",
                    "department": "Physics",
                    "email": "rsingh@institute.edu",
                    "phone": "9876543003",
                    "created_at": _now_iso(),
                },
                {
                    "name": "Prof. M. Khan",
                    "designation": "Assistant Professor",
                    "department": "Computer Science",
                    "email": "mkhan@institute.edu",
                    "phone": "9876543004",
                    "created_at": _now_iso(),
                },
            ],
        )

        # announcements
        _ensure_rows(
            conn,
            "announcements",
            [
                {
                    "category": "URGENT",
                    "title": "Water supply maintenance",
                    "body": "Hostel water supply will be intermittent from 6AM–9AM tomorrow.",
                    "author": "Hostel Office",
                    "tag1": "#Hostel",
                    "tag2": "#Maintenance",
                    "created_at": _now_iso(),
                },
                {
                    "category": "GENERAL",
                    "title": "Library hours extended",
                    "body": "Reading hall open till 8PM this weekend.",
                    "author": "Library",
                    "tag1": "#Library",
                    "tag2": None,
                    "created_at": _now_iso(),
                },
                {
                    "category": "EVENT",
                    "title": "Coding contest",
                    "body": "Register for CodeSprint. Top 3 win goodies.",
                    "author": "Tech Club",
                    "tag1": "#Contest",
                    "tag2": "#Coding",
                    "created_at": _now_iso(),
                },
                {
                    "category": "EXAM",
                    "title": "Internal assessments",
                    "body": "Internal assessment schedule will be published on portal.",
                    "author": "Exam Cell",
                    "tag1": "#Exams",
                    "tag2": "#Notice",
                    "created_at": _now_iso(),
                },
            ],
        )

        # news_posts
        _ensure_rows(
            conn,
            "news_posts",
            [
                {
                    "priority": "URGENT",
                    "date_time": _now_iso(),
                    "heading": "Server maintenance tonight",
                    "body": "Portal services may be slow between 11PM–1AM.",
                    "sender": "IT Desk",
                    "news_type": "Alert",
                    "tags": "IT,Maintenance",
                },
                {
                    "priority": "HIGH",
                    "date_time": _now_iso(),
                    "heading": "Exam form deadline",
                    "body": "Exam form submission closes tomorrow 5PM.",
                    "sender": "Exam Cell",
                    "news_type": "Notice",
                    "tags": "Exams,Deadline",
                },
                {
                    "priority": "NORMAL",
                    "date_time": _now_iso(),
                    "heading": "New e-books added",
                    "body": "New DBMS and OS e-books are added to the library.",
                    "sender": "Library",
                    "news_type": "Update",
                    "tags": "Library,Books",
                },
                {
                    "priority": "LOW",
                    "date_time": _now_iso(),
                    "heading": "Canteen menu update",
                    "body": "New menu effective from next Monday.",
                    "sender": "Campus Services",
                    "news_type": "Update",
                    "tags": "Campus,Canteen",
                },
            ],
        )

        # library_books
        _ensure_rows(
            conn,
            "library_books",
            [
                {
                    "title": "Introduction to Algorithms",
                    "author": "Cormen",
                    "status": "Issued",
                    "due_date": (now + timedelta(days=7)).date().isoformat(),
                },
                {
                    "title": "Operating System Concepts",
                    "author": "Silberschatz",
                    "status": "Available",
                    "due_date": None,
                },
                {
                    "title": "Database System Concepts",
                    "author": "Korth",
                    "status": "Available",
                    "due_date": None,
                },
                {
                    "title": "Computer Networks",
                    "author": "Tanenbaum",
                    "status": "Issued",
                    "due_date": (now + timedelta(days=14)).date().isoformat(),
                },
            ],
        )

        # library_resources
        _ensure_rows(
            conn,
            "library_resources",
            [
                {
                    "heading": "DBMS Unit-2 Notes",
                    "description": "ER model and relational algebra summary.",
                    "pdf_url": "https://example.com/dbms-unit2.pdf",
                    "uploader": "Prof. Sharma",
                    "uploaded_at": _now_iso(),
                    "tags": "DBMS,SQL,Semester-4",
                },
                {
                    "heading": "OS Scheduling Cheatsheet",
                    "description": "FCFS, SJF, RR, Priority scheduling quick reference.",
                    "pdf_url": "https://example.com/os-scheduling.pdf",
                    "uploader": "Dr. Mehta",
                    "uploaded_at": _now_iso(),
                    "tags": "OS,CPU,Scheduling",
                },
                {
                    "heading": "CN Important Questions",
                    "description": "Transport layer and routing protocols.",
                    "pdf_url": "https://example.com/cn-impq.pdf",
                    "uploader": "Prof. Verma",
                    "uploaded_at": _now_iso(),
                    "tags": "CN,Networks,Semester-4",
                },
                {
                    "heading": "Discrete Math Practice Set",
                    "description": "Graphs, relations, and combinatorics.",
                    "pdf_url": "https://example.com/dm-practice.pdf",
                    "uploader": "Prof. Rao",
                    "uploaded_at": _now_iso(),
                    "tags": "DM,Math,Practice",
                },
            ],
        )

        # exam_results
        _ensure_rows(
            conn,
            "exam_results",
            [
                {
                    "course": "IT202",
                    "exam": "Mid Sem",
                    "score": 24,
                    "max_score": 30,
                    "grade": "A",
                    "published_at": _now_iso(),
                },
                {
                    "course": "IT203",
                    "exam": "Mid Sem",
                    "score": 26,
                    "max_score": 30,
                    "grade": "A+",
                    "published_at": _now_iso(),
                },
                {
                    "course": "IT204",
                    "exam": "Mid Sem",
                    "score": 22,
                    "max_score": 30,
                    "grade": "B+",
                    "published_at": _now_iso(),
                },
                {
                    "course": "ENV201",
                    "exam": "Assignment",
                    "score": 18,
                    "max_score": 20,
                    "grade": "A",
                    "published_at": _now_iso(),
                },
            ],
        )

        # exam_forms (ensure 4)
        _ensure_rows(
            conn,
            "exam_forms",
            [
                {
                    "title": "Examination Form",
                    "semester_label": "Odd Semester (2025-26)",
                    "status": "OPEN",
                    "open_from": (now - timedelta(days=5)).date().isoformat(),
                    "open_to": (now + timedelta(days=10)).date().isoformat(),
                    "fee": 1200,
                    "note": "Fill carefully.",
                    "apply_url": "https://forms.example.com/exam?roll={exam_roll_number}",
                    "apply_roll_placeholder": "{exam_roll_number}",
                    "program": "B.Tech",
                    "department": "Computer Science",
                },
                {
                    "title": "Back Paper Form",
                    "semester_label": "Odd Semester (2025-26)",
                    "status": "CLOSED",
                    "open_from": (now - timedelta(days=40)).date().isoformat(),
                    "open_to": (now - timedelta(days=30)).date().isoformat(),
                    "fee": 800,
                    "note": "Closed.",
                    "apply_url": "https://forms.example.com/backpaper?roll={exam_roll_number}",
                    "apply_roll_placeholder": "{exam_roll_number}",
                },
                {
                    "title": "Revaluation Form",
                    "semester_label": "Even Semester (2024-25)",
                    "status": "OPEN",
                    "open_from": (now - timedelta(days=1)).date().isoformat(),
                    "open_to": (now + timedelta(days=14)).date().isoformat(),
                    "fee": 500,
                    "note": "Upload supporting documents.",
                    "apply_url": "https://forms.example.com/reval?roll={exam_roll_number}",
                    "apply_roll_placeholder": "{exam_roll_number}",
                },
                {
                    "title": "Improvement Form",
                    "semester_label": "Even Semester (2024-25)",
                    "status": "CLOSED",
                    "open_from": (now - timedelta(days=60)).date().isoformat(),
                    "open_to": (now - timedelta(days=55)).date().isoformat(),
                    "fee": 700,
                    "note": "Contact exam cell for eligibility.",
                },
            ],
            min_rows=4,
        )

        # admit_card_openings
        _ensure_rows(
            conn,
            "admit_card_openings",
            [
                {
                    "title": "Admit Card Download",
                    "semester_label": "Odd Semester (2025-26)",
                    "open_from": (now - timedelta(days=2)).date().isoformat(),
                    "open_to": (now + timedelta(days=20)).date().isoformat(),
                    "note": "Use your exam roll number.",
                    "program": "B.Tech",
                    "department": "Computer Science",
                    "admit_card_url": "https://admit.example.com/download?roll={exam_roll_number}",
                    "roll_placeholder": "{exam_roll_number}",
                },
                {
                    "title": "Admit Card Download",
                    "semester_label": "BCA Sem 2",
                    "open_from": (now - timedelta(days=5)).date().isoformat(),
                    "open_to": (now + timedelta(days=5)).date().isoformat(),
                    "note": "BCA students only.",
                    "program": "BCA",
                    "department": "Computer Applications",
                    "admit_card_url": "https://admit.example.com/bca?roll={exam_roll_number}",
                    "roll_placeholder": "{exam_roll_number}",
                },
                {
                    "title": "Admit Card Window (Closed)",
                    "semester_label": "Even Semester (2024-25)",
                    "open_from": (now - timedelta(days=30)).date().isoformat(),
                    "open_to": (now - timedelta(days=20)).date().isoformat(),
                    "note": "Closed.",
                    "admit_card_url": "https://admit.example.com/old?roll={exam_roll_number}",
                    "roll_placeholder": "{exam_roll_number}",
                },
                {
                    "title": "Special Admit Card",
                    "semester_label": "Odd Semester (2025-26)",
                    "open_from": (now - timedelta(days=1)).date().isoformat(),
                    "open_to": (now + timedelta(days=2)).date().isoformat(),
                    "note": "Special case window.",
                    "admit_card_url": "https://admit.example.com/special?roll={exam_roll_number}",
                    "roll_placeholder": "{exam_roll_number}",
                },
            ],
        )

        # schedules (calendar events, legacy) - keep some rows anyway
        _ensure_rows(
            conn,
            "schedules",
            [
                {
                    "title": "Seminar: AI in 2026",
                    "location": "Seminar Hall 1",
                    "start_at": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
                    "end_at": (now + timedelta(days=2, hours=2)).strftime("%Y-%m-%dT%H:%M"),
                    "schedule_id": 2,
                },
                {
                    "title": "Sports Day",
                    "location": "Main Ground",
                    "start_at": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
                    "end_at": (now + timedelta(days=7, hours=5)).strftime("%Y-%m-%dT%H:%M"),
                    "schedule_id": 1,
                },
                {
                    "title": "Placement Talk",
                    "location": "Auditorium",
                    "start_at": (now + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M"),
                    "end_at": (now + timedelta(days=10, hours=1)).strftime("%Y-%m-%dT%H:%M"),
                    "schedule_id": 3,
                },
                {
                    "title": "Lab Maintenance",
                    "location": "Lab 2",
                    "start_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
                    "end_at": (now + timedelta(days=1, hours=3)).strftime("%Y-%m-%dT%H:%M"),
                    "schedule_id": 4,
                },
            ],
        )

        # weekly_timetable: add extra rows for multiple schedule groups
        tt_cols = _table_columns(conn, "weekly_timetable")
        if "schedule_id" in tt_cols:
            base = [
                (2, 0, "09:00", "10:00", "Data Structures", "C-101", "Dr. Mehta"),
                (2, 1, "10:15", "11:15", "Operating Systems", "C-105", "Prof. Sharma"),
                (2, 3, "11:30", "12:30", "Computer Networks", "C-110", "Prof. Verma"),
                (2, 4, "09:00", "10:00", "Discrete Mathematics", "C-203", "Prof. Rao"),
                (3, 0, "09:00", "10:00", "DSA (Batch B)", "C-102", "Dr. Mehta"),
                (3, 2, "10:15", "11:15", "OS (Batch B)", "C-106", "Prof. Sharma"),
                (3, 4, "11:30", "13:00", "Python Lab", "Lab-3", "TA Team"),
                (3, 5, "09:00", "10:00", "Seminar", "Seminar Hall", "Prof. Khan"),
                (4, 0, "09:00", "10:00", "C Programming", "BCA-201", "Prof. Anita"),
                (4, 1, "10:15", "11:15", "Maths", "BCA-202", "Prof. Raj"),
                (4, 3, "11:30", "12:30", "Digital Logic", "BCA-203", "Prof. Neeraj"),
                (4, 4, "09:00", "10:00", "English", "BCA-204", "Prof. Sunita"),
            ]
            for schedule_id, dow, st, et, subj, room, inst in base:
                conn.execute(
                    """
                    INSERT INTO weekly_timetable (schedule_id, day_of_week, start_time, end_time, subject, room, instructor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (schedule_id, dow, st, et, subj, room, inst),
                )

        # programs
        _ensure_rows(
            conn,
            "programs",
            [
                {"name": "B.Tech", "branch": "IT"},
                {"name": "B.Tech", "branch": "CSE"},
                {"name": "BCA", "branch": "General"},
                {"name": "MBA", "branch": "HR"},
            ],
            min_rows=4,
        )

        # subjects (schema varies across app versions; provide both key sets)
        _ensure_rows(
            conn,
            "subjects",
            [
                {
                    "program_id": 1,
                    "semester": 4,
                    "code": "IT202",
                    "name": "Data Structure",
                    "course_code": "IT202",
                    "course_name": "Data Structure",
                },
                {
                    "program_id": 1,
                    "semester": 4,
                    "code": "IT203",
                    "name": "Python with Linux",
                    "course_code": "IT203",
                    "course_name": "Python with Linux",
                },
                {
                    "program_id": 1,
                    "semester": 4,
                    "code": "IT204",
                    "name": "Discrete Mathematics",
                    "course_code": "IT204",
                    "course_name": "Discrete Mathematics",
                },
                {
                    "program_id": 3,
                    "semester": 2,
                    "code": "BCA102",
                    "name": "C Programming",
                    "course_code": "BCA102",
                    "course_name": "C Programming",
                },
            ],
            min_rows=4,
        )

        # student_programs (map each student to a program)
        student_ids = _get_student_ids(conn)
        for sid in student_ids:
            exists = conn.execute("SELECT 1 FROM student_programs WHERE student_id = ?", (int(sid),)).fetchone()
            if exists is None:
                prog = 1 if sid in (1, 2, 3, 4) else 1
                _insert(conn, "student_programs", {"student_id": int(sid), "program_id": prog})

        # student_subject_enrollments
        subj_ids = [int(r[0]) for r in conn.execute("SELECT id FROM subjects ORDER BY id").fetchall()]
        if subj_ids and _count(conn, "student_subject_enrollments") < 4:
            session_label = "Odd Semester (2025-26)"
            for sid in student_ids[:4]:
                for sub in subj_ids[:3]:
                    try:
                        _insert(
                            conn,
                            "student_subject_enrollments",
                            {"student_id": int(sid), "subject_id": int(sub), "session_label": session_label},
                        )
                    except sqlite3.IntegrityError:
                        pass

        # exam_sessions
        _ensure_rows(
            conn,
            "exam_sessions",
            [
                {
                    "session_label": "Odd Semester (2025-26)",
                    "program_id": 1,
                    "semester": 4,
                    "university": "Demo University",
                    "college_label": "Demo College",
                    "exam_center": "Center 1",
                    "status": "ACTIVE",
                    "issued_at": _now_iso(),
                },
                {
                    "session_label": "Even Semester (2024-25)",
                    "program_id": 1,
                    "semester": 4,
                    "university": "Demo University",
                    "college_label": "Demo College",
                    "exam_center": "Center 2",
                    "status": "ACTIVE",
                    "issued_at": _now_iso(),
                },
                {
                    "session_label": "BCA Sem 2 (2025-26)",
                    "program_id": 3,
                    "semester": 2,
                    "university": "Demo University",
                    "college_label": "Demo College",
                    "exam_center": "Center 3",
                    "status": "ACTIVE",
                    "issued_at": _now_iso(),
                },
                {
                    "session_label": "MBA Sem 1 (2025-26)",
                    "program_id": 4,
                    "semester": 1,
                    "university": "Demo University",
                    "college_label": "Demo College",
                    "exam_center": "Center 4",
                    "status": "ACTIVE",
                    "issued_at": _now_iso(),
                },
            ],
            min_rows=4,
        )

        # exam_timetable
        if _count(conn, "exam_timetable") < 4:
            sess_id = int(conn.execute("SELECT id FROM exam_sessions ORDER BY id").fetchone()[0])
            sub_id = int(conn.execute("SELECT id FROM subjects ORDER BY id").fetchone()[0])
            _ensure_rows(
                conn,
                "exam_timetable",
                [
                    {
                        "session_id": sess_id,
                        "subject_id": sub_id,
                        "paper_type": "REGULAR",
                        "exam_date": (now + timedelta(days=30)).date().isoformat(),
                        "exam_time": "11:30 AM to 01:00 PM",
                    },
                    {
                        "session_id": sess_id,
                        "subject_id": sub_id + 1,
                        "paper_type": "REGULAR",
                        "exam_date": (now + timedelta(days=31)).date().isoformat(),
                        "exam_time": "11:30 AM to 01:00 PM",
                    },
                    {
                        "session_id": sess_id,
                        "subject_id": sub_id + 2,
                        "paper_type": "REGULAR",
                        "exam_date": (now + timedelta(days=33)).date().isoformat(),
                        "exam_time": "11:30 AM to 01:00 PM",
                    },
                    {
                        "session_id": sess_id,
                        "subject_id": sub_id + 3,
                        "paper_type": "REGULAR",
                        "exam_date": (now + timedelta(days=35)).date().isoformat(),
                        "exam_time": "11:30 AM to 01:00 PM",
                    },
                ],
                min_rows=4,
            )

        # exam_form_submissions (link students to first exam form)
        if _count(conn, "exam_form_submissions") < 4:
            form_id = int(conn.execute("SELECT id FROM exam_forms ORDER BY id").fetchone()[0])
            for sid in student_ids[:4]:
                student = conn.execute("SELECT * FROM students WHERE id = ?", (int(sid),)).fetchone()
                if not student:
                    continue
                try:
                    _insert(
                        conn,
                        "exam_form_submissions",
                        {
                            "form_id": form_id,
                            "student_id": int(sid),
                            "submitted_at": _now_iso(),
                            "student_name": student["name"],
                            "roll_no": student["roll_no"],
                            "program": student["program"],
                            "semester": int(student["sem"]),
                            "phone": student["phone"],
                            "email": student["email"],
                            "guardian": student["guardian"],
                            "address": "Demo Address",
                            "category": "GENERAL",
                            "gender": "Male",
                            "status": "Active",
                            "residential_status": student["residential_status"],
                        },
                    )
                except sqlite3.IntegrityError:
                    pass

        # admit_cards + subjects
        if _count(conn, "admit_cards") < 4:
            for sid in student_ids[:4]:
                student = conn.execute("SELECT * FROM students WHERE id = ?", (int(sid),)).fetchone()
                details = conn.execute("SELECT * FROM student_details WHERE student_id = ?", (int(sid),)).fetchone()
                father = (details["father_name"] if details else "Father")
                gender = (details["gender"] if details else "Male")
                category = (details["category"] if details else "GENERAL")
                address = (details["address"] if details else "Demo Address")
                conn.execute(
                    """
                    INSERT INTO admit_cards (
                        student_id, university, session_label, program_label, college_label,
                        student_name, roll_number, father_name, gender, category, address,
                        exam_center, image_label, issued_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(sid),
                        "Demo University",
                        "Odd Semester (2025-26)",
                        "Program",
                        "Demo College",
                        student["name"],
                        student["roll_no"],
                        father,
                        gender,
                        category,
                        address,
                        "Center 1",
                        None,
                        _now_iso(),
                    ),
                )
                admit_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                # add 3 subjects per admit card
                for i in range(1, 4):
                    _insert(
                        conn,
                        "admit_card_subjects",
                        {
                            "admit_card_id": admit_id,
                            "sno": i,
                            "paper_type": "REGULAR",
                            "subject_code": f"SUB{i:03d}",
                            "subject_name": f"Subject {i}",
                            "exam_date": (now + timedelta(days=25 + i)).date().isoformat(),
                            "exam_time": "11:30 AM to 01:00 PM",
                        },
                    )

        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a fresh dummy eduportal.db with seed data")
    parser.add_argument(
        "--db",
        default=str(Path(__file__).with_name("eduportal.db")),
        help="Path to sqlite db file (default: ./eduportal.db)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing db file if it exists",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if db_path.exists():
        if not args.force:
            raise SystemExit(
                f"DB already exists at {db_path}. Re-run with --force to overwrite."
            )
        os.remove(db_path)

    seed(db_path)
    print(f"Dummy database created at: {db_path}")
    print("Login credentials:")
    print("- Admin: admin / admin123")
    print("- Students: use one of the seeded roll numbers with password student123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
