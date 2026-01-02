from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Blueprint, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ..config import BASE_DIR, NEWS_UPLOAD_DIR, VAULT_UPLOAD_DIR
from ..services.auth_service import admin_login_required, get_current_admin_id, get_safe_next_url
from ..services.db_service import get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")


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


def sanitize_news_html(html: str) -> str:
    if not html:
        return ""

    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.I | re.S)
    cleaned = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\son\w+\s*=\s*'[^']*'", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\son\w+\s*=\s*[^\s>]+", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"(href|src)\s*=\s*\"\s*javascript:[^\"]*\"",
        r"\1=\"#\"",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"(href|src)\s*=\s*'\s*javascript:[^']*'",
        r"\1='#'",
        cleaned,
        flags=re.I,
    )

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
            if href:
                url = (href.group(2) or "").strip()
                if url.lower().startswith("javascript:"):
                    tag = re.sub(r"href\s*=\s*(['\"]).*?\1", "href=\"#\"", tag, flags=re.I)
        tag = re.sub(r"\s(on\w+)\s*=\s*(['\"]).*?\2", "", tag, flags=re.I)
        return tag

    cleaned = re.sub(r"</?\s*([a-zA-Z0-9]+)([^>]*)>", _filter_tag, cleaned)
    return cleaned


@bp.app_template_filter("fmt_dt")
def fmt_dt(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", ""))
    except Exception:
        return str(value)
    return dt.strftime("%d-%m-%Y %I:%M %p")


@bp.app_context_processor
def inject_admin_user():
    aid = get_current_admin_id()
    if aid is None:
        return {"admin_user": None}
    db = get_db()
    admin_user = db.execute("SELECT * FROM admin_users WHERE id = ?", (int(aid),)).fetchone()
    return {"admin_user": admin_user}


@bp.get("/")
@admin_login_required
def dashboard():
    db = get_db()
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
        news_count=int(news_count),
        open_forms=int(open_forms),
        error=None,
    )


@bp.get("/change-password")
@admin_login_required
def change_password():
    return render_template(
        "admin_change_password.html",
        page_title="Change Password",
        page_subtitle="Update your admin password",
        active_page="admin",
        error=None,
        success=None,
    )


@bp.post("/change-password", endpoint="change_password_post")
@admin_login_required
def change_password_post():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    next_url = get_safe_next_url("admin.dashboard")
    sep = "&" if ("?" in next_url) else "?"

    db = get_db()
    aid = get_current_admin_id()
    admin_user = db.execute("SELECT * FROM admin_users WHERE id = ?", (aid,)).fetchone()
    if not admin_user:
        session.pop("admin_user_id", None)
        return redirect(url_for("auth.admin_login"))

    if not current_password or not new_password or not confirm_password:
        return redirect(f"{next_url}{sep}ap_error={quote('Please fill in all fields.')}")

    if not admin_user["password_hash"] or not check_password_hash(admin_user["password_hash"], current_password):
        return redirect(f"{next_url}{sep}ap_error={quote('Current password is incorrect.')}")

    if len(new_password) < 8:
        return redirect(f"{next_url}{sep}ap_error={quote('New password must be at least 8 characters.')}")

    if new_password != confirm_password:
        return redirect(f"{next_url}{sep}ap_error={quote('New password and confirmation do not match.')}")

    db.execute(
        "UPDATE admin_users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), int(admin_user["id"])),
    )
    db.commit()

    return redirect(f"{next_url}{sep}ap_success={quote('Password updated successfully.')}")


@bp.get("/schedules")
@admin_login_required
def schedules():
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
        SELECT wt.*, sg.name AS schedule_group_name
        FROM weekly_timetable wt
        LEFT JOIN schedule_groups sg ON sg.id = wt.schedule_id
        WHERE wt.schedule_id = ?
        ORDER BY wt.day_of_week ASC, time(wt.start_time) ASC
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


@bp.post("/calendar-items/new")
@admin_login_required
def calendar_item_create():
    item_date = (request.form.get("item_date") or "").strip()
    item_type = (request.form.get("item_type") or "").strip()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not item_date or not item_type or not title:
        return redirect(url_for("admin.schedules"))
    db = get_db()
    db.execute(
        "INSERT INTO calendar_items (item_date, item_type, title, description) VALUES (?, ?, ?, ?)",
        (item_date, item_type, title, description),
    )
    db.commit()
    return redirect(url_for("admin.schedules"))


