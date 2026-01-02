from __future__ import annotations

import calendar
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, abort, redirect, render_template, render_template_string, request, send_file, url_for
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
        start = datetime.fromisoformat(open_from)
        end = datetime.fromisoformat(open_to)
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
