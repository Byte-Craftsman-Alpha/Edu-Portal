from flask import Flask, g, render_template, request, redirect, url_for, render_template_string, session, abort, send_file
from datetime import datetime
from pathlib import Path
import os
import shutil
import sqlite3
import calendar
from urllib.parse import quote
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

DB_PATH = Path(__file__).with_name("eduportal.db")

NEWS_UPLOAD_DIR = Path(__file__).with_name("static") / "uploads" / "news"
VAULT_UPLOAD_DIR = Path(__file__).with_name("uploads") / "vault"


def save_news_attachment(upload) -> tuple[str, str, str] | None:
    if upload is None:
        return None
    original = (upload.filename or "").strip()
    if not original:
        return None
    NEWS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe = secure_filename(original)
    if not safe:
        return None
    unique = f"{uuid.uuid4().hex}_{safe}"
    abs_path = NEWS_UPLOAD_DIR / unique
    upload.save(abs_path)

    rel_path = f"uploads/news/{unique}"
    mime = (getattr(upload, "mimetype", None) or "").strip()
    return (rel_path, original, mime)


def ensure_news_posts_rich_schema(db: sqlite3.Connection) -> None:
    cols = {row[1] for row in db.execute("PRAGMA table_info(news_posts)").fetchall()}
    if "body_is_html" not in cols:
        db.execute("ALTER TABLE news_posts ADD COLUMN body_is_html INTEGER NOT NULL DEFAULT 0")
    if "attachment_path" not in cols:
        db.execute("ALTER TABLE news_posts ADD COLUMN attachment_path TEXT")
    if "attachment_name" not in cols:
        db.execute("ALTER TABLE news_posts ADD COLUMN attachment_name TEXT")
    if "attachment_mime" not in cols:
        db.execute("ALTER TABLE news_posts ADD COLUMN attachment_mime TEXT")


def save_vault_file(upload, student_id: int) -> tuple[str, str, str, int] | None:
    if upload is None:
        return None
    original = (upload.filename or "").strip()
    if not original:
        return None

    safe = secure_filename(original)
    if not safe:
        return None

    VAULT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique = f"{uuid.uuid4().hex}_{safe}"
    abs_path = VAULT_UPLOAD_DIR / str(int(student_id)) / unique
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    upload.save(str(abs_path))

    rel_path = f"vault/{int(student_id)}/{unique}"
    mime = (getattr(upload, "mimetype", None) or "").strip()
    size_bytes = int(abs_path.stat().st_size) if abs_path.exists() else 0
    return (rel_path, original, mime, size_bytes)


def get_vault_abs_path(stored_path: str) -> Path | None:
    stored = (stored_path or "").strip()
    if not stored.startswith("vault/"):
        return None
    return Path(__file__).with_name("uploads") / stored


def delete_vault_physical_file(stored_path: str) -> None:
    abs_path = get_vault_abs_path(stored_path)
    if abs_path is None:
        return
    try:
        if abs_path.exists() and abs_path.is_file():
            abs_path.unlink()
    except Exception:
        pass


def sanitize_news_html(html: str) -> str:
    # Allow a small, safe subset of HTML for news bodies.
    if not html:
        return ""

    # Remove script/style blocks
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.I | re.S)
    # Remove on* handlers
    cleaned = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\son\w+\s*=\s*'[^']*'", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\son\w+\s*=\s*[^\s>]+", "", cleaned, flags=re.I)
    # Block javascript: URLs
    cleaned = re.sub(r"(href|src)\s*=\s*\"\s*javascript:[^\"]*\"", r"\1=\"#\"", cleaned, flags=re.I)
    cleaned = re.sub(r"(href|src)\s*=\s*'\s*javascript:[^']*'", r"\1='#'", cleaned, flags=re.I)

    allowed = {
        "b",
        "strong",
        "i",
        "em",
        "u",
        "s",
        "del",
        "code",
        "pre",
        "br",
        "p",
        "ul",
        "ol",
        "li",
        "a",
        "span",
        "div",
    }

    def _filter_tag(match: re.Match) -> str:
        tag = match.group(0)
        name = match.group(1) or ""
        n = name.strip().lower()
        if n not in allowed:
            return ""
        if n == "a":
            href = re.search(r"href\s*=\s*(['\"])(.*?)\1", tag, flags=re.I)
            href_val = href.group(2) if href else "#"
            if href_val.strip().lower().startswith("javascript:"):
                href_val = "#"
            return f'<a href="{href_val}" target="_blank" rel="noopener noreferrer">'
        if tag.startswith("</"):
            return f"</{n}>"
        if n in {"span", "div", "p", "pre", "code", "ul", "ol", "li", "strong", "b", "em", "i", "u", "s", "del", "br"}:
            return f"<{n}>" if n != "br" else "<br>"
        return f"<{n}>"

    cleaned = re.sub(r"</?\s*([a-zA-Z0-9]+)(\s[^>]*)?>", _filter_tag, cleaned)
    return cleaned.strip()


def get_current_student_id() -> int | None:
    sid = session.get("student_id")
    if sid is None:
        return None
    try:
        return int(sid)
    except Exception:
        return None


def get_current_admin_id() -> int | None:
    aid = session.get("admin_user_id")
    if aid is None:
        return None
    try:
        return int(aid)
    except Exception:
        return None