@bp.post("/calendar-items/<int:item_id>/update")
@admin_login_required
def calendar_item_update(item_id: int):
    item_date = (request.form.get("item_date") or "").strip()
    item_type = (request.form.get("item_type") or "").strip()
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not item_date or not item_type or not title:
        return redirect(url_for("admin.schedules"))
    db = get_db()
    db.execute(
        "UPDATE calendar_items SET item_date = ?, item_type = ?, title = ?, description = ? WHERE id = ?",
        (item_date, item_type, title, description, int(item_id)),
    )
    db.commit()
    return redirect(url_for("admin.schedules"))


@bp.post("/calendar-items/<int:item_id>/delete")
@admin_login_required
def calendar_item_delete(item_id: int):
    db = get_db()
    db.execute("DELETE FROM calendar_items WHERE id = ?", (int(item_id),))
    db.commit()
    return redirect(url_for("admin.schedules"))


@bp.post("/schedules/groups/new")
@admin_login_required
def schedule_group_create():
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
        return redirect(url_for("admin.schedules"))
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
    return redirect(url_for("admin.schedules", schedule_id=new_id))


@bp.post("/schedules/groups/<int:group_id>/update")
@admin_login_required
def schedule_group_update(group_id: int):
    name = (request.form.get("name") or "").strip()
    schedule_id_raw = (request.form.get("schedule_id") or request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = int(group_id)

    if not name:
        return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))

    db = get_db()
    db.execute("UPDATE schedule_groups SET name = ? WHERE id = ?", (name, int(group_id)))
    db.commit()
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/events/new")
@admin_login_required
def schedules_event_create():
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
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/events/<int:event_id>/delete")
@admin_login_required
def schedules_event_delete(event_id: int):
    schedule_id_raw = (request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1
    db = get_db()
    db.execute("DELETE FROM schedules WHERE id = ?", (int(event_id),))
    db.commit()
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/timetable/new")
@admin_login_required
def timetable_create():
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
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/timetable/<int:row_id>/update")
@admin_login_required
def timetable_update(row_id: int):
    schedule_id_raw = (request.form.get("schedule_id") or request.args.get("schedule_id") or "").strip()
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
        return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))

    db = get_db()
    db.execute(
        """
        UPDATE weekly_timetable
        SET schedule_id = ?, day_of_week = ?, start_time = ?, end_time = ?, subject = ?, room = ?, instructor = ?
        WHERE id = ?
        """,
        (int(schedule_id), int(day_of_week), start_time, end_time, subject, room, instructor, int(row_id)),
    )
    db.commit()
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/timetable/<int:row_id>/delete")
@admin_login_required
def timetable_delete(row_id: int):
    schedule_id_raw = (request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1
    db = get_db()
    db.execute("DELETE FROM weekly_timetable WHERE id = ?", (int(row_id),))
    db.commit()
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/timetable/bulk-delete")
@admin_login_required
def timetable_bulk_delete():
    schedule_id_raw = (request.form.get("schedule_id") or request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1

    ids = request.form.getlist("row_ids")
    resolved: list[int] = []
    for raw in ids:
        try:
            resolved.append(int(raw))
        except Exception:
            continue
    if not resolved:
        return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))

    db = get_db()
    placeholders = ",".join(["?"] * len(resolved))
    db.execute(f"DELETE FROM weekly_timetable WHERE id IN ({placeholders})", tuple(resolved))
    db.commit()
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.post("/schedules/timetable/bulk-update")
@admin_login_required
def timetable_bulk_update():
    schedule_id_raw = (request.form.get("schedule_id") or request.args.get("schedule_id") or "").strip()
    try:
        schedule_id = int(schedule_id_raw)
    except Exception:
        schedule_id = 1

    ids = request.form.getlist("row_ids")
    resolved: list[int] = []
    for raw in ids:
        try:
            resolved.append(int(raw))
        except Exception:
            continue
    if not resolved:
        return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))

    day_of_week_raw = (request.form.get("day_of_week") or "").strip()
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()
    subject = (request.form.get("subject") or "").strip()
    room = (request.form.get("room") or "").strip()
    instructor = (request.form.get("instructor") or "").strip()

    day_of_week = None
    if day_of_week_raw:
        try:
            day_of_week = int(day_of_week_raw)
        except Exception:
            day_of_week = None
    if day_of_week is not None and (day_of_week < 0 or day_of_week > 6):
        day_of_week = None

    db = get_db()
    rows = db.execute(
        f"SELECT * FROM weekly_timetable WHERE id IN ({','.join(['?'] * len(resolved))})",
        tuple(resolved),
    ).fetchall()
    by_id = {int(r["id"]): r for r in rows}

    for rid in resolved:
        r = by_id.get(int(rid))
        if not r:
            continue

        new_schedule_id = schedule_id if schedule_id else int(r["schedule_id"] or 1)
        new_day = day_of_week if day_of_week is not None else int(r["day_of_week"])
        new_start = start_time or str(r["start_time"])
        new_end = end_time or str(r["end_time"])
        new_subject = subject or str(r["subject"])
        new_room = room or str(r["room"])
        new_instructor = instructor or str(r["instructor"])

        db.execute(
            """
            UPDATE weekly_timetable
            SET schedule_id = ?, day_of_week = ?, start_time = ?, end_time = ?, subject = ?, room = ?, instructor = ?
            WHERE id = ?
            """,
            (
                int(new_schedule_id),
                int(new_day),
                new_start,
                new_end,
                new_subject,
                new_room,
                new_instructor,
                int(rid),
            ),
        )

    db.commit()
    return redirect(url_for("admin.schedules", schedule_id=int(schedule_id)))


