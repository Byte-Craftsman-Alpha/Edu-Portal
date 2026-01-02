from __future__ import annotations

from functools import wraps
from urllib.parse import quote

from flask import redirect, render_template, request, session, url_for

from .db_service import get_db


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


def get_safe_next_url(default_endpoint: str = "student.dashboard") -> str:
    next_url = (request.args.get("next") or request.form.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for(default_endpoint)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_student_id() is None:
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if get_current_admin_id() is None:
            return redirect(url_for("auth.admin_login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_role_required(*allowed_roles: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            aid = get_current_admin_id()
            if aid is None:
                return redirect(url_for("auth.admin_login"))
            db = get_db()
            admin_user = db.execute(
                "SELECT * FROM admin_users WHERE id = ?",
                (aid,),
            ).fetchone()
            if not admin_user:
                session.pop("admin_user_id", None)
                return redirect(url_for("auth.admin_login"))
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


def redirect_with_query(url: str, key: str, value: str) -> str:
    sep = "&" if ("?" in url) else "?"
    return f"{url}{sep}{key}={quote(value)}"