def get_safe_next_url(default_endpoint: str = "dashboard") -> str:
    next_url = (request.args.get("next") or request.form.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for(default_endpoint)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_student_id() is None:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_admin_id() is None:
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_role_required(*allowed_roles: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            aid = get_current_admin_id()
            if aid is None:
                return redirect(url_for("admin_login"))
            db = get_db()
            admin_user = db.execute(
                "SELECT * FROM admin_users WHERE id = ?",
                (aid,),
            ).fetchone()
            if not admin_user:
                session.pop("admin_user_id", None)
                return redirect(url_for("admin_login"))
            role = (admin_user["role"] or "").strip().lower()
            if allowed_roles and role not in {r.strip().lower() for r in allowed_roles}:
                return render_template(
                    "admin_dashboard.html",
                    page_title="Admin Panel",
                    page_subtitle="Restricted access",
                    active_page="admin",
                    admin_user=admin_user,
                    error="You do not have permission to access this page.",
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def ensure_students_password_column(db: sqlite3.Connection) -> None:
    cols = {row[1] for row in db.execute("PRAGMA table_info(students)").fetchall()}
    if "password_hash" not in cols:
        db.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")


def ensure_schedule_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schedule_groups (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            program TEXT,
            department TEXT,
            semester INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )

    student_cols = {row[1] for row in db.execute("PRAGMA table_info(students)").fetchall()}
    if "schedule_id" not in student_cols:
        db.execute("ALTER TABLE students ADD COLUMN schedule_id INTEGER")

    schedule_cols = {row[1] for row in db.execute("PRAGMA table_info(schedules)").fetchall()}
    if "schedule_id" not in schedule_cols:
        db.execute("ALTER TABLE schedules ADD COLUMN schedule_id INTEGER")

    tt_cols = {row[1] for row in db.execute("PRAGMA table_info(weekly_timetable)").fetchall()}
    if "schedule_id" not in tt_cols:
        db.execute("ALTER TABLE weekly_timetable ADD COLUMN schedule_id INTEGER")

    groups_count = db.execute("SELECT COUNT(*) FROM schedule_groups").fetchone()[0]
    if int(groups_count) == 0:
        now = datetime.utcnow().isoformat(timespec="seconds")
        db.execute(
            """
            INSERT INTO schedule_groups (id, name, program, department, semester, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, "Default Schedule", None, None, None, now),
        )

    db.execute(
        "UPDATE students SET schedule_id = 1 WHERE schedule_id IS NULL OR schedule_id = 0"
    )
    db.execute(
        "UPDATE schedules SET schedule_id = 1 WHERE schedule_id IS NULL OR schedule_id = 0"
    )
    db.execute(
        "UPDATE weekly_timetable SET schedule_id = 1 WHERE schedule_id IS NULL OR schedule_id = 0"
    )


def ensure_exam_forms_link_schema(db: sqlite3.Connection) -> None:
    cols = {row[1] for row in db.execute("PRAGMA table_info(exam_forms)").fetchall()}
    if "apply_url" not in cols:
        db.execute("ALTER TABLE exam_forms ADD COLUMN apply_url TEXT")
    if "admit_card_url" not in cols:
        db.execute("ALTER TABLE exam_forms ADD COLUMN admit_card_url TEXT")
    if "apply_roll_placeholder" not in cols:
        db.execute("ALTER TABLE exam_forms ADD COLUMN apply_roll_placeholder TEXT")
    if "admit_roll_placeholder" not in cols:
        db.execute("ALTER TABLE exam_forms ADD COLUMN admit_roll_placeholder TEXT")
    if "program" not in cols:
        db.execute("ALTER TABLE exam_forms ADD COLUMN program TEXT")
    if "department" not in cols:
        db.execute("ALTER TABLE exam_forms ADD COLUMN department TEXT")


def ensure_admit_card_openings_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
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
        """
    )


def resolve_exam_link(url_template: str | None, placeholder: str | None, exam_roll_number: str) -> str:
    url = (url_template or "").strip()
    if not url:
        return ""

    marker = (placeholder or "{exam_roll_number}").strip() or "{exam_roll_number}"
    encoded = quote((exam_roll_number or "").strip(), safe="")
    if not encoded:
        return url
    return url.replace(marker, encoded)


def is_exam_form_open(open_from: str | None, open_to: str | None, now: datetime | None = None) -> bool:
    if not open_from or not open_to:
        return False
    try:
        today = (now or datetime.now()).date()
        start_d = datetime.strptime(open_from, "%Y-%m-%d").date()
        end_d = datetime.strptime(open_to, "%Y-%m-%d").date()
        return start_d <= today <= end_d
    except Exception:
        return False


def seed_attendance_for_student(db: sqlite3.Connection, student_id: int) -> None:
    existing = db.execute(
        "SELECT COUNT(*) FROM attendance_heatmap WHERE student_id = ?",
        (int(student_id),),
    ).fetchone()[0]
    if int(existing) > 0:
        return
    today = datetime.now().date()
    start = today.toordinal() - (7 * 28) + 1
    rows = []
    for i in range(7 * 28):
        d = datetime.fromordinal(start + i).date().isoformat()
        lvl = (i * 3 + int(student_id)) % 5
        rows.append((int(student_id), d, int(lvl)))
    db.executemany(
        """
        INSERT INTO attendance_heatmap (student_id, att_date, level)
        VALUES (?, ?, ?)
        """,
        rows,
    )


def _norm_text(v: str | None) -> str:
    return " ".join((v or "").strip().lower().split())


def _scope_match(student_val: str, rule_val: str) -> bool:
    s = _norm_text(student_val)
    r = _norm_text(rule_val)
    if not r:
        return True
    if not s:
        # If we cannot determine student's value reliably, do not hide the record.
        return True
    return s == r or (r in s) or (s in r)


def _scope_match_program(student_program_name: str, student_program_id: int | None, rule_val: str) -> bool:
    rv = (rule_val or "").strip()
    if not rv:
        return True
    if rv.isdigit() and student_program_id is not None:
        return int(rv) == int(student_program_id)
    return _scope_match(student_program_name, rv)


def _scope_rule_clean(v: str | None) -> str:
    r = _norm_text(v)
    if r in {"na", "n/a", "none", "all", "any", "-", "--", "example"}:
        return ""
    return r

@app.template_filter("fmt_dt")
def fmt_dt(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", ""))
    except Exception:
        return str(value)
    return dt.strftime("%d-%m-%Y %I:%M %p")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exception):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
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
            """
        )

        student_cols = {row[1] for row in db.execute("PRAGMA table_info(students)").fetchall()}
        if "password_hash" not in student_cols:
            db.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")

        subj_cols = {row[1] for row in db.execute("PRAGMA table_info(subjects)").fetchall()}
        if "code" not in subj_cols:
            db.execute("ALTER TABLE subjects ADD COLUMN code TEXT")
        if "name" not in subj_cols:
            db.execute("ALTER TABLE subjects ADD COLUMN name TEXT")
        subj_cols = {row[1] for row in db.execute("PRAGMA table_info(subjects)").fetchall()}
        if {"course_code", "course_name", "code", "name"}.issubset(subj_cols):
            db.execute(
                "UPDATE subjects SET code = course_code WHERE code IS NULL OR TRIM(code) = ''"
            )
            db.execute(
                "UPDATE subjects SET name = course_name WHERE name IS NULL OR TRIM(name) = ''"
            )

        ensure_schedule_schema(db)
        ensure_exam_forms_link_schema(db)
        ensure_admit_card_openings_schema(db)
        ensure_news_posts_rich_schema(db)

        default_password = "student123"
        dummy_students = [
            {
                "id": 1,
                "name": "Alex Johnson",
                "roll_no": "CS-2024-042",
                "email": "alex.johnson@institute.edu",
                "phone": "+91 98765 43210",
                "guardian": "Robert Johnson (Father)",
                "residential_status": "Hosteler (Block B, Rm 302)",
                "program": "B.Tech in Computer Science and Engineering",
                "year": 2,
                "sem": 4,
                "attendance_percent": 82,
                "next_class": "Physics Lab @ 2PM",
            },
            {
                "id": 2,
                "name": "Priya Sharma",
                "roll_no": "CS-2024-043",
                "email": "priya.sharma@institute.edu",
                "phone": "+91 98765 43211",
                "guardian": "Anil Sharma (Father)",
                "residential_status": "Day Scholar",
                "program": "B.Tech in Computer Science and Engineering",
                "year": 2,
                "sem": 4,
                "attendance_percent": 91,
                "next_class": "Discrete Math @ 10:15 AM",
            },
            {
                "id": 3,
                "name": "Rohan Verma",
                "roll_no": "CS-2024-044",
                "email": "rohan.verma@institute.edu",
                "phone": "+91 98765 43212",
                "guardian": "Sunita Verma (Mother)",
                "residential_status": "Hosteler (Block A, Rm 110)",
                "program": "B.Tech in Computer Science and Engineering",
                "year": 2,
                "sem": 4,
                "attendance_percent": 76,
                "next_class": "Data Structures @ 9AM",
            },
            {
                "id": 4,
                "name": "Neha Singh",
                "roll_no": "CS-2024-045",
                "email": "neha.singh@institute.edu",
                "phone": "+91 98765 43213",
                "guardian": "Arvind Singh (Father)",
                "residential_status": "Day Scholar",
                "program": "B.Tech in Computer Science and Engineering",
                "year": 2,
                "sem": 4,
                "attendance_percent": 88,
                "next_class": "Python with Linux Lab @ 11AM",
            },
        ]

        for ds in dummy_students:
            existing = db.execute(
                "SELECT id FROM students WHERE roll_no = ?",
                (ds["roll_no"],),
            ).fetchone()
            if existing is None:
                db.execute(
                    """
                    INSERT OR IGNORE INTO students (
                        id, name, roll_no, email, phone, guardian, residential_status,
                        program, year, sem, attendance_percent, next_class, password_hash, schedule_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ds["id"],
                        ds["name"],
                        ds["roll_no"],
                        ds["email"],
                        ds["phone"],
                        ds["guardian"],
                        ds["residential_status"],
                        ds["program"],
                        ds["year"],
                        ds["sem"],
                        ds["attendance_percent"],
                        ds["next_class"],
                        generate_password_hash(default_password),
                        1,
                    ),
                )

        # Ensure every student has a password_hash
        missing_pw = db.execute(
            "SELECT id FROM students WHERE password_hash IS NULL OR TRIM(password_hash) = ''"
        ).fetchall()
        for row in missing_pw:
            db.execute(
                "UPDATE students SET password_hash = ? WHERE id = ?",
                (generate_password_hash(default_password), int(row[0])),
            )

        admin_count = db.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
        if int(admin_count) == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.execute(
                """
                INSERT INTO admin_users (username, full_name, role, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "admin",
                    "System Administrator",
                    "admin",
                    generate_password_hash("admin123"),
                    now,
                ),
            )

        tt_count = db.execute("SELECT COUNT(*) FROM weekly_timetable").fetchone()[0]
        if tt_count == 0:
            db.executemany(
                """
                INSERT INTO weekly_timetable (day_of_week, start_time, end_time, subject, room, instructor)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (0, "09:00", "10:00", "Data Structures", "C-101", "Dr. Mehta"),
                    (0, "10:15", "11:15", "Discrete Math", "C-203", "Prof. Rao"),
                    (1, "09:00", "10:30", "Operating Systems", "C-105", "Prof. Sharma"),
                    (1, "11:00", "13:00", "Physics Lab", "Lab-2", "Dr. Singh"),
                    (2, "10:00", "11:00", "Computer Networks", "C-110", "Prof. Verma"),
                    (3, "09:30", "10:30", "Data Structures", "C-101", "Dr. Mehta"),
                    (3, "10:45", "11:45", "OS Tutorial", "C-105", "TA Team"),
                    (4, "09:00", "10:00", "Software Engineering", "C-120", "Prof. Khan"),
                    (4, "10:15", "11:15", "Library Hour", "Library", "Library Admin"),
                ],
            )

        today = datetime.now().date()
        start = today.toordinal() - (7 * 28) + 1
        student_ids = [r[0] for r in db.execute("SELECT id FROM students ORDER BY id").fetchall()]
        for sid in student_ids:
            existing = db.execute(
                "SELECT COUNT(*) FROM attendance_heatmap WHERE student_id = ?",
                (int(sid),),
            ).fetchone()[0]
            if int(existing) > 0:
                continue
            rows = []
            for i in range(7 * 28):
                d = datetime.fromordinal(start + i).date().isoformat()
                lvl = (i * 3 + sid) % 5
                rows.append((int(sid), d, int(lvl)))
            db.executemany(
                """
                INSERT INTO attendance_heatmap (student_id, att_date, level)
                VALUES (?, ?, ?)
                """,
                rows,
            )

        program_count = db.execute("SELECT COUNT(*) FROM programs").fetchone()[0]
        if program_count == 0:
            db.execute(
                "INSERT INTO programs (id, name, branch) VALUES (?, ?, ?)",
                (1, "B.Tech", "IT"),
            )

        semres_count = db.execute("SELECT COUNT(*) FROM semester_results").fetchone()[0]
        if semres_count == 0:
            declared_on = "2025-03-04"
            session_label = "Semester Examination 2025-26"
            program_id = 1
            semester = 4
            db.execute(
                """
                INSERT INTO semester_results (
                    student_id, program_id, semester, session_label, university, college_label,
                    student_name, student_type, father_name, mother_name, roll_no, enrollment_no,
                    sgpa, result_status, declared_on
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    program_id,
                    semester,
                    session_label,
                    "Deen Dayal Upadhyaya Gorakhpur University, Gorakhpur",
                    "DEEN DAYAL UPADHYAYA GORAKHPUR UNIVERSITY, GORAKHPUR",
                    "Alex Johnson",
                    "REGULAR",
                    "Robert Johnson",
                    "Mary Johnson",
                    "2514670010038",
                    "DDU0012509999",
                    8.46,
                    "PASSED",
                    declared_on,
                ),
            )
            result_id = db.execute("SELECT last_insert_rowid() ").fetchone()[0]
            db.executemany(
                """
                INSERT INTO semester_result_courses (
                    result_id, category, course_code, course_title,
                    ext_theory, int_theory, int_pract, ext_pract,
                    obt_marks, total_credit, grade, grade_point
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (result_id, "Major Courses", "ECHE101", "Engineering Chemistry", 41, 20, None, None, 61, 3, "B+", 7),
                    (result_id, "Major Courses", "EMAT101", "Engineering Mathematics-I", 48, 24, None, None, 72, 3, "A", 8),
                    (result_id, "Major Courses", "HSM101", "Professional Communication", 56, 19, None, None, 75, 3, "A", 8),
                    (result_id, "Major Courses", "ECE101", "Basic Electronics Engineering", 69, 22, None, None, 91, 3, "O", 10),
                    (result_id, "Major Courses", "ME101", "Engineering Graphics & Design", None, None, 22, 71, 93, 2, "O", 10),
                    (result_id, "Major Courses", "ECHE151", "Engineering Chemistry Lab", None, None, 20, 55, 75, 1, "A", 8),
                    (result_id, "Major Courses", "HSM151", "Professional Communication Lab", None, None, 17, 53, 70, 1, "A", 8),
                    (result_id, "Major Courses", "ECE151", "Basic Electronics Engineering Lab", None, None, 23, 60, 83, 1, "A+", 9),
                    (result_id, "Ability Enhancement Course", "AE1DDSP", "Pandit Deen Dayal Upadhyaya Vichar Evam Darshan", 86, None, None, None, 86, 2, "A+", 9),
                    (result_id, "Skill Enhancement Course", "SE1MAT", "Basic Arithmetic", 76, None, None, None, 76, 3, "A", 8),
                ],
            )

        details_seed = {
            1: ("Robert Johnson", "Male", "GENERAL", "123, Campus Housing, Institute Campus", "CS-2024-042"),
            2: ("Anil Sharma", "Female", "OBC", "45, City Center, Near Metro", "CS-2024-043"),
            3: ("Suresh Verma", "Male", "GENERAL", "Block A Hostel, Room 110", "CS-2024-044"),
            4: ("Arvind Singh", "Female", "SC", "78, Riverside Colony", "CS-2024-045"),
        }
        for sid in student_ids:
            if int(sid) not in details_seed:
                continue
            exists = db.execute(
                "SELECT 1 FROM student_details WHERE student_id = ?",
                (int(sid),),
            ).fetchone()
            if exists is None:
                father, gender, category, address, exam_roll = details_seed[int(sid)]
                db.execute(
                    """
                    INSERT INTO student_details (student_id, father_name, gender, category, address, exam_roll_number)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (int(sid), father, gender, category, address, exam_roll),
                )

        profile_seed = {
            1: ("Active", "2023-2027", "Computer Science", "A", "123, Campus Housing, Institute Campus", "Robert Johnson", "Father", "+91-98765-12345"),
            2: ("Active", "2023-2027", "Computer Science", "B", "45, City Center, Near Metro", "Anil Sharma", "Father", "+91-98765-22345"),
            3: ("Active", "2023-2027", "Computer Science", "A", "Block A Hostel, Room 110", "Suresh Verma", "Father", "+91-98765-32345"),
            4: ("Active", "2023-2027", "Computer Science", "C", "78, Riverside Colony", "Arvind Singh", "Father", "+91-98765-42345"),
        }
        for sid in student_ids:
            if int(sid) not in profile_seed:
                continue
            exists = db.execute(
                "SELECT 1 FROM student_profile WHERE student_id = ?",
                (int(sid),),
            ).fetchone()
            if exists is None:
                status, batch, dept, section, address, e_name, e_rel, e_phone = profile_seed[int(sid)]
                db.execute(
                    """
                    INSERT INTO student_profile (
                        student_id, status, batch, department, section, address,
                        emergency_contact_name, emergency_contact_relation, emergency_contact_phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (int(sid), status, batch, dept, section, address, e_name, e_rel, e_phone),
                )

        dues_seed = {1: 1500, 2: 0, 3: 800, 4: 300}
        for sid in student_ids:
            if int(sid) not in dues_seed:
                continue
            exists = db.execute(
                "SELECT 1 FROM student_dues WHERE student_id = ?",
                (int(sid),),
            ).fetchone()
            if exists is None:
                db.execute(
                    "INSERT INTO student_dues (student_id, pending_amount) VALUES (?, ?)",
                    (int(sid), int(dues_seed[int(sid)])),
                )

        for sid in student_ids:
            exists = db.execute(
                "SELECT 1 FROM student_programs WHERE student_id = ?",
                (int(sid),),
            ).fetchone()
            if exists is None:
                db.execute(
                    "INSERT INTO student_programs (student_id, program_id) VALUES (?, ?)",
                    (int(sid), 1),
                )

        subj_count = db.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        if subj_count == 0:
            subj_cols = {row[1] for row in db.execute("PRAGMA table_info(subjects)").fetchall()}
            seed_rows = [
                (1, 4, "AE3ENG1", "Basics of English Grammar"),
                (1, 4, "ECE202", "Digital Electronics & Logic Design"),
                (1, 4, "ECE252", "Digital Electronics & Logic Design Lab"),
                (1, 4, "ENV201", "Environment & Ecology"),
                (1, 4, "IT201", "Mathematics for Machine Learning"),
                (1, 4, "IT202", "Data Structure"),
                (1, 4, "IT203", "Python with Linux"),
                (1, 4, "IT204", "Discrete Mathematics"),
                (1, 4, "IT251", "Mathematics for Machine Learning Lab"),
                (1, 4, "IT252", "Data Structure Lab"),
                (1, 4, "IT253", "Python with Linux Lab"),
                (1, 4, "SE3MAT1", "Basics of Reasoning and Logic"),
            ]
            if {"course_code", "course_name"}.issubset(subj_cols) and {"code", "name"}.issubset(subj_cols):
                db.executemany(
                    """
                    INSERT INTO subjects (program_id, semester, course_code, course_name, code, name)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [(p, s, c, n, c, n) for (p, s, c, n) in seed_rows],
                )
            elif {"course_code", "course_name"}.issubset(subj_cols):
                db.executemany(
                    """
                    INSERT INTO subjects (program_id, semester, course_code, course_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    seed_rows,
                )
            else:
                db.executemany(
                    """
                    INSERT INTO subjects (program_id, semester, code, name)
                    VALUES (?, ?, ?, ?)
                    """,
                    seed_rows,
                )

        session_label = "Odd Semester (2025-26)"
        student_sem = 4
        session_count = db.execute(
            "SELECT COUNT(*) FROM exam_sessions WHERE session_label = ? AND program_id = ? AND semester = ?",
            (session_label, 1, student_sem),
        ).fetchone()[0]
        if session_count == 0:
            issued = datetime.utcnow().isoformat(timespec="seconds")
            db.execute(
                """
                INSERT INTO exam_sessions (
                    session_label, program_id, semester, university, college_label, exam_center, status, issued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_label,
                    1,
                    student_sem,
                    "Deen Dayal Upadhyaya Gorakhpur University, Gorakhpur",
                    "(001) DEEN DAYAL UPADHYAYA GORAKHPUR UNIVERSITY, GORAKHPUR",
                    "(001) DEEN DAYAL UPADHYAYA GORAKHPUR UNIVERSITY, GORAKHPUR",
                    "ACTIVE",
                    issued,
                ),
            )

        enroll_count = db.execute("SELECT COUNT(*) FROM student_subject_enrollments").fetchone()[0]
        if enroll_count == 0:
            student_ids = [r[0] for r in db.execute("SELECT id FROM students ORDER BY id").fetchall()]
            for sid in student_ids:
                db.execute(
                    """
                    INSERT INTO student_subject_enrollments (student_id, subject_id, session_label)
                    SELECT ?, s.id, ?
                    FROM subjects s
                    WHERE s.program_id = ? AND s.semester = ?
                    """,
                    (int(sid), session_label, 1, student_sem),
                )

        tt_count = db.execute("SELECT COUNT(*) FROM exam_timetable").fetchone()[0]
        if tt_count == 0:
            session_id = db.execute(
                "SELECT id FROM exam_sessions WHERE session_label = ? AND program_id = ? AND semester = ?",
                (session_label, 1, student_sem),
            ).fetchone()[0]
            subj_by_code = {
                r[1]: r[0]
                for r in db.execute(
                    "SELECT id, code FROM subjects WHERE program_id = ? AND semester = ?",
                    (1, student_sem),
                ).fetchall()
            }
            db.executemany(
                """
                INSERT INTO exam_timetable (session_id, subject_id, paper_type, exam_date, exam_time)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (session_id, subj_by_code["AE3ENG1"], "REGULAR", "2025-12-26", "11:30 AM to 01:00 PM"),
                    (session_id, subj_by_code["ECE202"], "REGULAR", None, None),
                    (session_id, subj_by_code["ECE252"], "REGULAR", None, None),
                    (session_id, subj_by_code["ENV201"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT201"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT202"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT203"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT204"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT251"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT252"], "REGULAR", None, None),
                    (session_id, subj_by_code["IT253"], "REGULAR", None, None),
                    (session_id, subj_by_code["SE3MAT1"], "REGULAR", "2025-12-27", "11:30 AM to 01:00 PM"),
                ],
            )

        forms_count = db.execute("SELECT COUNT(*) FROM exam_forms").fetchone()[0]
        if forms_count == 0:
            db.executemany(
                """
                INSERT INTO exam_forms (title, semester_label, status, open_from, open_to, fee, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Examination Form",
                        "Odd Semester (2025-26)",
                        "OPEN",
                        "2025-12-01",
                        "2025-12-20",
                        1200,
                        "Fill carefully. Any discrepancy may lead to cancellation.",
                    ),
                    (
                        "Back Paper Form",
                        "Odd Semester (2025-26)",
                        "CLOSED",
                        "2025-11-01",
                        "2025-11-10",
                        800,
                        "Closed. Contact exam cell for late submission.",
                    ),
                ],
            )

        admit_count = db.execute("SELECT COUNT(*) FROM admit_cards").fetchone()[0]
        if admit_count == 0:
            issued = datetime.utcnow().isoformat(timespec="seconds")
            db.execute(
                """
                INSERT INTO admit_cards (
                    student_id, university, session_label, program_label, college_label,
                    student_name, roll_number, father_name, gender, category, address,
                    exam_center, image_label, issued_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "Deen Dayal Upadhyaya Gorakhpur University, Gorakhpur",
                    "Odd Semester (2025-26)",
                    "B.Tech. (IT) - 3 Semester",
                    "(001) DEEN DAYAL UPADHYAYA GORAKHPUR UNIVERSITY, GORAKHPUR",
                    "ADITYA CHAUDHARI",
                    "2514670010038",
                    "RAM ASARE CHAUDHARI",
                    "Male",
                    "OBC",
                    "VILLAGE GHOGHARA POST BODARWAR DIST KUSHINAGAR",
                    "(001) DEEN DAYAL UPADHYAYA GORAKHPUR UNIVERSITY, GORAKHPUR",
                    "Stuimg",
                    issued,
                ),
            )
            admit_id = db.execute("SELECT last_insert_rowid() ").fetchone()[0]
            db.executemany(
                """
                INSERT INTO admit_card_subjects (
                    admit_card_id, sno, paper_type, subject_code, subject_name, exam_date, exam_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (admit_id, 1, "REGULAR", "AE3ENG1", "Basics of English Grammar", "2025-12-26", "11:30 AM to 01:00 PM"),
                    (admit_id, 2, "REGULAR", "ECE202", "Digital Electronics & Logic Design", None, None),
                    (admit_id, 3, "REGULAR", "ECE252", "Digital Electronics & Logic Design Lab", None, None),
                    (admit_id, 4, "REGULAR", "ENV201", "Environment & Ecology", None, None),
                    (admit_id, 5, "REGULAR", "IT201", "Mathematics for Machine Learning", None, None),
                    (admit_id, 6, "REGULAR", "IT202", "Data Structure", None, None),
                    (admit_id, 7, "REGULAR", "IT203", "Python with Linux", None, None),
                    (admit_id, 8, "REGULAR", "IT204", "Discrete Mathematics", None, None),
                    (admit_id, 9, "REGULAR", "IT251", "Mathematics for Machine Learning Lab", None, None),
                    (admit_id, 10, "REGULAR", "IT252", "Data Structure Lab", None, None),
                    (admit_id, 11, "REGULAR", "IT253", "Python with Linux Lab", None, None),
                    (admit_id, 12, "REGULAR", "SE3MAT1", "Basics of Reasoning and Logic", "2025-12-27", "11:30 AM to 01:00 PM"),
                ],
            )

        cal_count = db.execute("SELECT COUNT(*) FROM calendar_items").fetchone()[0]
        if cal_count == 0:
            # Use current month for dummy data so it always shows
            today = datetime.now()
            month_prefix = f"{today.year:04d}-{today.month:02d}"
            db.executemany(
                """
                INSERT INTO calendar_items (item_date, item_type, title, description)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (f"{month_prefix}-02", "HOLIDAY", "Public Holiday", "Institute closed for a public holiday."),
                    (f"{month_prefix}-10", "EVENT", "Career Talk", "Guest lecture on internships and placements."),
                    (f"{month_prefix}-18", "EVENT", "Hackathon Workshop", "Preparation session for Hackathon 2024."),
                    (f"{month_prefix}-25", "HOLIDAY", "Library Maintenance", "Digital library may be intermittent."),
                ],
            )

        ann_count = db.execute("SELECT COUNT(*) FROM announcements").fetchone()[0]
        if ann_count == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.executemany(
                """
                INSERT INTO announcements (category, title, body, author, tag1, tag2, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "URGENT",
                        "End-Term Lab Exam Rescheduled",
                        "The Operating Systems lab exam originally scheduled for Friday has been moved to Monday, June 10th due to maintenance in the server room.",
                        "Prof. S. Sharma",
                        "#CSE_Department",
                        "#Examination",
                        now,
                    ),
                    (
                        "GENERAL",
                        "Annual Library Stock Audit",
                        "Library will remain closed for students from May 25-27 for the annual audit. E-resources will remain accessible via the student portal.",
                        "Library Admin",
                        "#All_Students",
                        None,
                        now,
                    ),
                    (
                        "EVENT",
                        "Hackathon 2024: Registration Open",
                        "Calling all innovators! Registrations for the 24-hour campus hackathon are now open. Team up and win exciting prizes up to ₹50,000.",
                        "Tech Club",
                        "#Hackathon",
                        "#Innovation",
                        now,
                    ),
                ],
            )

        # Migrate existing news_posts schema (older versions had title/body/author/created_at)
        cols = {row[1] for row in db.execute("PRAGMA table_info(news_posts)").fetchall()}
        required = {"priority", "date_time", "heading", "body", "sender", "news_type", "tags"}
        legacy = {"title", "author", "created_at"}
        if legacy.issubset(cols) and not required.issubset(cols):
            db.executescript(
                """
                ALTER TABLE news_posts RENAME TO news_posts_legacy;
                CREATE TABLE news_posts (
                    id INTEGER PRIMARY KEY,
                    priority TEXT NOT NULL,
                    date_time TEXT NOT NULL,
                    heading TEXT NOT NULL,
                    body TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    news_type TEXT NOT NULL,
                    tags TEXT NOT NULL
                );
                """
            )
            db.execute(
                """
                INSERT INTO news_posts (id, priority, date_time, heading, body, sender, news_type, tags)
                SELECT id,
                       'NORMAL' AS priority,
                       created_at AS date_time,
                       title AS heading,
                       body,
                       author AS sender,
                       'News' AS news_type,
                       '' AS tags
                FROM news_posts_legacy;
                """
            )

        news_count = db.execute("SELECT COUNT(*) FROM news_posts").fetchone()[0]
        if news_count == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.executemany(
                """
                INSERT INTO news_posts (priority, date_time, heading, body, sender, news_type, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "URGENT",
                        now,
                        "Campus Wi-Fi Upgrade Tonight",
                        "Network maintenance will run from 11:00 PM to 2:00 AM. Expect intermittent connectivity.",
                        "IT Desk",
                        "Alert",
                        "IT,Campus",
                    ),
                    (
                        "LOW",
                        now,
                        "New Journals Added to Digital Library",
                        "ACM and IEEE latest issues are now available in the Digital Library section.",
                        "Library Team",
                        "Update",
                        "Library,Research",
                    ),
                    (
                        "HIGH",
                        now,
                        "Tech Fest 2024 Registration",
                        "Registrations are open for Tech Fest 2024. Last date: Jan 20. Events: Hackathon, Code Wars, Robotics.",
                        "Student Council",
                        "Event",
                        "Cultural,Event",
                    ),
                ],
            )

        existing_priorities = {
            r[0]
            for r in db.execute("SELECT DISTINCT priority FROM news_posts").fetchall()
            if r[0]
        }
        required_priorities = ["URGENT", "HIGH", "MEDIUM", "NORMAL", "LOW"]
        missing_priorities = [p for p in required_priorities if p not in existing_priorities]
        if missing_priorities:
            now = datetime.utcnow().isoformat(timespec="seconds")
            seed_map = {
                "URGENT": (
                    "URGENT",
                    now,
                    "Urgent: Class Suspension Notice",
                    "Due to severe weather, all classes after 2:00 PM are suspended today. Check the portal for updates.",
                    "Admin Office",
                    "Alert",
                    "Campus,Weather",
                ),
                "HIGH": (
                    "HIGH",
                    now,
                    "High Priority: Exam Form Deadline",
                    "Examination form submission closes tomorrow 5:00 PM. Late submissions will not be accepted.",
                    "Examination Cell",
                    "Notice",
                    "Exams,Deadline",
                ),
                "MEDIUM": (
                    "MEDIUM",
                    now,
                    "Medium Priority: Placement Training Session",
                    "Aptitude training session is scheduled this Friday 3:00 PM in Seminar Hall-1.",
                    "Training & Placement",
                    "Update",
                    "Placements,Training",
                ),
                "NORMAL": (
                    "NORMAL",
                    now,
                    "General Update: Canteen Menu Refresh",
                    "The canteen menu has been updated with new healthy options starting next week.",
                    "Campus Services",
                    "Update",
                    "Canteen,Campus",
                ),
                "LOW": (
                    "LOW",
                    now,
                    "Low Priority: Library Reading Hours",
                    "Extended reading hall hours this weekend (9 AM - 8 PM).",
                    "Library Team",
                    "Update",
                    "Library,Facilities",
                ),
            }
            db.executemany(
                """
                INSERT INTO news_posts (priority, date_time, heading, body, sender, news_type, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [seed_map[p] for p in missing_priorities],
            )

        sch_count = db.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
        if sch_count == 0:
            db.executemany(
                """
                INSERT INTO schedules (title, location, start_at, end_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "Physics Lab",
                        "Lab-2",
                        "2025-12-29 14:00",
                        "2025-12-29 16:00",
                    ),
                    (
                        "Data Structures Lecture",
                        "Room C-101",
                        "2025-12-30 10:00",
                        "2025-12-30 11:00",
                    ),
                ],
            )

        books_count = db.execute("SELECT COUNT(*) FROM library_books").fetchone()[0]
        if books_count == 0:
            db.executemany(
                """
                INSERT INTO library_books (title, author, status, due_date)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        "Operating System Concepts",
                        "Silberschatz",
                        "ISSUED",
                        "2026-01-05",
                    ),
                    (
                        "Introduction to Algorithms",
                        "Cormen",
                        "AVAILABLE",
                        None,
                    ),
                ],
            )

        res_count = db.execute("SELECT COUNT(*) FROM library_resources").fetchone()[0]
        if res_count == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.executemany(
                """
                INSERT INTO library_resources (
                    heading, description, pdf_url, uploader, uploaded_at, tags
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "DSA Notes: Arrays & Strings",
                        "Concise notes covering arrays, strings, and common patterns with examples.",
                        "https://example.com/resources/dsa-arrays-strings.pdf",
                        "Prof. Mehta",
                        now,
                        "DSA,Notes,Semester-4",
                    ),
                    (
                        "Operating Systems: Process Scheduling",
                        "Quick reference on FCFS, SJF, RR, priority scheduling with solved numericals.",
                        "https://example.com/resources/os-scheduling.pdf",
                        "Prof. Sharma",
                        now,
                        "OS,Notes,Core",
                    ),
                    (
                        "Computer Networks: TCP/IP Cheat Sheet",
                        "One-page cheat sheet for TCP/IP model, ports, common protocols and headers.",
                        "https://example.com/resources/cn-tcpip-cheatsheet.pdf",
                        "IT Desk",
                        now,
                        "CN,CheatSheet,Protocols",
                    ),
                    (
                        "DBMS Lab Manual",
                        "Lab experiments for SQL, normalization, indexing and transactions.",
                        "https://example.com/resources/dbms-lab-manual.pdf",
                        "Lab Instructor",
                        now,
                        "DBMS,Lab,SQL",
                    ),
                    (
                        "Placement Aptitude Set 01",
                        "Practice questions for aptitude and reasoning with answer key.",
                        "https://example.com/resources/aptitude-set-01.pdf",
                        "Training & Placement",
                        now,
                        "Placement,Aptitude,Practice",
                    ),
                ],
            )

        results_count = db.execute("SELECT COUNT(*) FROM exam_results").fetchone()[0]
        if results_count == 0:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.executemany(
                """
                INSERT INTO exam_results (course, exam, score, max_score, grade, published_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("Operating Systems", "Mid-Term", 42, 50, "A", now),
                    ("Data Structures", "Quiz 2", 18, 20, "A+", now),
                ],
            )

        db.commit()
    finally:
        db.close()


@app.context_processor
def inject_student():
    db = get_db()
    sid = get_current_student_id()
    student = None
    if sid is not None:
        student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    aid = get_current_admin_id()
    admin_user = None
    if aid is not None:
        admin_user = db.execute("SELECT * FROM admin_users WHERE id = ?", (aid,)).fetchone()
    return {"student": student, "admin_user": admin_user}


@app.get("/login")
def login():
    if get_current_student_id() is not None:
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None)


@app.post("/login")
def login_post():
    roll_no = (request.form.get("roll_no") or "").strip()
    password = request.form.get("password") or ""
    if not roll_no or not password:
        return render_template("login.html", error="Please enter roll number and password.")

    db = get_db()
    student = db.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,)).fetchone()
    if not student:
        return render_template("login.html", error="Invalid roll number or password.")

    if not student["password_hash"] or not check_password_hash(student["password_hash"], password):
        return render_template("login.html", error="Invalid roll number or password.")

    session["student_id"] = int(student["id"])
    return redirect(url_for("dashboard"))


@app.get("/logout")
def logout():
    session.pop("student_id", None)
    return redirect(url_for("login"))


@app.get("/admin/login")
def admin_login():
    if get_current_admin_id() is not None:
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html", error=None)


@app.post("/admin/login")
def admin_login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if not username or not password:
        return render_template("admin_login.html", error="Please enter username and password.")

    db = get_db()
    admin_user = db.execute(
        "SELECT * FROM admin_users WHERE username = ?",
        (username,),
    ).fetchone()
    if not admin_user or not admin_user["password_hash"] or not check_password_hash(
        admin_user["password_hash"], password
    ):
        return render_template("admin_login.html", error="Invalid username or password.")

    session["admin_user_id"] = int(admin_user["id"])
    return redirect(url_for("admin_dashboard"))


@app.get("/admin/logout")
def admin_logout():
    session.pop("admin_user_id", None)
    return redirect(url_for("admin_login"))


@app.get("/admin/change-password")
@admin_login_required
def admin_change_password():
    db = get_db()
    aid = get_current_admin_id()
    admin_user = db.execute("SELECT * FROM admin_users WHERE id = ?", (aid,)).fetchone()
    return render_template(
        "admin_change_password.html",
        page_title="Change Password",
        page_subtitle="Update your admin password",
        active_page="admin",
        admin_user=admin_user,
        error=None,
        success=None,
    )


@app.post("/admin/change-password")
@admin_login_required
def admin_change_password_post():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    next_url = get_safe_next_url("admin_dashboard")
    sep = "&" if ("?" in next_url) else "?"

    db = get_db()
    aid = get_current_admin_id()
    admin_user = db.execute("SELECT * FROM admin_users WHERE id = ?", (aid,)).fetchone()
    if not admin_user:
        session.pop("admin_user_id", None)
        return redirect(url_for("admin_login"))

    if not current_password or not new_password or not confirm_password:
        return redirect(f"{next_url}{sep}ap_error={quote('Please fill in all fields.')}")

    if not admin_user["password_hash"] or not check_password_hash(admin_user["password_hash"], current_password):
        return redirect(f"{next_url}{sep}ap_error={quote('Current password is incorrect.')}")

    if len(new_password) < 8:
        return redirect(
            f"{next_url}{sep}ap_error={quote('New password must be at least 8 characters.')}")

    if new_password != confirm_password:
        return redirect(
            f"{next_url}{sep}ap_error={quote('New password and confirmation do not match.')}")

    db.execute(
        "UPDATE admin_users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), int(admin_user["id"])),
    )
    db.commit()

    return redirect(f"{next_url}{sep}ap_success={quote('Password updated successfully.')}")


@app.get("/admin")
@admin_login_required
def admin_dashboard():
    db = get_db()
    aid = get_current_admin_id()
    admin_user = db.execute("SELECT * FROM admin_users WHERE id = ?", (aid,)).fetchone()
    news_count = db.execute("SELECT COUNT(*) FROM news_posts").fetchone()[0]
    open_forms = 0
    try:
        rows = db.execute("SELECT open_from, open_to FROM exam_forms").fetchall()
        for r in rows:
            if is_exam_form_open(r["open_from"], r["open_to"]):
                open_forms += 1
    except Exception:
        open_forms = db.execute("SELECT COUNT(*) FROM exam_forms WHERE status = 'OPEN'").fetchone()[0]
    return render_template(
        "admin_dashboard.html",
        page_title="Admin Panel",
        page_subtitle="Manage restricted content",
        active_page="admin",
        admin_user=admin_user,
        news_count=int(news_count),
        open_forms=int(open_forms),
        error=None,
    )


@app.get("/admin/schedules")
@admin_login_required
def admin_schedules():
    db = get_db()

    groups = db.execute("SELECT * FROM schedule_groups ORDER BY id ASC").fetchall()
    selected_raw = (request.args.get("schedule_id") or "").strip()
    selected_id = None
    if selected_raw:
        try:
            selected_id = int(selected_raw)
        except Exception:
            selected_id = None
    if selected_id is None:
        selected_id = int(groups[0]["id"]) if groups else 1

    calendar_items = db.execute(
        "SELECT * FROM calendar_items ORDER BY date(item_date) DESC, id DESC"
    ).fetchall()
    timetable_rows = db.execute(
        """
        SELECT * FROM weekly_timetable
        WHERE schedule_id = ?
        ORDER BY day_of_week ASC, time(start_time) ASC
        """,
        (int(selected_id),),
    ).fetchall()
    return render_template(
        "admin_schedules.html",
        page_title="Manage Schedules",
        page_subtitle="Monthly events & holidays and weekly timetable",
        active_page="admin_schedules",
        calendar_items=calendar_items,
        timetable_rows=timetable_rows,
        schedule_groups=groups,
        selected_schedule_id=int(selected_id),
        error=None,
    )


@app.post("/admin/calendar-items/new")
@admin_login_required
def admin_calendar_item_create():
    item_date = (request.form.get("item_date") or "").strip()
    item_type = (request.form.get("item_type") or "").strip()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not item_date or not item_type or not title:
        return redirect(url_for("admin_schedules"))
    db = get_db()
    db.execute(
        "INSERT INTO calendar_items (item_date, item_type, title, description) VALUES (?, ?, ?, ?)",
        (item_date, item_type, title, description),
    )
    db.commit()
    return redirect(url_for("admin_schedules"))


@app.post("/admin/calendar-items/<int:item_id>/update")
@admin_login_required
def admin_calendar_item_update(item_id: int):
    item_date = (request.form.get("item_date") or "").strip()
    item_type = (request.form.get("item_type") or "").strip()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not item_date or not item_type or not title:
        return redirect(url_for("admin_schedules"))
    db = get_db()
    db.execute(
        "UPDATE calendar_items SET item_date = ?, item_type = ?, title = ?, description = ? WHERE id = ?",
        (item_date, item_type, title, description, int(item_id)),
    )
    db.commit()
    return redirect(url_for("admin_schedules"))


@app.post("/admin/calendar-items/<int:item_id>/delete")
@admin_login_required
def admin_calendar_item_delete(item_id: int):
    db = get_db()
    db.execute("DELETE FROM calendar_items WHERE id = ?", (int(item_id),))
    db.commit()
    return redirect(url_for("admin_schedules"))


@app.post("/admin/schedules/groups/new")
@admin_login_required
def admin_schedule_group_create():
    name = (request.form.get("name") or "").strip()
    program = (request.form.get("program") or "").strip() or None
    department = (request.form.get("department") or "").strip() or None
    semester_raw = (request.form.get("semester") or "").strip()
    semester = None
    if semester_raw:
        try:
            semester = int(semester_raw)
        except Exception:
            semester = None
    if not name:
        return redirect(url_for("admin_schedules"))
    db = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO schedule_groups (name, program, department, semester, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, program, department, semester, now),
    )
    db.commit()
    new_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    return redirect(url_for("admin_schedules", schedule_id=new_id))


@app.post("/admin/schedules/events/new")
@admin_login_required
def admin_schedules_event_create():
    schedule_id_raw = (request.form.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1
    title = (request.form.get("title") or "").strip()
    location = (request.form.get("location") or "").strip()
    start_at = (request.form.get("start_at") or "").strip()
    end_at = (request.form.get("end_at") or "").strip()
    if not title or not location or not start_at or not end_at:
        db = get_db()
        groups = db.execute("SELECT * FROM schedule_groups ORDER BY id ASC").fetchall()
        calendar_items = db.execute(
            "SELECT * FROM calendar_items ORDER BY date(item_date) DESC, id DESC"
        ).fetchall()
        timetable_rows = db.execute(
            """
            SELECT * FROM weekly_timetable
            WHERE schedule_id = ?
            ORDER BY day_of_week ASC, time(start_time) ASC
            """,
            (int(schedule_id),),
        ).fetchall()
        return render_template(
            "admin_schedules.html",
            page_title="Manage Schedules",
            page_subtitle="Monthly events & holidays and weekly timetable",
            active_page="admin_schedules",
            calendar_items=calendar_items,
            timetable_rows=timetable_rows,
            schedule_groups=groups,
            selected_schedule_id=int(schedule_id),
            error="Please fill all required event fields.",
        )
    db = get_db()
    db.execute(
        "INSERT INTO schedules (schedule_id, title, location, start_at, end_at) VALUES (?, ?, ?, ?, ?)",
        (int(schedule_id), title, location, start_at, end_at),
    )
    db.commit()
    return redirect(url_for("admin_schedules", schedule_id=int(schedule_id)))


@app.post("/admin/schedules/events/<int:event_id>/delete")
@admin_login_required
def admin_schedules_event_delete(event_id: int):
    schedule_id_raw = (request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1
    db = get_db()
    db.execute("DELETE FROM schedules WHERE id = ?", (int(event_id),))
    db.commit()
    return redirect(url_for("admin_schedules", schedule_id=int(schedule_id)))


@app.post("/admin/schedules/timetable/new")
@admin_login_required
def admin_timetable_create():
    schedule_id_raw = (request.form.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1
    day_of_week_raw = (request.form.get("day_of_week") or "").strip()
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    room = (request.form.get("room") or "").strip()
    instructor = (request.form.get("instructor") or "").strip()
    try:
        day_of_week = int(day_of_week_raw)
    except Exception:
        day_of_week = -1
    if day_of_week < 0 or day_of_week > 6 or not start_time or not end_time or not subject or not room or not instructor:
        db = get_db()
        groups = db.execute("SELECT * FROM schedule_groups ORDER BY id ASC").fetchall()
        calendar_items = db.execute(
            "SELECT * FROM calendar_items ORDER BY date(item_date) DESC, id DESC"
        ).fetchall()
        timetable_rows = db.execute(
            """
            SELECT * FROM weekly_timetable
            WHERE schedule_id = ?
            ORDER BY day_of_week ASC, time(start_time) ASC
            """,
            (int(schedule_id),),
        ).fetchall()
        return render_template(
            "admin_schedules.html",
            page_title="Manage Schedules",
            page_subtitle="Monthly events & holidays and weekly timetable",
            active_page="admin_schedules",
            calendar_items=calendar_items,
            timetable_rows=timetable_rows,
            schedule_groups=groups,
            selected_schedule_id=int(schedule_id),
            error="Please fill all required timetable fields.",
        )
    db = get_db()
    db.execute(
        """
        INSERT INTO weekly_timetable (schedule_id, day_of_week, start_time, end_time, subject, room, instructor)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (int(schedule_id), day_of_week, start_time, end_time, subject, room, instructor),
    )
    db.commit()
    return redirect(url_for("admin_schedules", schedule_id=int(schedule_id)))