@bp.get("/teachers")
@admin_login_required
def teachers():
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

    filtered = []
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
        filtered.append(t)

    return render_template(
        "admin_teachers.html",
        page_title="Teachers",
        page_subtitle="Manage faculty list",
        active_page="admin_teachers",
        teachers=filtered,
        filters=filters,
        error=None,
    )


@bp.post("/teachers/new", endpoint="teachers_create")
@admin_login_required
def teacher_create():
    name = (request.form.get("name") or "").strip()
    designation = (request.form.get("designation") or "").strip()
    department = (request.form.get("department") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    phone = (request.form.get("phone") or "").strip() or None
    if not name or not designation or not department:
        db = get_db()
        teachers_rows = db.execute("SELECT * FROM teachers ORDER BY name ASC").fetchall()
        return render_template(
            "admin_teachers.html",
            page_title="Teachers",
            page_subtitle="Manage faculty list",
            active_page="admin_teachers",
            teachers=teachers_rows,
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
    return redirect(url_for("admin.teachers"))


@bp.post("/teachers/<int:teacher_id>/update")
@admin_login_required
def teacher_update(teacher_id: int):
    db = get_db()
    t = db.execute("SELECT * FROM teachers WHERE id = ?", (int(teacher_id),)).fetchone()
    if not t:
        return redirect(url_for("admin.teachers"))

    name = (request.form.get("name") or "").strip()
    designation = (request.form.get("designation") or "").strip()
    department = (request.form.get("department") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    phone = (request.form.get("phone") or "").strip() or None

    if not name or not designation or not department:
        return redirect(url_for("admin.teachers"))

    db.execute(
        "UPDATE teachers SET name = ?, designation = ?, department = ?, email = ?, phone = ? WHERE id = ?",
        (name, designation, department, email, phone, int(teacher_id)),
    )
    db.commit()
    return redirect(url_for("admin.teachers"))


@bp.post("/teachers/<int:teacher_id>/delete", endpoint="teachers_delete")
@admin_login_required
def teacher_delete(teacher_id: int):
    db = get_db()
    db.execute("DELETE FROM teachers WHERE id = ?", (int(teacher_id),))
    db.commit()
    return redirect(url_for("admin.teachers"))


@bp.get("/students")
@admin_login_required
def students():
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

    students_rows = db.execute("SELECT * FROM students ORDER BY id DESC").fetchall()
    details = {int(r["student_id"]): r for r in db.execute("SELECT * FROM student_details").fetchall()}
    profiles = {int(r["student_id"]): r for r in db.execute("SELECT * FROM student_profile").fetchall()}
    dues = {int(r["student_id"]): r for r in db.execute("SELECT * FROM student_dues").fetchall()}
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
    for s in students_rows:
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


@bp.post("/students/<int:student_id>/update")
@admin_login_required
def student_update(student_id: int):
    form = {k: (request.form.get(k) or "").strip() for k in request.form.keys()}
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (int(student_id),)).fetchone()
    if not student:
        return redirect(url_for("admin.students"))

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
            if payload and {"father_name", "gender", "category", "address"}.issubset(
                set(payload.keys()) | {"father_name", "gender", "category", "address"}
            ):
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
    return redirect(url_for("admin.students"))


@bp.post("/students/bulk-update")
@admin_login_required
def students_bulk_update():
    raw_ids = request.form.getlist("student_ids")

    student_ids: list[int] = []
    for x in raw_ids:
        try:
            student_ids.append(int(x))
        except Exception:
            continue
    if not student_ids:
        return redirect(url_for("admin.students"))

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
    return redirect(url_for("admin.students"))


@bp.post("/students/<int:student_id>/delete")
@admin_login_required
def student_delete(student_id: int):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id = ?", (int(student_id),)).fetchone()
    if not student:
        return redirect(url_for("admin.students"))

    vault_files = db.execute(
        "SELECT stored_path FROM vault_files WHERE student_id = ?",
        (int(student_id),),
    ).fetchall()
    for f in vault_files:
        stored = (f["stored_path"] or "").strip()
        if stored.startswith("vault/"):
            abs_path = BASE_DIR / "uploads" / stored
            try:
                if abs_path.exists() and abs_path.is_file():
                    abs_path.unlink()
            except Exception:
                pass

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
    return redirect(url_for("admin.students"))


@bp.get("/news")
@admin_login_required
def news_list():
    db = get_db()
    posts = db.execute("SELECT * FROM news_posts ORDER BY datetime(date_time) DESC").fetchall()
    return render_template(
        "admin_news_list.html",
        page_title="Manage News",
        page_subtitle="Create, edit or delete posts",
        active_page="admin_news",
        posts=posts,
    )


@bp.get("/news/new", endpoint="news_new")
@admin_login_required
def news_new():
    return render_template(
        "admin_news_form.html",
        page_title="New News Post",
        page_subtitle="Publish an announcement",
        active_page="admin_news",
        post=None,
        error=None,
    )


@bp.post("/news/new", endpoint="news_create")
@admin_login_required
def news_create():
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
    return redirect(url_for("admin.news_list"))


@bp.route("/news/<int:post_id>/edit", methods=["GET", "POST"])
@admin_login_required
def news_update(post_id: int):
    if request.method == "GET":
        db = get_db()
        post = db.execute("SELECT * FROM news_posts WHERE id = ?", (int(post_id),)).fetchone()
        if not post:
            return redirect(url_for("admin.news_list"))
        return render_template(
            "admin_news_form.html",
            page_title="Edit News Post",
            page_subtitle="Update announcement",
            active_page="admin_news",
            post=post,
            error=None,
        )

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
    return redirect(url_for("admin.news_list"))


@bp.post("/news/<int:post_id>/delete")
@admin_login_required
def news_delete(post_id: int):
    db = get_db()
    db.execute("DELETE FROM news_posts WHERE id = ?", (int(post_id),))
    db.commit()
    return redirect(url_for("admin.news_list"))


@bp.get("/exam-forms")
@admin_login_required
def exam_forms():
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


@bp.get("/exam-forms/new", endpoint="exam_form_new")
@admin_login_required
def exam_form_new():
    return render_template(
        "admin_exam_form_form.html",
        page_title="New Exam Form",
        page_subtitle="Create a new exam application form",
        active_page="admin_exam_forms",
        form=None,
        error=None,
    )


@bp.post("/exam-forms/new", endpoint="exam_form_create")
@admin_login_required
def exam_form_create():
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
    return redirect(url_for("admin.exam_forms"))


@bp.route("/exam-forms/<int:form_id>/edit", methods=["GET", "POST"])
@admin_login_required
def exam_form_update(form_id: int):
    if request.method == "GET":
        db = get_db()
        form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
        if not form:
            return redirect(url_for("admin.exam_forms"))
        return render_template(
            "admin_exam_form_form.html",
            page_title="Edit Exam Form",
            page_subtitle="Update exam application form",
            active_page="admin_exam_forms",
            form=form,
            error=None,
        )

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
    return redirect(url_for("admin.exam_forms"))


@bp.post("/exam-forms/<int:form_id>/delete")
@admin_login_required
def exam_form_delete(form_id: int):
    db = get_db()
    db.execute("DELETE FROM exam_forms WHERE id = ?", (int(form_id),))
    db.commit()
    return redirect(url_for("admin.exam_forms"))


@bp.post("/exam-forms/<int:form_id>/toggle")
@admin_login_required
def exam_form_toggle(form_id: int):
    db = get_db()
    form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
    if not form:
        return redirect(url_for("admin.exam_forms"))
    new_status = "CLOSED" if (form["status"] or "").upper() == "OPEN" else "OPEN"
    db.execute("UPDATE exam_forms SET status = ? WHERE id = ?", (new_status, int(form_id)))
    db.commit()
    return redirect(url_for("admin.exam_forms"))


@bp.get("/exam-forms/<int:form_id>/submissions")
@admin_login_required
def exam_form_submissions(form_id: int):
    db = get_db()
    form = db.execute("SELECT * FROM exam_forms WHERE id = ?", (int(form_id),)).fetchone()
    if not form:
        return redirect(url_for("admin.exam_forms"))
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


@bp.get("/admit-card-openings")
@admin_login_required
def admit_card_openings():
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


@bp.route("/admit-card-openings/new", methods=["GET", "POST"])
@admin_login_required
def admit_card_opening_create():
    if request.method == "GET":
        return render_template(
            "admin_admit_card_opening_form.html",
            page_title="New Admit Card Opening",
            page_subtitle="Create a new admit card link window",
            active_page="admin_exam_forms",
            error=None,
        )

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
    return redirect(get_safe_next_url("admin.admit_card_openings"))


@bp.get("/admit-card-openings/<int:opening_id>/edit")
@admin_login_required
def admit_card_opening_edit(opening_id: int):
    db = get_db()
    opening = db.execute(
        "SELECT * FROM admit_card_openings WHERE id = ?",
        (int(opening_id),),
    ).fetchone()
    if not opening:
        return redirect(url_for("admin.admit_card_openings"))
    return render_template(
        "admin_admit_card_opening_form.html",
        page_title="Edit Admit Card Opening",
        page_subtitle="Update admit card link window",
        active_page="admin_exam_forms",
        error=None,
        opening=opening,
    )


@bp.post("/admit-card-openings/<int:opening_id>/edit")
@admin_login_required
def admit_card_opening_update(opening_id: int):
    title = (request.form.get("title") or "").strip()
    semester_label = (request.form.get("semester_label") or "").strip()
    open_from = (request.form.get("open_from") or "").strip() or None
    open_to = (request.form.get("open_to") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    program = (request.form.get("program") or "").strip() or None
    department = (request.form.get("department") or "").strip() or None
    admit_card_url = (request.form.get("admit_card_url") or "").strip() or None
    roll_placeholder = (request.form.get("roll_placeholder") or "").strip() or None

    db = get_db()
    opening = db.execute(
        "SELECT * FROM admit_card_openings WHERE id = ?",
        (int(opening_id),),
    ).fetchone()
    if not opening:
        return redirect(url_for("admin.admit_card_openings"))

    if not title or not semester_label or not admit_card_url or not open_from or not open_to:
        return render_template(
            "admin_admit_card_opening_form.html",
            page_title="Edit Admit Card Opening",
            page_subtitle="Update admit card link window",
            active_page="admin_exam_forms",
            error="Title, semester, link, open from and open to are required.",
            opening=opening,
        )

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
    return redirect(get_safe_next_url("admin.admit_card_openings"))


@bp.post("/admit-card-openings/<int:opening_id>/delete")
@admin_login_required
def admit_card_opening_delete(opening_id: int):
    db = get_db()
    db.execute("DELETE FROM admit_card_openings WHERE id = ?", (int(opening_id),))
    db.commit()
    return redirect(get_safe_next_url("admin.admit_card_openings"))
