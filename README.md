# EduPortal (Flask + SQLite)

A student portal demo built with **Flask** and **SQLite**, with DB-driven dashboard/news/library/profile pages.

## Features
- Dashboard with DB-backed news + attendance heatmap
- News feed with filters
- Schedules + calendar UI
- Exams: admit card + semester results print views
- Library: resources from DB with **PDF links** (external URLs or uploaded PDFs)

## Project Structure
- `app.py` Flask app + DB schema + seed data
- `templates/` Jinja2 templates
- `static/` static assets
- `eduportal.db` is created locally (ignored by git)

## Note about `index.html`
There is a root `index.html` in this repo that can be treated as a legacy/static prototype.
The Flask app uses `templates/` for rendering pages and does not serve the root `index.html` as an application route.

## Requirements
- Python 3.10+ recommended

Install deps:
```bash
pip install -r requirements.txt
```

## Run (development)
```bash
python app.py
```

Environment variables (optional):
- `SECRET_KEY`
- `DEBUG` or `FLASK_DEBUG` (set to `1` / `true`)
- `HOST` (default `127.0.0.1`)
- `PORT` (default `5000`)

## Run (production-style with Waitress)
```bash
python wsgi.py
```

Environment variables (optional):
- `HOST` (default `0.0.0.0`)
- `PORT` (default `8000`)

## Library PDF uploads
- Uploads are saved to: `static/uploads/`
- DB stores either:
  - an external URL (starting with `http://` or `https://`), or
  - a relative local path like `uploads/<file>.pdf` (served from `/static/uploads/...`)

## Notes for Git
- Your local virtualenv folder `edu_portal/` is ignored.
- Your local SQLite DB `*.db` is ignored.
- User uploaded PDFs under `static/uploads/` are ignored.

If you want to ship a demo DB with seed data, create an explicit seed/export file instead of committing `eduportal.db`.