@app.post("/admin/schedules/timetable/<int:row_id>/delete")
@admin_login_required
def admin_timetable_delete(row_id: int):
    schedule_id_raw = (request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1
    db = get_db()
    db.execute("DELETE FROM weekly_timetable WHERE id = ?", (int(row_id),))
    db.commit()
    return redirect(url_for("admin_schedules", schedule_id=int(schedule_id)))


@app.get("/admin/teachers")
@admin_login_required
def admin_teachers():
    db = get_db()

    filters = {
        "q": (request.args.get("q") or "").strip(),
        "department": (request.args.get("department") or "").strip(),
        "designation": (request.args.get("designation") or "").strip(),
    }

    rows = db.execute("SELECT * FROM teachers ORDER BY name ASC").fetchall()

    q = filters["q"].lower()
    f_department = filters["department"].lower()
    f_designation = filters["designation"].lower()

    teachers = []
    for t in rows:
        t_dict = dict(t)
        hay = " ".join(
            [
                str(t_dict.get("name") or ""),
                str(t_dict.get("designation") or ""),
                str(t_dict.get("department") or ""),
                str(t_dict.get("email") or ""),
                str(t_dict.get("phone") or ""),
            ]
        ).lower()
        if q and q not in hay:
            continue
        if f_department and (str(t_dict.get("department") or "").lower() != f_department):
            continue
        if f_designation and (str(t_dict.get("designation") or "").lower() != f_designation):
            continue
        teachers.append(t)

    return render_template(
        "admin_teachers.html",
        page_title="Teachers",
        page_subtitle="Manage faculty list",
        active_page="admin_teachers",
        teachers=teachers,
        filters=filters,
        error=None,
    )


@app.post("/admin/teachers/<int:teacher_id>/update")
@admin_login_required
def admin_teacher_update(teacher_id: int):
    db = get_db()
    t = db.execute("SELECT * FROM teachers WHERE id = ?", (int(teacher_id),)).fetchone()
    if not t:
        return redirect(url_for("admin_teachers"))

    name = (request.form.get("name") or "").strip()
    designation = (request.form.get("designation") or "").strip()
    department = (request.form.get("department") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    phone = (request.form.get("phone") or "").strip() or None

    if not name or not designation or not department:
        return redirect(url_for("admin_teachers"))

    db.execute(
        "UPDATE teachers SET name = ?, designation = ?, department = ?, email = ?, phone = ? WHERE id = ?",
        (name, designation, department, email, phone, int(teacher_id)),
    )
    db.commit()
    return redirect(url_for("admin_teachers"))


@app.get("/admin/students")
@admin_login_required
def admin_students():
    db = get_db()

    filters = {
        "q": (request.args.get("q") or "").strip(),
        "program": (request.args.get("program") or "").strip(),
        "department": (request.args.get("department") or "").strip(),
        "year": (request.args.get("year") or "").strip(),
        "sem": (request.args.get("sem") or "").strip(),
        "schedule_id": (request.args.get("schedule_id") or "").strip(),
        "status": (request.args.get("status") or "").strip(),
        "section": (request.args.get("section") or "").strip(),
    }

    students = db.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    details = {
        int(r["student_id"]): r
        for r in db.execute("SELECT * FROM student_details").fetchall()
    }
    profiles = {
        int(r["student_id"]): r
        for r in db.execute("SELECT * FROM student_profile").fetchall()
    }
    dues = {
        int(r["student_id"]): r
        for r in db.execute("SELECT * FROM student_dues").fetchall()
    }
    groups = db.execute("SELECT * FROM schedule_groups ORDER BY id ASC").fetchall()

    def to_int(val: str) -> int | None:
        try:
            return int(val)
        except Exception:
            return None

    q = filters["q"].lower()
    f_program = filters["program"].lower()
    f_department = filters["department"].lower()
    f_year = to_int(filters["year"])
    f_sem = to_int(filters["sem"])
    f_schedule_id = to_int(filters["schedule_id"])
    f_status = filters["status"].lower()
    f_section = filters["section"].lower()

    filtered_students = []
    for s in students:
        s_dict = dict(s)
        sid = int(s_dict.get("id") or 0)
        p = profiles.get(sid)
        p_dict = dict(p) if p else {}
        hay = " ".join(
            [
                str(s_dict.get("name") or ""),
                str(s_dict.get("roll_no") or ""),
                str(s_dict.get("email") or ""),
                str(s_dict.get("phone") or ""),
                str(s_dict.get("program") or ""),
                str(p_dict.get("department") or ""),
                str(p_dict.get("section") or ""),
                str(p_dict.get("status") or ""),
            ]
        ).lower()

        if q and q not in hay:
            continue
        if f_program and (str(s_dict.get("program") or "").lower() != f_program):
            continue
        if f_department and (str(p_dict.get("department") or "").lower() != f_department):
            continue
        if f_year is not None and int(s_dict.get("year") or 0) != f_year:
            continue
        if f_sem is not None and int(s_dict.get("sem") or 0) != f_sem:
            continue
        if f_schedule_id is not None:
            current_schedule = s_dict.get("schedule_id") if ("schedule_id" in s.keys()) else None
            if int(current_schedule or 0) != f_schedule_id:
                continue
        if f_status and (str(p_dict.get("status") or "").lower() != f_status):
            continue
        if f_section and (str(p_dict.get("section") or "").lower() != f_section):
            continue

        filtered_students.append(s)

    return render_template(
        "admin_students.html",
        page_title="Students",
        page_subtitle="View and update registered students",
        active_page="admin_students",
        students=filtered_students,
        details_by_student_id=details,
        profile_by_student_id=profiles,
        dues_by_student_id=dues,
        schedule_groups=groups,
        filters=filters,
        error=None,
    )


@app.post("/admin/students/<int:student_id>/update")
@admin_login_required
def admin_student_update(student_id: int):
    form = {k: (request.form.get(k) or "").strip() for k in request.form.keys()}
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (int(student_id),)).fetchone()
    if not student:
        return redirect(url_for("admin_students"))

    def to_int(val: str, default: int = 0) -> int:
        try:
            return int(val)
        except Exception:
            return default

    schedule_id = None
    if "schedule_id" in student.keys():
        raw = form.get("schedule_id") or ""
        schedule_id = to_int(raw, default=0) or None

    year = to_int(form.get("year") or str(student["year"]), default=int(student["year"]))
    sem = to_int(form.get("sem") or str(student["sem"]), default=int(student["sem"]))
    attendance_percent = to_int(
        form.get("attendance_percent") or str(student["attendance_percent"]),
        default=int(student["attendance_percent"]),
    )
    pending_amount = to_int(form.get("pending_amount") or "0", default=0)

    # Update students
    student_cols = {row[1] for row in db.execute("PRAGMA table_info(students)").fetchall()}
    update_cols = [
        "name",
        "roll_no",
        "email",
        "phone",
        "guardian",
        "residential_status",
        "program",
        "year",
        "sem",
        "attendance_percent",
        "next_class",
    ]
    if "schedule_id" in student_cols:
        update_cols.append("schedule_id")

    values = {
        "name": form.get("name") or student["name"],
        "roll_no": form.get("roll_no") or student["roll_no"],
        "email": form.get("email") or student["email"],
        "phone": form.get("phone") or student["phone"],
        "guardian": form.get("guardian") or student["guardian"],
        "residential_status": form.get("residential_status") or student["residential_status"],
        "program": form.get("program") or student["program"],
        "year": year,
        "sem": sem,
        "attendance_percent": attendance_percent,
        "next_class": form.get("next_class") or student["next_class"],
    }
    if "schedule_id" in student_cols:
        values["schedule_id"] = schedule_id

    set_sql = ", ".join([f"{c} = ?" for c in update_cols])
    db.execute(
        f"UPDATE students SET {set_sql} WHERE id = ?",
        [values[c] for c in update_cols] + [int(student_id)],
    )

    # Upsert student_details
    details_cols = {row[1] for row in db.execute("PRAGMA table_info(student_details)").fetchall()}
    if details_cols:
        exists = db.execute(
            "SELECT 1 FROM student_details WHERE student_id = ?",
            (int(student_id),),
        ).fetchone()
        payload = {
            "father_name": form.get("father_name"),
            "gender": form.get("gender"),
            "category": form.get("category"),
            "address": form.get("details_address"),
            "exam_roll_number": form.get("exam_roll_number"),
        }
        payload = {k: v for k, v in payload.items() if (k in details_cols and v)}
        if exists is None:
            if payload and {"father_name", "gender", "category", "address"}.issubset(set(payload.keys()) | {"father_name", "gender", "category", "address"}):
                # Fill required fallbacks from current values when missing
                father = payload.get("father_name") or "-"
                gender = payload.get("gender") or "-"
                category = payload.get("category") or "-"
                addr = payload.get("address") or "-"
                exam_roll = payload.get("exam_roll_number")
                db.execute(
                    """
                    INSERT INTO student_details (student_id, father_name, gender, category, address, exam_roll_number)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (int(student_id), father, gender, category, addr, exam_roll),
                )
        else:
            if payload:
                set_sql = ", ".join([f"{k} = ?" for k in payload.keys()])
                db.execute(
                    f"UPDATE student_details SET {set_sql} WHERE student_id = ?",
                    list(payload.values()) + [int(student_id)],
                )

    # Upsert student_profile
    prof_cols = {row[1] for row in db.execute("PRAGMA table_info(student_profile)").fetchall()}
    if prof_cols:
        exists = db.execute(
            "SELECT 1 FROM student_profile WHERE student_id = ?",
            (int(student_id),),
        ).fetchone()
        payload = {
            "status": form.get("status"),
            "batch": form.get("batch"),
            "department": form.get("department"),
            "section": form.get("section"),
            "address": form.get("profile_address"),
            "emergency_contact_name": form.get("emergency_contact_name"),
            "emergency_contact_relation": form.get("emergency_contact_relation"),
            "emergency_contact_phone": form.get("emergency_contact_phone"),
        }
        payload = {k: v for k, v in payload.items() if (k in prof_cols and v)}
        if exists is None:
            if prof_cols:
                db.execute(
                    """
                    INSERT INTO student_profile (
                        student_id, status, batch, department, section, address,
                        emergency_contact_name, emergency_contact_relation, emergency_contact_phone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(student_id),
                        payload.get("status") or "Active",
                        payload.get("batch") or "-",
                        payload.get("department") or "-",
                        payload.get("section") or "-",
                        payload.get("address") or "-",
                        payload.get("emergency_contact_name") or "-",
                        payload.get("emergency_contact_relation") or "-",
                        payload.get("emergency_contact_phone") or "-",
                    ),
                )
        else:
            if payload:
                set_sql = ", ".join([f"{k} = ?" for k in payload.keys()])
                db.execute(
                    f"UPDATE student_profile SET {set_sql} WHERE student_id = ?",
                    list(payload.values()) + [int(student_id)],
                )

    # Upsert dues
    dues_cols = {row[1] for row in db.execute("PRAGMA table_info(student_dues)").fetchall()}
    if "pending_amount" in dues_cols:
        exists = db.execute(
            "SELECT 1 FROM student_dues WHERE student_id = ?",
            (int(student_id),),
        ).fetchone()
        if exists is None:
            db.execute(
                "INSERT INTO student_dues (student_id, pending_amount) VALUES (?, ?)",
                (int(student_id), int(pending_amount)),
            )
        else:
            db.execute(
                "UPDATE student_dues SET pending_amount = ? WHERE student_id = ?",
                (int(pending_amount), int(student_id)),
            )

    db.commit()
    return redirect(url_for("admin_students"))


@app.post("/admin/students/bulk-update")
@admin_login_required
def admin_students_bulk_update():
    raw_ids = request.form.getlist("student_ids")

    student_ids: list[int] = []
    for x in raw_ids:
        try:
            student_ids.append(int(x))
        except Exception:
            continue
    if not student_ids:
        return redirect(url_for("admin_students"))

    def to_int(val: str) -> int | None:
        try:
            return int(val)
        except Exception:
            return None

    year = (request.form.get("year") or "").strip()
    sem = (request.form.get("sem") or "").strip()
    schedule_id = (request.form.get("schedule_id") or "").strip()
    status = (request.form.get("status") or "").strip()
    section = (request.form.get("section") or "").strip()

    year_i = to_int(year)
    sem_i = to_int(sem)
    schedule_i = to_int(schedule_id)

    db = get_db()
    cols = {row[1] for row in db.execute("PRAGMA table_info(students)").fetchall()}

    q_marks = ",".join(["?"] * len(student_ids))

    student_updates: list[tuple[str, int | None]] = []
    if year_i is not None:
        student_updates.append(("year", year_i))
    if sem_i is not None:
        student_updates.append(("sem", sem_i))
    if "schedule_id" in cols and schedule_i is not None:
        student_updates.append(("schedule_id", schedule_i or None))

    if student_updates:
        set_sql = ", ".join([f"{k} = ?" for k, _ in student_updates])
        db.execute(
            f"UPDATE students SET {set_sql} WHERE id IN ({q_marks})",
            [v for _, v in student_updates] + student_ids,
        )

    prof_cols = {row[1] for row in db.execute("PRAGMA table_info(student_profile)").fetchall()}
    prof_updates: list[tuple[str, str]] = []
    if "status" in prof_cols and status:
        prof_updates.append(("status", status))
    if "section" in prof_cols and section:
        prof_updates.append(("section", section))
    if prof_updates:
        set_sql = ", ".join([f"{k} = ?" for k, _ in prof_updates])
        db.execute(
            f"UPDATE student_profile SET {set_sql} WHERE student_id IN ({q_marks})",
            [v for _, v in prof_updates] + student_ids,
        )

    db.commit()
    return redirect(url_for("admin_students"))


@app.post("/admin/students/<int:student_id>/delete")
@admin_login_required
def admin_student_delete(student_id: int):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (int(student_id),)).fetchone()
    if not student:
        return redirect(url_for("admin_students"))

    # Remove vault files from disk first
    vault_files = db.execute(
        "SELECT stored_path FROM vault_files WHERE student_id = ?",
        (int(student_id),),
    ).fetchall()
    for f in vault_files:
        stored = (f["stored_path"] or "").strip()
        if stored.startswith("vault/"):
            abs_path = Path(__file__).with_name("uploads") / stored
            try:
                if abs_path.exists() and abs_path.is_file():
                    abs_path.unlink()
            except Exception:
                pass

    # Attempt to clean the whole vault directory for this student
    try:
        student_vault_dir = VAULT_UPLOAD_DIR / str(int(student_id))
        if student_vault_dir.exists() and student_vault_dir.is_dir():
            for root, dirs, files in os.walk(str(student_vault_dir), topdown=False):
                for name in files:
                    try:
                        Path(root, name).unlink()
                    except Exception:
                        pass
                for name in dirs:
                    try:
                        Path(root, name).rmdir()
                    except Exception:
                        pass
            try:
                student_vault_dir.rmdir()
            except Exception:
                pass
    except Exception:
        pass

    # Delete dependent rows (order matters due to foreign keys)
    db.execute(
        "DELETE FROM admit_card_subjects WHERE admit_card_id IN (SELECT id FROM admit_cards WHERE student_id = ?)",
        (int(student_id),),
    )
    db.execute("DELETE FROM admit_cards WHERE student_id = ?", (int(student_id),))

    db.execute(
        "DELETE FROM semester_result_courses WHERE result_id IN (SELECT id FROM semester_results WHERE student_id = ?)",
        (int(student_id),),
    )
    db.execute("DELETE FROM semester_results WHERE student_id = ?", (int(student_id),))

    db.execute("DELETE FROM student_subject_enrollments WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM student_programs WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM exam_form_submissions WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM attendance_heatmap WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM vault_files WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM vault_folders WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM student_dues WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM student_profile WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM student_details WHERE student_id = ?", (int(student_id),))
    db.execute("DELETE FROM students WHERE id = ?", (int(student_id),))

    db.commit()
    return redirect(url_for("admin_students"))


