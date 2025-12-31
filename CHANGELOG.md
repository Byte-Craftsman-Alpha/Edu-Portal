# Changelog

All notable changes to EduPortal will be documented in this file.

## [Unreleased]

### Added
- Admin can edit and delete student records (including cleanup of related rows and vault files)
- Fixed advanced filter icon/toggle on student News page
- Improved admin News header alignment (search + New Post button)
- Updated README with project documentation and Git upload checklist
- Added LICENSE, CODE_OF_CONDUCT.md, CONTRIBUTING.md, SECURITY.md, CHANGELOG.md, PROJECT_OVERVIEW.md
- GitHub-style navigation progress bar for smooth page transitions
- Enhanced news advanced filters (priority, type, sender, tags, date range)

### Changed
- Improved UI consistency across admin panels

### Fixed
- Advanced filter dropdown not opening/icon missing on student News page
- Admin News header misalignment between search and New Post button

---

## [1.0.0] - Initial Release

### Features
- Student portal: dashboard, news, schedules, library, vault, exams, profile
- Admin panel: dashboard, students (view/edit/delete), news (create/edit/delete), schedules, exam forms, admit card openings, teachers
- SQLite database with automatic schema migrations
- Dummy data generator (`seed_dummy_db.py`)
- Responsive UI with Tailwind CSS and Iconify icons
- Production-ready Waitress server (`wsgi.py`)
