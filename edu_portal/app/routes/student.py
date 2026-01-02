from __future__ import annotations

import calendar
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, render_template_string, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ..config import NEWS_UPLOAD_DIR, VAULT_UPLOAD_DIR
from ..services.auth_service import get_current_student_id, get_safe_next_url, login_required
from ..services.db_service import get_db


bp = Blueprint("student", __name__)


def _norm_text(v: str | None) -> str:
    return " ".join((v or "").strip().lower().split())


def _scope_match(student_val: str, rule_val: str) -> bool:
    s = _norm_text(student_val)
    r = _norm_text(rule_val)
    if not r:
        return True
    if r in {"all", "any"}:
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


def resolve_exam_link(url_template: str | None, placeholder: str | None, exam_roll_number: str) -> str:
    url = (url_template or "").strip()
    if not url:
        return ""
    marker = (placeholder or "{roll}").strip() or "{roll}"
    from urllib.parse import quote

    encoded = quote(exam_roll_number or "")
    return url.replace(marker, encoded)


def is_exam_form_open(open_from: str | None, open_to: str | None, now: datetime | None = None) -> bool:
    if not open_from or not open_to:
        return False
    try:
        current = now or datetime.utcnow()
        try:
            start = datetime.fromisoformat(open_from)
        except Exception:
            start = datetime.strptime(open_from, "%Y-%m-%d")
        try:
            end = datetime.fromisoformat(open_to)
        except Exception:
            end = datetime.strptime(open_to, "%Y-%m-%d")
        return start <= current <= end
    except Exception:
        return False


def get_vault_abs_path(stored_path: str) -> Path | None:
    stored = (stored_path or "").strip()
    if not stored.startswith("vault/"):
        return None
    return Path(__file__).resolve().parents[3] / "uploads" / stored


def delete_vault_physical_file(stored_path: str) -> None:
    abs_path = get_vault_abs_path(stored_path)
    if abs_path is None:
        return
    try:
        if abs_path.exists() and abs_path.is_file():
            abs_path.unlink()
    except Exception:
        return


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


@bp.get("/")
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


@bp.get("/teachers")
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


@bp.get("/library")
@login_required
def library():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    filters = {
        "q": (request.args.get("q") or "").strip(),
        "tag": (request.args.get("tag") or "").strip(),
        "uploader": (request.args.get("uploader") or "").strip(),
    }

    where = []
    params: list[str] = []
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
        for r in db.execute("SELECT DISTINCT uploader FROM library_resources ORDER BY uploader").fetchall()
    ]
    return render_template(
        "library.html",
        page_title="Digital Library",
        page_subtitle="Books & Journals",
        active_page="library",
        student=student,
        resources=resources,
        uploaders=uploaders,
        filters=filters,
    )


@bp.post("/library/resources/upload")
@login_required
def library_resource_upload():
    heading = (request.form.get("heading") or "").strip()
    description = (request.form.get("description") or "").strip()
    tags = (request.form.get("tags") or "").strip()
    uploader = (request.form.get("uploader") or "").strip()
    pdf_url = (request.form.get("pdf_url") or "").strip()
    pdf_file = request.files.get("pdf_file")

    if not heading or not description or not uploader:
        return redirect(url_for("student.library"))

    final_pdf_url = ""
    if pdf_file and pdf_file.filename:
        filename = secure_filename(pdf_file.filename)
        if not filename.lower().endswith(".pdf"):
            return redirect(url_for("student.library"))
        upload_dir = Path(__file__).resolve().parents[3] / "static" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_name = f"{stamp}_{filename}"
        pdf_file.save(str(upload_dir / safe_name))
        final_pdf_url = f"uploads/{safe_name}"
    else:
        if not pdf_url:
            return redirect(url_for("student.library"))
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
    return redirect(url_for("student.library"))


@bp.post("/vault/folders")
@login_required
def vault_folder_create():
    sid = get_current_student_id()
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(get_safe_next_url("student.dashboard"))

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
    return redirect(get_safe_next_url("student.dashboard"))


@bp.post("/vault/folders/<int:folder_id>/delete")
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
    return redirect(get_safe_next_url("student.dashboard"))