@app.post("/admin/teachers/new")
@admin_login_required
def admin_teachers_create():
    name = (request.form.get("name") or "").strip()
    designation = (request.form.get("designation") or "").strip()
    department = (request.form.get("department") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    phone = (request.form.get("phone") or "").strip() or None
    if not name or not designation or not department:
        db = get_db()
        teachers = db.execute("SELECT * FROM teachers ORDER BY name ASC").fetchall()
        return render_template(
            "admin_teachers.html",
            page_title="Teachers",
            page_subtitle="Manage faculty list",
            active_page="admin_teachers",
            teachers=teachers,
            error="Please fill all required teacher fields.",
        )
    db = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO teachers (name, designation, department, email, phone, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, designation, department, email, phone, now),
    )
    db.commit()
    return redirect(url_for("admin_teachers"))


@app.post("/admin/teachers/<int:teacher_id>/delete")
@admin_login_required
def admin_teachers_delete(teacher_id: int):
    db = get_db()
    db.execute("DELETE FROM teachers WHERE id = ?", (int(teacher_id),))
    db.commit()
    return redirect(url_for("admin_teachers"))


@app.get("/admin/news")
@admin_login_required
def admin_news_list():
    db = get_db()
    posts = db.execute(
        "SELECT * FROM news_posts ORDER BY datetime(date_time) DESC"
    ).fetchall()
    return render_template(
        "admin_news_list.html",
        page_title="Manage News",
        page_subtitle="Create, edit or delete posts",
        active_page="admin_news",
        posts=posts,
    )


