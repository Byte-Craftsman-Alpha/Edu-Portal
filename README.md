# EduPortal (Flask + SQLite)

EduPortal is a student portal + admin panel built with **Flask** and **SQLite**.

It includes a student-facing portal (dashboard/news/schedules/exams/library/profile) and an admin dashboard (students, news, schedules, exam forms, admit card windows, teachers, etc.).

This repository is designed to be **easy to run locally** and includes a script to generate a full dummy database for end-to-end testing.

---

## Tech Stack

- **Backend**: Python + Flask
- **Database**: SQLite (`eduportal.db`)
- **Server (optional production-style)**: Waitress (`wsgi.py`)
- **Frontend**: Jinja2 templates + Tailwind (CDN)

---

## Requirements

- Python **3.10+** recommended

Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt`:

- Flask
- waitress

---

## Quick Start (Development)

1) Install dependencies

```bash
pip install -r requirements.txt
```

2) Run the app

```bash
python app.py
```

3) Open in browser

- Student portal: `http://127.0.0.1:5000/`
- Admin portal: `http://127.0.0.1:5000/admin`

---

## Production-style Run (Waitress)

```bash
python wsgi.py
```

Defaults:

- `HOST=0.0.0.0`
- `PORT=8000`

---

## Environment Variables

- `SECRET_KEY`
  - Flask session secret.
  - If not set, defaults to a dev key.
- `HOST`
  - Dev default: `127.0.0.1`
  - Waitress default: `0.0.0.0`
- `PORT`
  - Dev default: `5000`
  - Waitress default: `8000`
- `DEBUG` / `FLASK_DEBUG`
  - Set to `1` or `true` to enable debug.

---

## Database

### Location

By default the app uses:

- `eduportal.db` (next to `app.py`)

The DB is created automatically at runtime.

### Schema and migrations

The DB schema is maintained in:

- `app.py` → `init_db()`

`init_db()`:

- creates tables (if missing)
- applies small schema migrations (adds columns if required)
- inserts baseline demo rows if the database is empty

---

## Dummy Database Generator (Recommended for full testing)

To test the entire project with realistic data, generate a full dummy DB using:

```bash
python seed_dummy_db.py --force
```

What it does:

- recreates `eduportal.db`
- runs `init_db()` to create schema
- inserts multiple dummy rows across major tables (students, schedules, timetable, library, exams, etc.)

Flags:

- `--force`: overwrite existing DB
- `--db <path>`: generate DB to a custom path

Example:

```bash
python seed_dummy_db.py --db demo.db --force
```

---

## Default Credentials

### Admin

- URL: `/admin`
- Username: `admin`
- Password: `admin123`

### Students

Seeded students exist in the DB (created by `init_db()` / `seed_dummy_db.py`).

- Password: `student123`
- Example roll numbers:
  - `CS-2024-042`
  - `CS-2024-043`
  - `CS-2024-044`
  - `CS-2024-045`

---

## Core Features

### Student Portal

- **Dashboard**
  - overview widgets
  - attendance heatmap
  - news highlights
- **News**
  - DB-backed feed
  - priority-based items
- **Schedules**
  - personalized **weekly timetable** based on the student’s `schedule_id`
  - global **monthly events & holidays** (`calendar_items`)
  - calendar view
- **Exams**
  - semester results view
  - admit card view
  - exam form availability + application links (if open)
- **Library**
  - resources list with search and filters
  - PDF resources via:
    - external URL
    - uploaded file under `static/uploads/`
- **Profile**
  - student details + profile data

### Admin Panel

- **Dashboard**: counts + quick overview
- **Students**: view / edit / delete student records (includes cleanup of related rows and uploaded vault files)
- **News**: create / edit / delete posts
- **Schedules**:
  - manage global monthly events/holidays
  - manage weekly timetable per schedule group
- **Exam Forms**:
  - open/close windows
  - delete forms
  - manage admit card openings
- **Teachers**: add / delete teachers

---

## `schedule_id` and Personalized Timetable

- `schedule_groups` table defines schedule groups (e.g., *B.Tech CSE Sem-4 Section A*).
- Each student row has `students.schedule_id`.
- Weekly timetable rows are stored in `weekly_timetable` and linked by `schedule_id`.

During registration, a student selects their **Weekly Schedule** (schedule group).
The portal then shows the timetable for that schedule group.

---

## Library PDF Uploads

- Uploads are saved to:
  - `static/uploads/`

The DB stores `library_resources.pdf_url` as either:

- External URL (starts with `http://` / `https://`), or
- Local relative path such as `uploads/<file>.pdf` (served via `/static/uploads/...`)

---

## Project Documentation

### Core Files
- `README.md` – Project overview, setup, and feature list
- `requirements.txt` – Python dependencies
- `.env.example` – Environment variable template
- `app.py` – Main Flask application (routes, DB schema, auth)
- `wsgi.py` – Production server entry (Waitress)
- `seed_dummy_db.py` – Dummy data generator for testing

### Templates
- `templates/base.html` – Base layout for student portal (includes Iconify, Tailwind)
- `templates/admin_base.html` – Base layout for admin panel
- `templates/*.html` – Page templates (dashboard, news, schedules, library, vault, exams, profile, admin pages)

### Static Assets
- `static/app.js` – Shared client-side interactions
- `static/app_icon/logo.png` – Logo used in UI
- `static/uploads/` – Runtime uploads (news attachments, library PDFs) – **do not commit**
- `uploads/vault/` – Student vault files – **do not commit**

### Database
- `eduportal.db` – SQLite database (auto-created) – **do not commit**

---

## Uploading to Git (What to Include/Exclude)

### Include
- All source files (`*.py`, `templates/`, `static/` except runtime uploads)
- `README.md`, `requirements.txt`, `.env.example`
- Documentation files (if any)
- `static/app_icon/logo.png` and other static assets
- Any custom CSS/JS under `static/` that are part of the app

### Exclude (already in `.gitignore` or should be)
- `*.db` (SQLite databases)
- `uploads/` and `static/uploads/` (user uploads)
- `.env` (environment secrets)
- `__pycache__/`, `*.pyc`
- IDE/editor files (`.vscode/`, `.idea/`, etc.)
- OS-generated files (`.DS_Store`, `Thumbs.db`)
- Temporary files and logs

### Tip
- Use `seed_dummy_db.py --force` to generate a fresh demo DB after cloning.
- Never commit real user data or production databases.

---

## Project Structure

- `app.py`
  - Flask routes
  - DB schema + migrations (`init_db()`)
- `wsgi.py`
  - Waitress entrypoint
  - calls `init_db()` on startup
- `seed_dummy_db.py`
  - generates a fresh demo DB for complete testing
- `templates/`
  - Jinja templates for student + admin UIs
- `static/`
  - static assets

---

## Notes about `index.html`

There is a root `index.html` in this repo that can be treated as a legacy/static prototype.

The Flask app uses `templates/` for rendering pages and does not serve the root `index.html` as an application route.

---

## Troubleshooting

### 1) “Database locked”

- Stop all running instances of the app.
- Ensure the DB file isn’t opened by another process.

### 2) Seeding errors

If you want a clean reset:

```bash
python seed_dummy_db.py --force
```

### 3) Uploaded PDFs not found

- Check the file exists under `static/uploads/`
- Verify the DB value is either:
  - a full external URL, or
  - a relative path `uploads/<file>.pdf`

---

## Git Notes

- Local DB files `*.db` are ignored
- User uploads under `static/uploads/` are ignored

If you want to distribute a demo DB, use `seed_dummy_db.py` rather than committing a `.db` file.
