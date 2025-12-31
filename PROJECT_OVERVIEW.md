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

- **Student Portal**: Dashboard, news, schedules, library, vault, exams, profile
- **Admin Panel**: Manage students, news, schedules, exam forms, admit cards, teachers
- **Tech Stack**: Python + Flask, SQLite, Tailwind CSS, Iconify
- **Features**: Responsive design, dummy data generator, production-ready server

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