@app.get("/admin/news/new")
@admin_login_required
def admin_news_new():
    return render_template(
        "admin_news_form.html",
        page_title="New News Post",
        page_subtitle="Publish an announcement",
        active_page="admin_news",
        post=None,
        error=None,
    )


@app.post("/admin/news/new")
@admin_login_required
def admin_news_create():
    priority = (request.form.get("priority") or "").strip().upper() or "NORMAL"
    heading = (request.form.get("heading") or "").strip()
    body_html_raw = (request.form.get("body_html") or "").strip()
    body_plain = (request.form.get("body") or "").strip()
    sender = (request.form.get("sender") or "").strip()
    news_type = (request.form.get("news_type") or "").strip()
    tags = (request.form.get("tags") or "").strip()

    body_is_html = 1 if body_html_raw else 0
    body = sanitize_news_html(body_html_raw) if body_is_html else body_plain

    if not heading or not body or not sender or not news_type:
        return render_template(
            "admin_news_form.html",
            page_title="New News Post",
            page_subtitle="Publish an announcement",
            active_page="admin_news",
            post=None,
            error="Please fill all required fields.",
        )
    db = get_db()
    now = datetime.now().isoformat(timespec="seconds")

    attachment = save_news_attachment(request.files.get("attachment"))
    attachment_path = attachment[0] if attachment else None
    attachment_name = attachment[1] if attachment else None
    attachment_mime = attachment[2] if attachment else None
    db.execute(
        """
        INSERT INTO news_posts (
            priority, date_time, heading, body, sender, news_type, tags,
            body_is_html, attachment_path, attachment_name, attachment_mime
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            priority,
            now,
            heading,
            body,
            sender,
            news_type,
            tags,
            int(body_is_html),
            attachment_path,
            attachment_name,
            attachment_mime,
        ),
    )
    db.commit()
    return redirect(url_for("admin_news_list"))


@app.get("/admin/news/<int:post_id>/edit")
@admin_login_required
def admin_news_edit(post_id: int):
    db = get_db()
    post = db.execute("SELECT * FROM news_posts WHERE id = ?", (int(post_id),)).fetchone()
    if not post:
        return redirect(url_for("admin_news_list"))
    return render_template(
        "admin_news_form.html",
        page_title="Edit News Post",
        page_subtitle="Update announcement",
        active_page="admin_news",
        post=post,
        error=None,
    )


@app.post("/admin/news/<int:post_id>/edit")
@admin_login_required
def admin_news_update(post_id: int):
    priority = (request.form.get("priority") or "").strip().upper() or "NORMAL"
    heading = (request.form.get("heading") or "").strip()
    body_html_raw = (request.form.get("body_html") or "").strip()
    body_plain = (request.form.get("body") or "").strip()
    sender = (request.form.get("sender") or "").strip()
    news_type = (request.form.get("news_type") or "").strip()
    tags = (request.form.get("tags") or "").strip()

    body_is_html = 1 if body_html_raw else 0
    body = sanitize_news_html(body_html_raw) if body_is_html else body_plain

    if not heading or not body or not sender or not news_type:
        db = get_db()
        post = db.execute("SELECT * FROM news_posts WHERE id = ?", (int(post_id),)).fetchone()
        return render_template(
            "admin_news_form.html",
            page_title="Edit News Post",
            page_subtitle="Update announcement",
            active_page="admin_news",
            post=post,
            error="Please fill all required fields.",
        )
    db = get_db()

    attachment = save_news_attachment(request.files.get("attachment"))
    attachment_path = attachment[0] if attachment else None
    attachment_name = attachment[1] if attachment else None
    attachment_mime = attachment[2] if attachment else None

    if attachment:
        db.execute(
            """
            UPDATE news_posts
            SET priority = ?, heading = ?, body = ?, sender = ?, news_type = ?, tags = ?,
                body_is_html = ?, attachment_path = ?, attachment_name = ?, attachment_mime = ?
            WHERE id = ?
            """,
            (
                priority,
                heading,
                body,
                sender,
                news_type,
                tags,
                int(body_is_html),
                attachment_path,
                attachment_name,
                attachment_mime,
                int(post_id),
            ),
        )
    else:
        db.execute(
            """
            UPDATE news_posts
            SET priority = ?, heading = ?, body = ?, sender = ?, news_type = ?, tags = ?, body_is_html = ?
            WHERE id = ?
            """,
            (
                priority,
                heading,
                body,
                sender,
                news_type,
                tags,
                int(body_is_html),
                int(post_id),
            ),
        )
    db.commit()
    return redirect(url_for("admin_news_list"))


@app.post("/admin/news/<int:post_id>/delete")
@admin_login_required
def admin_news_delete(post_id: int):
    db = get_db()
    db.execute("DELETE FROM news_posts WHERE id = ?", (int(post_id),))
    db.commit()
    return redirect(url_for("admin_news_list"))


@app.get("/admin/exam-forms")
@admin_login_required
def admin_exam_forms():
    db = get_db()

    forms = db.execute("SELECT * FROM exam_forms ORDER BY id DESC").fetchall()
    resolved_forms = []
    for f in forms:
        is_open = is_exam_form_open(f["open_from"], f["open_to"]) if ("open_from" in f.keys()) else False
        resolved_forms.append({**dict(f), "is_open": is_open, "computed_status": "OPEN" if is_open else "CLOSED"})

    openings = db.execute("SELECT * FROM admit_card_openings ORDER BY id DESC").fetchall()
    resolved_openings = []
    for o in openings:
        is_open = is_exam_form_open(o["open_from"], o["open_to"]) if ("open_from" in o.keys()) else False
        resolved_openings.append({**dict(o), "is_open": is_open, "computed_status": "OPEN" if is_open else "CLOSED"})
    return render_template(
        "admin_exam_forms.html",
        page_title="Manage Exam Forms",
        page_subtitle="Open/close exam forms",
        active_page="admin_exam_forms",
        forms=resolved_forms,
        admit_openings=resolved_openings,
    )


@app.post("/admin/exam-forms/<int:form_id>/delete")
@admin_login_required
def admin_exam_form_delete(form_id: int):
    db = get_db()
    db.execute("DELETE FROM exam_forms WHERE id = ?", (int(form_id),))
    db.commit()
    return redirect(url_for("admin_exam_forms"))


@app.post("/admin/admit-card-openings/<int:opening_id>/delete")
@admin_login_required
def admin_admit_card_opening_delete(opening_id: int):
    db = get_db()
    db.execute("DELETE FROM admit_card_openings WHERE id = ?", (int(opening_id),))
    db.commit()
    return redirect(get_safe_next_url("admin_admit_card_openings"))


@app.get("/admin/exam-forms/new")
@admin_login_required
def admin_exam_form_new():
    return render_template(
        "admin_exam_form_form.html",
        page_title="New Exam Form",
        page_subtitle="Create a new exam application form",
        active_page="admin_exam_forms",
        form=None,
        error=None,
    )


@app.get("/admin/admit-card-openings")
@admin_login_required
def admin_admit_card_openings():
    db = get_db()
    openings = db.execute("SELECT * FROM admit_card_openings ORDER BY id DESC").fetchall()
    resolved_openings = []
    for o in openings:
        is_open = is_exam_form_open(o["open_from"], o["open_to"]) if ("open_from" in o.keys()) else False
        resolved_openings.append({**dict(o), "is_open": is_open, "computed_status": "OPEN" if is_open else "CLOSED"})
    return render_template(
        "admin_admit_card_openings.html",
        page_title="Admit Card Openings",
        page_subtitle="Manage admit card link windows",
        active_page="admin_exam_forms",
        openings=resolved_openings,
    )


@app.get("/admin/admit-card-openings/new")
@admin_login_required
def admin_admit_card_opening_new():
    return render_template(
        "admin_admit_card_opening_form.html",
        page_title="New Admit Card Opening",
        page_subtitle="Create a new admit card link window",
        active_page="admin_exam_forms",
        error=None,
    )


@app.post("/admin/admit-card-openings/new")
@admin_login_required
def admin_admit_card_opening_create():
    title = (request.form.get("title") or "").strip()
    semester_label = (request.form.get("semester_label") or "").strip()
    open_from = (request.form.get("open_from") or "").strip() or None
    open_to = (request.form.get("open_to") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    program = (request.form.get("program") or "").strip() or None
    department = (request.form.get("department") or "").strip() or None
    admit_card_url = (request.form.get("admit_card_url") or "").strip() or None
    roll_placeholder = (request.form.get("roll_placeholder") or "").strip() or None

    if not title or not semester_label or not admit_card_url or not open_from or not open_to:
        return render_template(
            "admin_admit_card_opening_form.html",
            page_title="New Admit Card Opening",
            page_subtitle="Create a new admit card link window",
            active_page="admin_exam_forms",
            error="Title, semester, link, open from and open to are required.",
        )

    db = get_db()
    db.execute(
        """
        INSERT INTO admit_card_openings (
            title, semester_label, open_from, open_to, note,
            program, department, admit_card_url, roll_placeholder
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            semester_label,
            open_from,
            open_to,
            note,
            program,
            department,
            admit_card_url,
            roll_placeholder,
        ),
    )
    db.commit()
    return redirect(get_safe_next_url("admin_admit_card_openings"))