@bp.post("/vault/files")
@login_required
def vault_file_upload():
    sid = get_current_student_id()
    try:
        folder_id = int(request.form.get("folder_id") or "0")
    except Exception:
        folder_id = 0
    upload = request.files.get("file")
    if not folder_id or upload is None or not (upload.filename or "").strip():
        return redirect(get_safe_next_url("student.dashboard"))

    db = get_db()
    folder = db.execute(
        "SELECT * FROM vault_folders WHERE id = ? AND student_id = ?",
        (folder_id, sid),
    ).fetchone()
    if not folder:
        return redirect(get_safe_next_url("student.dashboard"))

    saved = save_vault_file(upload, int(sid))
    if saved is None:
        return redirect(get_safe_next_url("student.dashboard"))
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
    return redirect(get_safe_next_url("student.dashboard"))


@bp.get("/vault/files/<int:file_id>/download")
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
    abs_path = Path(__file__).resolve().parents[3] / "uploads" / stored
    if not abs_path.exists() or not abs_path.is_file():
        abort(404)

    return send_file(
        str(abs_path),
        as_attachment=True,
        download_name=f["original_name"],
        mimetype=(f["mime"] or None),
    )


@bp.post("/vault/files/<int:file_id>/delete", endpoint="vault_file_delete")
@login_required
def vault_file_delete(file_id: int):
    sid = get_current_student_id()
    db = get_db()
    f = db.execute(
        "SELECT * FROM vault_files WHERE id = ? AND student_id = ?",
        (int(file_id), sid),
    ).fetchone()
    if not f:
        return redirect(get_safe_next_url("student.dashboard"))

    delete_vault_physical_file(f["stored_path"])
    db.execute(
        "DELETE FROM vault_files WHERE id = ? AND student_id = ?",
        (int(file_id), sid),
    )
    db.commit()
    return redirect(get_safe_next_url("student.dashboard"))


@bp.post("/vault/files/bulk-delete", endpoint="vault_files_bulk_delete")
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
        return redirect(get_safe_next_url("student.vault"))

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
    return redirect(get_safe_next_url("student.vault"))


@bp.post("/vault/files/bulk-move", endpoint="vault_files_bulk_move")
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
        return redirect(get_safe_next_url("student.vault"))

    db = get_db()
    target = db.execute(
        "SELECT id FROM vault_folders WHERE id = ? AND student_id = ?",
        (int(target_folder_id), sid),
    ).fetchone()
    if not target:
        return redirect(get_safe_next_url("student.vault"))

    q_marks = ",".join(["?"] * len(file_ids))
    db.execute(
        f"UPDATE vault_files SET folder_id = ? WHERE student_id = ? AND id IN ({q_marks})",
        [int(target_folder_id), sid, *file_ids],
    )
    db.commit()
    return redirect(get_safe_next_url("student.vault"))


@bp.post("/vault/files/bulk-copy", endpoint="vault_files_bulk_copy")
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
        return redirect(get_safe_next_url("student.vault"))

    db = get_db()
    target = db.execute(
        "SELECT id FROM vault_folders WHERE id = ? AND student_id = ?",
        (int(target_folder_id), sid),
    ).fetchone()
    if not target:
        return redirect(get_safe_next_url("student.vault"))

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
    return redirect(get_safe_next_url("student.vault"))


@bp.get("/vault")
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


@bp.get("/news")
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


