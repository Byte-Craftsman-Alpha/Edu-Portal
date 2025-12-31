# EduPortal

EduPortal is a student portal + admin panel built with Flask and SQLite.

## Quick Links

- [Documentation](README.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

## Overview

- **Student Portal**: Dashboard, news (with advanced filters), schedules, library, vault, exams, profile
- **Admin Panel**: Manage students, news, schedules, exam forms, admit cards, teachers
- **Tech Stack**: Python + Flask, SQLite, Tailwind CSS, Iconify
- **Features**: Responsive design, dummy data generator, production-ready server
- **UX**: GitHub-style navigation progress bar for smooth transitions

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy environment variables:
   ```bash
   cp .env.example .env
   # Edit .env as needed
   ```

3. Generate demo data:
   ```bash
   python seed_dummy_db.py --force
   ```

4. Run the app:
   ```bash
   python app.py
   ```

5. Open in browser:
   - Student portal: http://127.0.0.1:5000/
   - Admin portal: http://127.0.0.1:5000/admin

## Default Credentials

- Admin: username `admin`, password `admin123`
- Students: roll numbers `CS-2024-042`, `CS-2024-043`, etc., password `student123`

## Recent Improvements

- **Admin Features**: Full CRUD operations for students, news management with advanced search
- **UI/UX**: GitHub-style navigation progress bar, improved header alignments, enhanced filters
- **Documentation**: Complete open-source files (LICENSE, CODE_OF_CONDUCT, CONTRIBUTING, SECURITY)
- **Git Ready**: Comprehensive README with project documentation and upload checklist

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