@app.post("/admin/exam-forms/new")
@admin_login_required
def admin_exam_form_create():
    title = (request.form.get("title") or "").strip()
    semester_label = (request.form.get("semester_label") or "").strip()
    open_from = (request.form.get("open_from") or "").strip() or None
    open_to = (request.form.get("open_to") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    program = (request.form.get("program") or "").strip() or None
    department = (request.form.get("department") or "").strip() or None
    apply_url = (request.form.get("apply_url") or "").strip() or None
    apply_roll_placeholder = (request.form.get("apply_roll_placeholder") or "").strip() or None
    if not title or not semester_label or not apply_url or not open_from or not open_to:
        return render_template(
            "admin_exam_form_form.html",
            page_title="New Exam Form",
            page_subtitle="Create a new exam application form",
            active_page="admin_exam_forms",
            form=None,
            error="Title, semester, link, open from and open to are required.",
        )

    derived_status = "OPEN" if is_exam_form_open(open_from, open_to) else "CLOSED"

    db = get_db()
    db.execute(
        """
        INSERT INTO exam_forms (
            title, semester_label, status, open_from, open_to, fee, note,
            apply_url, admit_card_url, apply_roll_placeholder, admit_roll_placeholder,
            program, department
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            semester_label,
            derived_status,
            open_from,
            open_to,
            None,
            note,
            apply_url,
            None,
            apply_roll_placeholder,
            None,
            program,
            department,
        ),
    )
    db.commit()
    return redirect(url_for("admin_exam_forms"))


@app.get("/admin/exam-forms/<int:form_id>/submissions")
@admin_login_required
def admin_exam_form_submissions(form_id: int):
    db = get_db()
    form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
    if not form:
        return redirect(url_for("admin_exam_forms"))
    submissions = db.execute(
        """
        SELECT s.*
        FROM exam_form_submissions s
        WHERE s.form_id = ?
        ORDER BY datetime(s.submitted_at) DESC
        """,
        (int(form_id),),
    ).fetchall()
    return render_template(
        "admin_exam_form_submissions.html",
        page_title="Exam Form Submissions",
        page_subtitle=f"Responses for: {form['title']}",
        active_page="admin_exam_forms",
        form=form,
        submissions=submissions,
    )


@app.post("/admin/exam-forms/<int:form_id>/toggle")
@admin_login_required
def admin_exam_form_toggle(form_id: int):
    db = get_db()
    form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
    if not form:
        return redirect(url_for("admin_exam_forms"))
    new_status = "CLOSED" if (form["status"] or "").upper() == "OPEN" else "OPEN"
    db.execute("UPDATE exam_forms SET status = ? WHERE id = ?", (new_status, int(form_id)))
    db.commit()
    return redirect(url_for("admin_exam_forms"))


@app.get("/admin/exam-forms/<int:form_id>/edit")
@admin_login_required
def admin_exam_form_edit(form_id: int):
    db = get_db()
    form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
    if not form:
        return redirect(url_for("admin_exam_forms"))
    return render_template(
        "admin_exam_form_form.html",
        page_title="Edit Exam Form",
        page_subtitle="Update exam application form",
        active_page="admin_exam_forms",
        form=form,
        error=None,
    )


@app.post("/admin/exam-forms/<int:form_id>/edit")
@admin_login_required
def admin_exam_form_update(form_id: int):
    title = (request.form.get("title") or "").strip()
    semester_label = (request.form.get("semester_label") or "").strip()
    open_from = (request.form.get("open_from") or "").strip() or None
    open_to = (request.form.get("open_to") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    program = (request.form.get("program") or "").strip() or None
    department = (request.form.get("department") or "").strip() or None
    apply_url = (request.form.get("apply_url") or "").strip() or None
    apply_roll_placeholder = (request.form.get("apply_roll_placeholder") or "").strip() or None

    if not title or not semester_label or not apply_url or not open_from or not open_to:
        db = get_db()
        form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
        return render_template(
            "admin_exam_form_form.html",
            page_title="Edit Exam Form",
            page_subtitle="Update exam application form",
            active_page="admin_exam_forms",
            form=form,
            error="Title, semester, link, open from and open to are required.",
        )

    derived_status = "OPEN" if is_exam_form_open(open_from, open_to) else "CLOSED"

    db = get_db()
    db.execute(
        """
        UPDATE exam_forms
        SET title = ?, semester_label = ?, status = ?, open_from = ?, open_to = ?, note = ?,
            apply_url = ?, apply_roll_placeholder = ?, program = ?, department = ?
        WHERE id = ?
        """,
        (
            title,
            semester_label,
            derived_status,
            open_from,
            open_to,
            note,
            apply_url,
            apply_roll_placeholder,
            program,
            department,
            int(form_id),
        ),
    )
    db.commit()
    return redirect(url_for("admin_exam_forms"))


@app.get("/register")
def register():
    if get_current_student_id() is not None:
        return redirect(url_for("dashboard"))
    db = get_db()
    groups = db.execute("SELECT * FROM schedule_groups ORDER BY id ASC").fetchall()
    return render_template("register.html", error=None, schedule_groups=groups)


@app.post("/register")
def register_post():
    form = {k: (request.form.get(k) or "").strip() for k in request.form.keys()}
    required = [
        "name",
        "roll_no",
        "email",
        "phone",
        "guardian",
        "residential_status",
        "program",
        "year",
        "sem",
        "schedule_id",
        "password",
        "confirm_password",
        "father_name",
        "gender",
        "category",
        "address",
        "batch",
        "department",
        "section",
        "emergency_contact_name",
        "emergency_contact_relation",
        "emergency_contact_phone",
    ]
    missing = [k for k in required if not form.get(k)]
    if missing:
        return render_template("register.html", error="Please fill all required fields.")

    phone_digits = re.sub(r"\D+", "", form.get("phone", ""))[-10:]
    emergency_digits = re.sub(r"\D+", "", form.get("emergency_contact_phone", ""))[-10:]

    if not re.fullmatch(r"[6-9]\d{9}", phone_digits):
        return render_template(
            "register.html",
            error="Please enter a valid 10-digit mobile number (starting with 6-9).",
        )
    if not re.fullmatch(r"[6-9]\d{9}", emergency_digits):
        return render_template(
            "register.html",
            error="Please enter a valid 10-digit emergency mobile number (starting with 6-9).",
        )

    form["phone"] = phone_digits
    form["emergency_contact_phone"] = emergency_digits

    if form["password"] != form["confirm_password"]:
        return render_template("register.html", error="Passwords do not match.")

    try:
        year = int(form["year"])
        sem = int(form["sem"])
    except Exception:
        return render_template("register.html", error="Year and semester must be numbers.")

    try:
        schedule_id = int(form["schedule_id"])
    except Exception:
        return render_template("register.html", error="Please select a weekly schedule.")

    attendance_percent = form.get("attendance_percent") or ""
    try:
        attendance_percent_int = int(attendance_percent) if attendance_percent else 0
    except Exception:
        attendance_percent_int = 0

    db = get_db()
    ensure_students_password_column(db)

    exists = db.execute(
        "SELECT id FROM students WHERE roll_no = ?",
        (form["roll_no"],),
    ).fetchone()
    if exists is not None:
        return render_template("register.html", error="Roll number already exists. Please login instead.")

    password_hash = generate_password_hash(form["password"])
    db.execute(
        """
        INSERT INTO students (
            name, roll_no, email, phone, guardian, residential_status,
            program, year, sem, attendance_percent, next_class, password_hash, schedule_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            form["name"],
            form["roll_no"],
            form["email"],
            form["phone"],
            form["guardian"],
            form["residential_status"],
            form["program"],
            year,
            sem,
            attendance_percent_int,
            "",
            password_hash,
            int(schedule_id),
        ),
    )
    student_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    exam_roll_number = form.get("exam_roll_number") or form["roll_no"]
    db.execute(
        """
        INSERT INTO student_details (student_id, father_name, gender, category, address, exam_roll_number)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            form["father_name"],
            form["gender"],
            form["category"],
            form["address"],
            exam_roll_number,
        ),
    )

    db.execute(
        """
        INSERT INTO student_profile (
            student_id, status, batch, department, section, address,
            emergency_contact_name, emergency_contact_relation, emergency_contact_phone
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            form.get("status") or "Active",
            form["batch"],
            form["department"],
            form["section"],
            form["address"],
            form["emergency_contact_name"],
            form["emergency_contact_relation"],
            form["emergency_contact_phone"],
        ),
    )

    db.execute(
        "INSERT INTO student_dues (student_id, pending_amount) VALUES (?, ?)",
        (student_id, 0),
    )

    program_row = db.execute("SELECT id FROM programs ORDER BY id ASC LIMIT 1").fetchone()
    program_id = int(program_row[0]) if program_row else 1
    db.execute(
        "INSERT INTO student_programs (student_id, program_id) VALUES (?, ?)",
        (student_id, program_id),
    )

    seed_attendance_for_student(db, student_id)

    db.commit()
    session["student_id"] = student_id
    return redirect(url_for("dashboard"))


@app.get("/")
@login_required
def dashboard():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    folders = db.execute(
        "SELECT * FROM vault_folders WHERE student_id = ? ORDER BY datetime(created_at) DESC",
        (sid,),
    ).fetchall()
    files = db.execute(
        """
        SELECT vf.*, vfo.name AS folder_name
        FROM vault_files vf
        JOIN vault_folders vfo ON vfo.id = vf.folder_id
        WHERE vf.student_id = ?
        ORDER BY datetime(vf.uploaded_at) DESC
        LIMIT 12
        """,
        (sid,),
    ).fetchall()

    immediate_attention = db.execute(
        """
        SELECT * FROM news_posts
        WHERE priority IN ('URGENT','HIGH')
        ORDER BY datetime(date_time) DESC
        LIMIT 2
        """
    ).fetchall()

    announcements = db.execute(
        """
        SELECT * FROM news_posts
        WHERE datetime(date_time) >= datetime('now', '-7 days')
        ORDER BY datetime(date_time) DESC
        LIMIT 6
        """
    ).fetchall()
    return render_template(
        "dashboard.html",
        page_title="Dashboard",
        page_subtitle=f"Welcome back, {student['name'].split(' ')[0]}" if student else "Welcome back",
        active_page="dashboard",
        student=student,
        vault_folders=folders,
        vault_files=files,
        immediate_attention=immediate_attention,
        announcements=announcements,
    )


@app.get("/teachers")
@login_required
def teachers():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    filters = {
        "q": (request.args.get("q") or "").strip(),
        "department": (request.args.get("department") or "").strip(),
        "designation": (request.args.get("designation") or "").strip(),
    }

    rows = db.execute("SELECT * FROM teachers ORDER BY name ASC").fetchall()
    q = filters["q"].lower()
    f_department = filters["department"].lower()
    f_designation = filters["designation"].lower()

    resolved = []
    for t in rows:
        t_dict = dict(t)
        hay = " ".join(
            [
                str(t_dict.get("name") or ""),
                str(t_dict.get("designation") or ""),
                str(t_dict.get("department") or ""),
                str(t_dict.get("email") or ""),
                str(t_dict.get("phone") or ""),
            ]
        ).lower()
        if q and q not in hay:
            continue
        if f_department and (str(t_dict.get("department") or "").lower() != f_department):
            continue
        if f_designation and (str(t_dict.get("designation") or "").lower() != f_designation):
            continue
        resolved.append(t)

    return render_template(
        "teachers.html",
        page_title="Teachers",
        page_subtitle="Faculty directory",
        active_page="teachers",
        student=student,
        teachers=resolved,
        filters=filters,
    )


@app.post("/vault/folders")
@login_required
def vault_folder_create():
    sid = get_current_student_id()
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(get_safe_next_url("dashboard"))

    db = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    try:
        db.execute(
            "INSERT INTO vault_folders (student_id, name, created_at) VALUES (?, ?, ?)",
            (sid, name, now),
        )
        db.commit()
    except sqlite3.IntegrityError:
        pass
    return redirect(get_safe_next_url("dashboard"))


@app.post("/vault/folders/<int:folder_id>/delete")
@login_required
def vault_folder_delete(folder_id: int):
    sid = get_current_student_id()
    db = get_db()

    files = db.execute(
        "SELECT stored_path FROM vault_files WHERE folder_id = ? AND student_id = ?",
        (int(folder_id), sid),
    ).fetchall()
    for row in files:
        delete_vault_physical_file(row["stored_path"])

    db.execute(
        "DELETE FROM vault_folders WHERE id = ? AND student_id = ?",
        (int(folder_id), sid),
    )
    db.commit()
    return redirect(get_safe_next_url("dashboard"))


@app.post("/vault/files")
@login_required
def vault_file_upload():
    sid = get_current_student_id()
    try:
        folder_id = int(request.form.get("folder_id") or "0")
    except Exception:
        folder_id = 0
    upload = request.files.get("file")
    if not folder_id or upload is None or not (upload.filename or "").strip():
        return redirect(get_safe_next_url("dashboard"))

    db = get_db()
    folder = db.execute(
        "SELECT * FROM vault_folders WHERE id = ? AND student_id = ?",
        (folder_id, sid),
    ).fetchone()
    if not folder:
        return redirect(get_safe_next_url("dashboard"))

    saved = save_vault_file(upload, int(sid))
    if saved is None:
        return redirect(get_safe_next_url("dashboard"))
    rel_path, original, mime, size_bytes = saved
    now = datetime.utcnow().isoformat(timespec="seconds")

    db.execute(
        """
        INSERT INTO vault_files (student_id, folder_id, original_name, stored_path, mime, size_bytes, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (sid, folder_id, original, rel_path, mime, size_bytes, now),
    )
    db.commit()
    return redirect(get_safe_next_url("dashboard"))


@app.get("/vault/files/<int:file_id>/download")
@login_required
def vault_file_download(file_id: int):
    sid = get_current_student_id()
    db = get_db()
    f = db.execute(
        "SELECT * FROM vault_files WHERE id = ? AND student_id = ?",
        (int(file_id), sid),
    ).fetchone()
    if not f:
        abort(404)

    stored = (f["stored_path"] or "").strip()
    if not stored.startswith("vault/"):
        abort(404)
    abs_path = Path(__file__).with_name("uploads") / stored
    if not abs_path.exists() or not abs_path.is_file():
        abort(404)

    return send_file(
        str(abs_path),
        as_attachment=True,
        download_name=f["original_name"],
        mimetype=(f["mime"] or None),
    )


@app.post("/vault/files/<int:file_id>/delete")
@login_required
def vault_file_delete(file_id: int):
    sid = get_current_student_id()
    db = get_db()
    f = db.execute(
        "SELECT * FROM vault_files WHERE id = ? AND student_id = ?",
        (int(file_id), sid),
    ).fetchone()
    if not f:
        return redirect(get_safe_next_url("dashboard"))

    delete_vault_physical_file(f["stored_path"])

    db.execute("DELETE FROM vault_files WHERE id = ? AND student_id = ?", (int(file_id), sid))
    db.commit()
    return redirect(get_safe_next_url("dashboard"))


@app.post("/vault/files/bulk-delete")
@login_required
def vault_files_bulk_delete():
    sid = get_current_student_id()
    raw_ids = request.form.getlist("file_ids")
    file_ids: list[int] = []
    for x in raw_ids:
        try:
            file_ids.append(int(x))
        except Exception:
            continue
    if not file_ids:
        return redirect(get_safe_next_url("vault"))

    db = get_db()
    q_marks = ",".join(["?"] * len(file_ids))
    rows = db.execute(
        f"SELECT id, stored_path FROM vault_files WHERE student_id = ? AND id IN ({q_marks})",
        [sid, *file_ids],
    ).fetchall()
    for r in rows:
        delete_vault_physical_file(r["stored_path"])

    db.execute(
        f"DELETE FROM vault_files WHERE student_id = ? AND id IN ({q_marks})",
        [sid, *file_ids],
    )
    db.commit()
    return redirect(get_safe_next_url("vault"))


@app.post("/vault/files/bulk-move")
@login_required
def vault_files_bulk_move():
    sid = get_current_student_id()
    raw_ids = request.form.getlist("file_ids")
    try:
        target_folder_id = int(request.form.get("target_folder_id") or "0")
    except Exception:
        target_folder_id = 0

    file_ids: list[int] = []
    for x in raw_ids:
        try:
            file_ids.append(int(x))
        except Exception:
            continue
    if not file_ids or not target_folder_id:
        return redirect(get_safe_next_url("vault"))

    db = get_db()
    target = db.execute(
        "SELECT id FROM vault_folders WHERE id = ? AND student_id = ?",
        (int(target_folder_id), sid),
    ).fetchone()
    if not target:
        return redirect(get_safe_next_url("vault"))

    q_marks = ",".join(["?"] * len(file_ids))
    db.execute(
        f"UPDATE vault_files SET folder_id = ? WHERE student_id = ? AND id IN ({q_marks})",
        [int(target_folder_id), sid, *file_ids],
    )
    db.commit()
    return redirect(get_safe_next_url("vault"))


@app.post("/vault/files/bulk-copy")
@login_required
def vault_files_bulk_copy():
    sid = get_current_student_id()
    raw_ids = request.form.getlist("file_ids")
    try:
        target_folder_id = int(request.form.get("target_folder_id") or "0")
    except Exception:
        target_folder_id = 0

    file_ids: list[int] = []
    for x in raw_ids:
        try:
            file_ids.append(int(x))
        except Exception:
            continue
    if not file_ids or not target_folder_id:
        return redirect(get_safe_next_url("vault"))

    db = get_db()
    target = db.execute(
        "SELECT id FROM vault_folders WHERE id = ? AND student_id = ?",
        (int(target_folder_id), sid),
    ).fetchone()
    if not target:
        return redirect(get_safe_next_url("vault"))

    q_marks = ",".join(["?"] * len(file_ids))
    rows = db.execute(
        f"SELECT * FROM vault_files WHERE student_id = ? AND id IN ({q_marks})",
        [sid, *file_ids],
    ).fetchall()

    now = datetime.utcnow().isoformat(timespec="seconds")
    for f in rows:
        src_abs = get_vault_abs_path(f["stored_path"])
        if src_abs is None or not src_abs.exists() or not src_abs.is_file():
            continue

        original_name = (f["original_name"] or "").strip()
        safe = secure_filename(original_name)
        if not safe:
            safe = f"file_{f['id']}"
        unique = f"{uuid.uuid4().hex}_{safe}"
        dst_abs = VAULT_UPLOAD_DIR / str(int(sid)) / unique
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(str(src_abs), str(dst_abs))
        except Exception:
            continue

        rel_path = f"vault/{int(sid)}/{unique}"
        size_bytes = int(dst_abs.stat().st_size) if dst_abs.exists() else int(f["size_bytes"] or 0)
        db.execute(
            """
            INSERT INTO vault_files (student_id, folder_id, original_name, stored_path, mime, size_bytes, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid,
                int(target_folder_id),
                original_name or safe,
                rel_path,
                (f["mime"] or None),
                size_bytes,
                now,
            ),
        )

    db.commit()
    return redirect(get_safe_next_url("vault"))


@app.get("/vault")
@login_required
def vault():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    folders = db.execute(
        "SELECT * FROM vault_folders WHERE student_id = ? ORDER BY datetime(created_at) DESC",
        (sid,),
    ).fetchall()

    selected_folder_id = None
    try:
        selected_folder_id = int(request.args.get("folder_id") or 0) or None
    except Exception:
        selected_folder_id = None

    if selected_folder_id is None and folders:
        selected_folder_id = int(folders[0]["id"])

    folder = None
    files = []
    if selected_folder_id is not None:
        folder = db.execute(
            "SELECT * FROM vault_folders WHERE id = ? AND student_id = ?",
            (int(selected_folder_id), sid),
        ).fetchone()
        if folder:
            files = db.execute(
                """
                SELECT vf.*, vfo.name AS folder_name
                FROM vault_files vf
                JOIN vault_folders vfo ON vfo.id = vf.folder_id
                WHERE vf.student_id = ? AND vf.folder_id = ?
                ORDER BY datetime(vf.uploaded_at) DESC
                """,
                (sid, int(selected_folder_id)),
            ).fetchall()

    return render_template(
        "vault.html",
        page_title="Vault",
        page_subtitle="Your private documents",
        active_page="vault",
        student=student,
        vault_folders=folders,
        selected_folder=folder,
        vault_files=files,
    )


@app.get("/news")
@login_required
def news():
    db = get_db()

    filters = {
        "priority": (request.args.get("priority") or "").strip(),
        "news_type": (request.args.get("news_type") or "").strip(),
        "sender": (request.args.get("sender") or "").strip(),
        "tag": (request.args.get("tag") or "").strip(),
        "q": (request.args.get("q") or "").strip(),
        "from_dt": (request.args.get("from") or "").strip(),
        "to_dt": (request.args.get("to") or "").strip(),
    }

    where = []
    params = []

    if filters["priority"]:
        where.append("priority = ?")
        params.append(filters["priority"])
    if filters["news_type"]:
        where.append("news_type = ?")
        params.append(filters["news_type"])
    if filters["sender"]:
        where.append("sender = ?")
        params.append(filters["sender"])
    if filters["tag"]:
        where.append("tags LIKE ?")
        params.append(f"%{filters['tag']}%")
    if filters["from_dt"]:
        where.append("datetime(date_time) >= datetime(?)")
        params.append(filters["from_dt"])
    if filters["to_dt"]:
        where.append("datetime(date_time) <= datetime(?)")
        params.append(filters["to_dt"])
    if filters["q"]:
        where.append("(heading LIKE ? OR body LIKE ? OR sender LIKE ? OR tags LIKE ?)")
        like = f"%{filters['q']}%"
        params.extend([like, like, like, like])

    sql = "SELECT * FROM news_posts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY datetime(date_time) DESC"

    posts = db.execute(sql, params).fetchall()

    priorities = [r[0] for r in db.execute("SELECT DISTINCT priority FROM news_posts ORDER BY priority").fetchall()]
    senders = [r[0] for r in db.execute("SELECT DISTINCT sender FROM news_posts ORDER BY sender").fetchall()]
    news_types = [r[0] for r in db.execute("SELECT DISTINCT news_type FROM news_posts ORDER BY news_type").fetchall()]
    return render_template(
        "news.html",
        page_title="News & Feed",
        page_subtitle="Latest from Institute",
        active_page="news",
        posts=posts,
        priorities=priorities,
        senders=senders,
        news_types=news_types,
        filters=filters,
    )


@app.get("/schedules")
@login_required
def schedules():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    schedule_id = int(student["schedule_id"] or 1) if student and ("schedule_id" in student.keys()) else 1

    events = db.execute(
        "SELECT * FROM schedules WHERE schedule_id = ? ORDER BY datetime(start_at) ASC",
        (int(schedule_id),),
    ).fetchall()

    timetable_rows = db.execute(
        """
        SELECT * FROM weekly_timetable
        WHERE schedule_id = ?
        ORDER BY day_of_week ASC, time(start_time) ASC
        """
        ,
        (int(schedule_id),)
    ).fetchall()
    timetable_by_day = {i: [] for i in range(7)}
    for row in timetable_rows:
        timetable_by_day[int(row["day_of_week"])].append(row)

    today = datetime.now()
    today_dow = today.weekday()
    month_start = f"{today.year:04d}-{today.month:02d}-01"
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = f"{today.year:04d}-{today.month:02d}-{last_day:02d}"
    month_items = db.execute(
        """
        SELECT * FROM calendar_items
        WHERE date(item_date) >= date(?) AND date(item_date) <= date(?)
        ORDER BY date(item_date) ASC
        """,
        (month_start, month_end),
    ).fetchall()

    month_schedule_events = db.execute(
        """
        SELECT * FROM schedules
        WHERE date(start_at) >= date(?) AND date(start_at) <= date(?)
          AND schedule_id = ?
        ORDER BY datetime(start_at) ASC
        """,
        (month_start, month_end, int(schedule_id)),
    ).fetchall()

    calendar_weeks = []
    cal = calendar.Calendar(firstweekday=0)
    for week in cal.monthdatescalendar(today.year, today.month):
        calendar_weeks.append(
            [
                {
                    "date": d.isoformat(),
                    "day": d.day,
                    "in_month": d.month == today.month,
                }
                for d in week
            ]
        )

    month_items_by_date = {}
    for m in month_items:
        key = m["item_date"]
        month_items_by_date.setdefault(key, []).append(
            {
                "type": m["item_type"],
                "title": m["title"],
                "description": m["description"],
            }
        )

    schedule_by_date = {}
    for e in month_schedule_events:
        key = str(e["start_at"])[:10]
        schedule_by_date.setdefault(key, []).append(
            {
                "title": e["title"],
                "location": e["location"],
                "start_at": e["start_at"],
                "end_at": e["end_at"],
            }
        )

    timetable_for_popup = {
        str(d): [
            {
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "subject": r["subject"],
                "room": r["room"],
                "instructor": r["instructor"],
            }
            for r in timetable_by_day[d]
        ]
        for d in timetable_by_day
    }

    return render_template(
        "schedules.html",
        page_title="Schedules",
        page_subtitle="Class & Exam Timetable",
        active_page="schedules",
        events=events,
        timetable_by_day=timetable_by_day,
        month_items=month_items,
        month_label=today.strftime("%B %Y"),
        today_dow=today_dow,
        today_date=today.date().isoformat(),
        calendar_weeks=calendar_weeks,
        month_items_by_date=month_items_by_date,
        schedule_by_date=schedule_by_date,
        timetable_for_popup=timetable_for_popup,
    )


@app.get("/library")
@login_required
def library():
    db = get_db()
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "tag": (request.args.get("tag") or "").strip(),
        "uploader": (request.args.get("uploader") or "").strip(),
    }

    where = []
    params = []
    if filters["uploader"]:
        where.append("uploader = ?")
        params.append(filters["uploader"])
    if filters["tag"]:
        where.append("tags LIKE ?")
        params.append(f"%{filters['tag']}%")
    if filters["q"]:
        where.append("(heading LIKE ? OR description LIKE ? OR uploader LIKE ? OR tags LIKE ?)")
        like = f"%{filters['q']}%"
        params.extend([like, like, like, like])

    sql = "SELECT * FROM library_resources"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY datetime(uploaded_at) DESC"
    resources = db.execute(sql, params).fetchall()

    uploaders = [
        r[0]
        for r in db.execute(
            "SELECT DISTINCT uploader FROM library_resources ORDER BY uploader"
        ).fetchall()
    ]
    return render_template(
        "library.html",
        page_title="Digital Library",
        page_subtitle="Books & Journals",
        active_page="library",
        resources=resources,
        uploaders=uploaders,
        filters=filters,
    )


