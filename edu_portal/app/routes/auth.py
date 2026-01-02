from __future__ import annotations

import re

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..services.auth_service import get_current_admin_id, get_current_student_id
from ..services.db_service import get_db


bp = Blueprint("auth", __name__)


@bp.context_processor
def inject_user():
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


@bp.get("/login")
def login():
    if get_current_student_id() is not None:
        return redirect(url_for("student.dashboard"))
    return render_template("login.html", error=None)


@bp.post("/login")
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
    return redirect(url_for("student.dashboard"))


@bp.get("/logout")
def logout():
    session.pop("student_id", None)
    return redirect(url_for("auth.login"))


@bp.get("/admin/login")
def admin_login():
    if get_current_admin_id() is not None:
        return redirect(url_for("admin.dashboard"))
    return render_template("admin_login.html", error=None)


@bp.post("/admin/login")
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
    return redirect(url_for("admin.dashboard"))


@bp.get("/admin/logout")
def admin_logout():
    session.pop("admin_user_id", None)
    return redirect(url_for("auth.admin_login"))


@bp.get("/register")
def register():
    if get_current_student_id() is not None:
        return redirect(url_for("student.dashboard"))
    db = get_db()
    groups = db.execute("SELECT * FROM schedule_groups ORDER BY id ASC").fetchall()
    return render_template("register.html", error=None, schedule_groups=groups)


@bp.post("/register")
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

    db.commit()
    session["student_id"] = student_id
    return redirect(url_for("student.dashboard"))