@bp.get("/schedules")
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
        """,
        (int(schedule_id),),
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

    month_overview = []
    for m in month_items:
        month_overview.append(
            {
                "kind": "CALENDAR_ITEM",
                "date": str(m["item_date"]),
                "item_type": m["item_type"],
                "title": m["title"],
                "description": m["description"],
            }
        )
    for e in month_schedule_events:
        month_overview.append(
            {
                "kind": "SCHEDULE",
                "date": str(e["start_at"])[:10],
                "title": e["title"],
                "location": e["location"],
                "start_at": e["start_at"],
                "end_at": e["end_at"],
            }
        )
    month_overview.sort(key=lambda x: (x.get("date") or "", x.get("kind") or ""))

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

    month_items_by_date: dict[str, list[dict]] = {}
    for m in month_items:
        key = m["item_date"]
        month_items_by_date.setdefault(key, []).append(
            {
                "type": m["item_type"],
                "title": m["title"],
                "description": m["description"],
            }
        )

    schedule_by_date: dict[str, list[dict]] = {}
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
        student=student,
        events=events,
        timetable_by_day=timetable_by_day,
        month_items=month_items,
        month_schedule_events=month_schedule_events,
        month_overview=month_overview,
        month_label=today.strftime("%B %Y"),
        today_dow=today_dow,
        today_date=today.date().isoformat(),
        calendar_weeks=calendar_weeks,
        month_items_by_date=month_items_by_date,
        schedule_by_date=schedule_by_date,
        timetable_for_popup=timetable_for_popup,
    )


@bp.get("/exams")
@login_required
def exams():
    db = get_db()
    forms = db.execute("SELECT * FROM exam_forms ORDER BY id DESC").fetchall()

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
    if student_program and ("program_id" in student_program.keys()):
        try:
            program_row = db.execute(
                "SELECT * FROM programs WHERE id = ?",
                (int(student_program["program_id"]),),
            ).fetchone()
            if program_row:
                resolved_student_program = _norm_text(program_row["name"])
                resolved_student_department = _norm_text(program_row["branch"])
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
        form_department = _scope_rule_clean((f["department"] or "") if ("department" in f.keys()) else "")
        if not _scope_match_program(resolved_student_program, student_program_id_int, raw_form_program):
            continue
        if not _scope_match(resolved_student_department, form_department):
            continue

        is_open = is_exam_form_open(
            f["open_from"] if ("open_from" in f.keys()) else None,
            f["open_to"] if ("open_to" in f.keys()) else None,
        )
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
    openings = db.execute("SELECT * FROM admit_card_openings ORDER BY id DESC").fetchall()
    for o in openings:
        raw_o_program = (o["program"] or "") if ("program" in o.keys()) else ""
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
    if student and details and student_program and ("program_id" in student_program.keys()):
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

    results = db.execute("SELECT * FROM exam_results ORDER BY datetime(published_at) DESC").fetchall()

    return render_template(
        "exams.html",
        page_title="Exams Portal",
        page_subtitle="Track your performance",
        active_page="exams",
        student=student,
        forms=resolved_forms,
        admit_card_link=admit_card_link,
        admit_openings=resolved_admit_openings,
        admit_card=admit_card,
        admit_subjects=admit_subjects,
        semester_result=semester_result,
        semester_result_courses=semester_result_courses,
        results=results,
    )


@bp.get("/profile")
@login_required
def profile():
    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()

    student_program = db.execute("SELECT * FROM student_programs WHERE student_id = ?", (sid,)).fetchone()
    program = None
    if student_program and ("program_id" in student_program.keys()):
        program = db.execute(
            "SELECT * FROM programs WHERE id = ?",
            (int(student_program["program_id"]),),
        ).fetchone()

    profile_row = db.execute("SELECT * FROM student_profile WHERE student_id = ?", (sid,)).fetchone()

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
        profile=profile_row,
        vault_folders=vault_folders,
        cp_error=cp_error,
        cp_success=cp_success,
    )


@bp.get("/profile/change-password", endpoint="change_password")
@login_required
def change_password():
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


@bp.post("/profile/change-password", endpoint="change_password_post")
@login_required
def change_password_post():
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    db = get_db()
    sid = get_current_student_id()
    student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        session.pop("student_id", None)
        return redirect(url_for("auth.login"))

    if not current_password or not new_password or not confirm_password:
        return redirect(url_for("student.profile", cp_error="Please fill in all fields."))

    if not student["password_hash"] or not check_password_hash(student["password_hash"], current_password):
        return redirect(url_for("student.profile", cp_error="Current password is incorrect."))

    if len(new_password) < 8:
        return redirect(url_for("student.profile", cp_error="New password must be at least 8 characters."))

    if new_password != confirm_password:
        return redirect(url_for("student.profile", cp_error="New password and confirmation do not match."))

    db.execute(
        "UPDATE students SET password_hash = ? WHERE id = ?",
        (generate_password_hash(new_password), int(student["id"])),
    )
    db.commit()

    return redirect(url_for("student.profile", cp_success="Password updated successfully."))


@bp.get("/administration")
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
                <a href="{{ url_for('student.profile') }}" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 transition-all">Back</a>
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


@bp.get("/fee-payment")
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
                <a href="{{ url_for('student.profile') }}" class="px-4 py-2 rounded-xl bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 transition-all">Back</a>
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