@app.post("/library/resources/upload")
@login_required
def library_resource_upload():
    heading = (request.form.get("heading") or "").strip()
    description = (request.form.get("description") or "").strip()
    tags = (request.form.get("tags") or "").strip()
    uploader = (request.form.get("uploader") or "").strip()
    pdf_url = (request.form.get("pdf_url") or "").strip()
    pdf_file = request.files.get("pdf_file")

    if not heading or not description or not uploader:
        return redirect(url_for("library"))

    final_pdf_url = ""
    if pdf_file and pdf_file.filename:
        filename = secure_filename(pdf_file.filename)
        if not filename.lower().endswith(".pdf"):
            return redirect(url_for("library"))
        upload_dir = Path(app.root_path) / "static" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_name = f"{stamp}_{filename}"
        pdf_file.save(str(upload_dir / safe_name))
        final_pdf_url = f"uploads/{safe_name}"
    else:
        if not pdf_url:
            return redirect(url_for("library"))
        final_pdf_url = pdf_url

    db = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO library_resources (heading, description, pdf_url, uploader, uploaded_at, tags)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (heading, description, final_pdf_url, uploader, now, tags),
    )
    db.commit()
    return redirect(url_for("library"))


@app.get("/exams")
@login_required
def exams():
    db = get_db()
    forms = db.execute(
        "SELECT * FROM exam_forms ORDER BY id DESC"
    ).fetchall()

    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    details = db.execute("SELECT * FROM student_details WHERE student_id = ?", (sid,)).fetchone()
    student_program = db.execute("SELECT * FROM student_programs WHERE student_id = ?", (sid,)).fetchone()
    profile = db.execute("SELECT * FROM student_profile WHERE student_id = ?", (sid,)).fetchone()

    student_program_id_int: int | None = None
    if student_program and ("program_id" in student_program.keys()):
        try:
            student_program_id_int = int(student_program["program_id"])
        except Exception:
            student_program_id_int = None

    resolved_student_program = ""
    resolved_student_department = ""
    if student_program:
        try:
            program_row = db.execute(
                "SELECT * FROM programs WHERE id = ?",
                (int(student_program["program_id"]),),
            ).fetchone()
            if program_row:
                resolved_student_program = _norm_text(program_row.get("name") if hasattr(program_row, "get") else program_row["name"])
                resolved_student_department = _norm_text(program_row.get("branch") if hasattr(program_row, "get") else program_row["branch"])
        except Exception:
            resolved_student_program = ""
            resolved_student_department = ""

    if not resolved_student_program:
        resolved_student_program = _norm_text(student["program"] if student and ("program" in student.keys()) else "")

    if profile and ("department" in profile.keys()):
        resolved_student_department = _norm_text(profile["department"])
    elif not resolved_student_department:
        resolved_student_department = _norm_text("")

    exam_roll_number = ""
    if student and details:
        exam_roll_number = (details["exam_roll_number"] or "").strip() or (student["roll_no"] or "").strip()
    elif student:
        exam_roll_number = (student["roll_no"] or "").strip()

    resolved_forms = []
    for f in forms:
        raw_form_program = (f["program"] or "") if ("program" in f.keys()) else ""
        form_program = _norm_text(raw_form_program)
        form_department = _scope_rule_clean((f["department"] or "") if ("department" in f.keys()) else "")
        if not _scope_match_program(resolved_student_program, student_program_id_int, raw_form_program):
            continue
        if not _scope_match(resolved_student_department, form_department):
            continue

        is_open = is_exam_form_open(f["open_from"], f["open_to"]) if ("open_from" in f.keys()) else False
        resolved_forms.append(
            {
                **dict(f),
                "computed_status": "OPEN" if is_open else "CLOSED",
                "is_open": is_open,
                "resolved_apply_url": resolve_exam_link(
                    f["apply_url"] if ("apply_url" in f.keys()) else None,
                    f["apply_roll_placeholder"] if ("apply_roll_placeholder" in f.keys()) else None,
                    exam_roll_number,
                ),
            }
        )

    admit_card_link = None
    resolved_admit_openings = []
    openings = db.execute(
        "SELECT * FROM admit_card_openings ORDER BY id DESC"
    ).fetchall()
    for o in openings:
        raw_o_program = (o["program"] or "") if ("program" in o.keys()) else ""
        o_program = _norm_text(raw_o_program)
        o_department = _scope_rule_clean((o["department"] or "") if ("department" in o.keys()) else "")
        if not _scope_match_program(resolved_student_program, student_program_id_int, raw_o_program):
            continue
        if not _scope_match(resolved_student_department, o_department):
            continue

        is_open = is_exam_form_open(
            o["open_from"] if ("open_from" in o.keys()) else None,
            o["open_to"] if ("open_to" in o.keys()) else None,
        )
        link = ""
        if exam_roll_number:
            link = resolve_exam_link(
                o["admit_card_url"] if ("admit_card_url" in o.keys()) else None,
                o["roll_placeholder"] if ("roll_placeholder" in o.keys()) else None,
                exam_roll_number,
            )
        resolved_admit_openings.append(
            {
                **dict(o),
                "is_open": is_open,
                "computed_status": "OPEN" if is_open else "CLOSED",
                "resolved_url": link,
            }
        )

    for o in resolved_admit_openings:
        if o.get("is_open") and o.get("resolved_url"):
            admit_card_link = o.get("resolved_url")
            break

    admit_card = None
    admit_subjects = []
    semester_result = None
    semester_result_courses = []
    if student and details and student_program:
        program_id = int(student_program["program_id"])
        program = db.execute("SELECT * FROM programs WHERE id = ?", (program_id,)).fetchone()
        session = db.execute(
            """
            SELECT * FROM exam_sessions
            WHERE program_id = ? AND semester = ? AND status = 'ACTIVE'
            ORDER BY datetime(issued_at) DESC
            LIMIT 1
            """,
            (program_id, int(student["sem"])),
        ).fetchone()

        if session and program:
            admit_card = {
                "university": session["university"],
                "session_label": session["session_label"],
                "program_label": f"{program['name']} ({program['branch']}) - {int(student['sem'])} Semester",
                "college_label": session["college_label"],
                "student_name": student["name"],
                "roll_number": details["exam_roll_number"] or student["roll_no"],
                "father_name": details["father_name"],
                "gender": details["gender"],
                "category": details["category"],
                "address": details["address"],
                "exam_center": session["exam_center"],
            }

            admit_subjects = db.execute(
                """
                SELECT
                    s.code AS subject_code,
                    s.name AS subject_name,
                    t.paper_type AS paper_type,
                    t.exam_date AS exam_date,
                    t.exam_time AS exam_time
                FROM student_subject_enrollments e
                JOIN subjects s ON s.id = e.subject_id
                LEFT JOIN exam_timetable t
                    ON t.subject_id = s.id AND t.session_id = ?
                WHERE e.student_id = ? AND e.session_label = ?
                ORDER BY s.code ASC
                """,
                (session["id"], sid, session["session_label"]),
            ).fetchall()

        semester_result = db.execute(
            """
            SELECT * FROM semester_results
            WHERE student_id = ? AND program_id = ? AND semester = ?
            ORDER BY declared_on DESC
            LIMIT 1
            """,
            (sid, program_id, int(student["sem"])),
        ).fetchone()
        if semester_result:
            semester_result_courses = db.execute(
                """
                SELECT * FROM semester_result_courses
                WHERE result_id = ?
                ORDER BY category ASC, course_code ASC
                """,
                (semester_result["id"],),
            ).fetchall()

    results = db.execute(
        "SELECT * FROM exam_results ORDER BY datetime(published_at) DESC"
    ).fetchall()

    return render_template(
        "exams.html",
        page_title="Exams Portal",
        page_subtitle="Track your performance",
        active_page="exams",
        forms=resolved_forms,
        admit_card_link=admit_card_link,
        admit_openings=resolved_admit_openings,
        admit_card=admit_card,
        admit_subjects=admit_subjects,
        semester_result=semester_result,
        semester_result_courses=semester_result_courses,
        results=results,
    )


@app.get("/admin/admit-card-openings/<int:opening_id>/edit")
@admin_login_required
def admin_admit_card_opening_edit(opening_id: int):
    db = get_db()
    opening = db.execute(
        "SELECT * FROM admit_card_openings WHERE id = ?",
        (int(opening_id),),
    ).fetchone()
    if not opening:
        return redirect(url_for("admin_admit_card_openings"))
    return render_template(
        "admin_admit_card_opening_form.html",
        page_title="Edit Admit Card Opening",
        page_subtitle="Update admit card link window",
        active_page="admin_exam_forms",
        error=None,
        opening=opening,
    )


@app.post("/admin/admit-card-openings/<int:opening_id>/edit")
@admin_login_required
def admin_admit_card_opening_update(opening_id: int):
    title = (request.form.get("title") or "").strip()
    semester_label = (request.form.get("semester_label") or "").strip()
    open_from = (request.form.get("open_from") or "").strip() or None
    open_to = (request.form.get("open_to") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    program = (request.form.get("program") or "").strip() or None
    department = (request.form.get("department") or "").strip() or None
    admit_card_url = (request.form.get("admit_card_url") or "").strip() or None
    roll_placeholder = (request.form.get("roll_placeholder") or "").strip() or None

    if not title or not semester_label or not admit_card_url or not open_from or not open_to:
        db = get_db()
        opening = db.execute(
            "SELECT * FROM admit_card_openings WHERE id = ?",
            (int(opening_id),),
        ).fetchone()
        return render_template(
            "admin_admit_card_opening_form.html",
            page_title="Edit Admit Card Opening",
            page_subtitle="Update admit card link window",
            active_page="admin_exam_forms",
            error="Title, semester, link, open from and open to are required.",
            opening=opening,
        )

    db = get_db()
    db.execute(
        """
        UPDATE admit_card_openings
        SET title = ?, semester_label = ?, open_from = ?, open_to = ?, note = ?,
            program = ?, department = ?, admit_card_url = ?, roll_placeholder = ?
        WHERE id = ?
        """,
        (
            title,
            semester_label,
            open_from,
            open_to,
            note,
            program,
            department,
            admit_card_url,
            roll_placeholder,
            int(opening_id),
        ),
    )
    db.commit()
    return redirect(get_safe_next_url("admin_admit_card_openings"))


@app.post("/exams/forms/<int:form_id>/apply")
@login_required
def exams_form_apply(form_id: int):
    db = get_db()
    sid = get_current_student_id()

    form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
    if not form:
        return redirect(url_for("exams"))
    if not is_exam_form_open(form["open_from"] if ("open_from" in form.keys()) else None, form["open_to"] if ("open_to" in form.keys()) else None):
        return redirect(url_for("exams"))

    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    details = db.execute("SELECT * FROM student_details WHERE student_id = ?", (sid,)).fetchone()
    exam_roll_number = ""
    if student and details:
        exam_roll_number = (details["exam_roll_number"] or "").strip() or (student["roll_no"] or "").strip()

    apply_url = (form["apply_url"] or "").strip() if ("apply_url" in form.keys()) else ""
    if not apply_url:
        return redirect(url_for("exams"))

    resolved = resolve_exam_link(
        apply_url,
        form["apply_roll_placeholder"] if ("apply_roll_placeholder" in form.keys()) else None,
        exam_roll_number,
    )
    if not resolved:
        return redirect(url_for("exams"))
    return redirect(resolved)


@app.get("/exams/admit-card/print")
@login_required
def exams_admit_print():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    details = db.execute("SELECT * FROM student_details WHERE student_id = ?", (sid,)).fetchone()
    student_program = db.execute("SELECT * FROM student_programs WHERE student_id = ?", (sid,)).fetchone()

    admit_card = None
    admit_subjects = []
    if student and details and student_program:
        program_id = int(student_program["program_id"])
        program = db.execute("SELECT * FROM programs WHERE id = ?", (program_id,)).fetchone()
        session = db.execute(
            """
            SELECT * FROM exam_sessions
            WHERE program_id = ? AND semester = ? AND status = 'ACTIVE'
            ORDER BY datetime(issued_at) DESC
            LIMIT 1
            """,
            (program_id, int(student["sem"])),
        ).fetchone()
        if session and program:
            admit_card = {
                "university": session["university"],
                "session_label": session["session_label"],
                "program_label": f"{program['name']} ({program['branch']}) - {int(student['sem'])} Semester",
                "college_label": session["college_label"],
                "student_name": student["name"],
                "roll_number": details["exam_roll_number"] or student["roll_no"],
                "father_name": details["father_name"],
                "gender": details["gender"],
                "category": details["category"],
                "address": details["address"],
                "exam_center": session["exam_center"],
            }
            admit_subjects = db.execute(
                """
                SELECT
                    s.code AS subject_code,
                    s.name AS subject_name,
                    t.paper_type AS paper_type,
                    t.exam_date AS exam_date,
                    t.exam_time AS exam_time
                FROM student_subject_enrollments e
                JOIN subjects s ON s.id = e.subject_id
                LEFT JOIN exam_timetable t
                    ON t.subject_id = s.id AND t.session_id = ?
                WHERE e.student_id = ? AND e.session_label = ?
                ORDER BY s.code ASC
                """,
                (session["id"], sid, session["session_label"]),
            ).fetchall()

    return render_template(
        "exams_admit_print.html",
        admit_card=admit_card,
        admit_subjects=admit_subjects,
    )


@app.get("/exams/result/print")
@login_required
def exams_result_print():
    db = get_db()
    sid = get_current_student_id()
    student_program = db.execute("SELECT * FROM student_programs WHERE student_id = ?", (sid,)).fetchone()
    semester_result = None
    semester_result_courses = []
    if student_program:
        program_id = int(student_program["program_id"])
        semester_result = db.execute(
            """
            SELECT * FROM semester_results
            WHERE student_id = ? AND program_id = ?
            ORDER BY declared_on DESC
            LIMIT 1
            """,
            (sid, program_id),
        ).fetchone()
        if semester_result:
            semester_result_courses = db.execute(
                """
                SELECT * FROM semester_result_courses
                WHERE result_id = ?
                ORDER BY category ASC, course_code ASC
                """,
                (semester_result["id"],),
            ).fetchall()

    return render_template(
        "exams_result_print.html",
        semester_result=semester_result,
        semester_result_courses=semester_result_courses,
    )


@app.get("/profile")
@login_required
def profile():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    student_program = db.execute("SELECT * FROM student_programs WHERE student_id = ?", (sid,)).fetchone()
    program = None
    if student_program:
        program = db.execute("SELECT * FROM programs WHERE id = ?", (int(student_program["program_id"]),)).fetchone()

    profile = db.execute("SELECT * FROM student_profile WHERE student_id = ?", (sid,)).fetchone()

    vault_folders = db.execute(
        "SELECT id, name FROM vault_folders WHERE student_id = ? ORDER BY created_at DESC",
        (sid,),
    ).fetchall()

    cp_error = (request.args.get("cp_error") or "").strip() or None
    cp_success = (request.args.get("cp_success") or "").strip() or None

    return render_template(
        "profile.html",
        page_title="My Profile",
        page_subtitle="Manage personal information",
        active_page="profile",
        student=student,
        program=program,
        profile=profile,
        vault_folders=vault_folders,
        cp_error=cp_error,
        cp_success=cp_success,
    )


@app.get("/profile/change-password")
@login_required
def student_change_password():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    return render_template(
        "change_password.html",
        page_title="Change Password",
        page_subtitle="Update your password",
        active_page="profile",
        student=student,
        error=None,
        success=None,
    )


@app.post("/profile/change-password")
@login_required
def student_change_password_post():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        session.pop("student_id", None)
        return redirect(url_for("login"))

    if not current_password or not new_password or not confirm_password:
        return redirect(url_for("profile", cp_error="Please fill in all fields."))

    if not student["password_hash"] or not check_password_hash(student["password_hash"], current_password):
        return redirect(url_for("profile", cp_error="Current password is incorrect."))

    if len(new_password) < 8:
        return redirect(url_for("profile", cp_error="New password must be at least 8 characters."))

    if new_password != confirm_password:
        return redirect(url_for("profile", cp_error="New password and confirmation do not match."))

    db.execute(
        "UPDATE students SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), int(student["id"])),
    )
    db.commit()

    return redirect(url_for("profile", cp_success="Password updated successfully."))


@app.get("/administration")
@login_required
def administration():
    return render_template_string(
        """
        {% extends 'base.html' %}
        {% block content %}
        <section class="tab-content space-y-6">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-xl font-semibold text-slate-900">Administration</h2>
                    <p class="text-sm text-slate-500 mt-1">Administrative services</p>
                </div>
                <a href="{{ url_for('profile') }}" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 transition-all">Back</a>
            </div>
            <div class="minimal-card p-6">
                <p class="text-sm text-slate-600">Administrative portal integration is pending. Add links here to student verification, ID card, hostel/transport services, etc.</p>
            </div>
        </section>
        {% endblock %}
        """,
        page_title="Administration",
        page_subtitle="Administrative services",
        active_page="profile",
    )


@app.get("/fee-payment")
@login_required
def fee_payment():
    return render_template_string(
        """
        {% extends 'base.html' %}
        {% block content %}
        <section class="tab-content space-y-6">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-xl font-semibold text-slate-900">Fee Payment</h2>
                    <p class="text-sm text-slate-500 mt-1">Pay semester fees and download receipts</p>
                </div>
                <a href="{{ url_for('profile') }}" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 transition-all">Back</a>
            </div>
            <div class="minimal-card p-6">
                <p class="text-sm text-slate-600">Fee payment gateway integration is pending. Add your institute payment URL or API integration here.</p>
            </div>
        </section>
        {% endblock %}
        """,
        page_title="Fee Payment",
        page_subtitle="Pay semester fees and download receipts",
        active_page="profile",
    )


if __name__ == "__main__":
    init_db()
    debug = (os.getenv("FLASK_DEBUG", "").strip() == "1") or (
        os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes"}
    )
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=debug)
