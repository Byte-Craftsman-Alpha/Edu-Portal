# Contributing to EduPortal

Thank you for your interest in contributing to EduPortal! This document provides guidelines and steps to help you get started.

## Getting Started

### Prerequisites
- Python 3.10+ recommended
- Git

### Setup
1. Fork the repository
2. Clone your fork locally
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and adjust values as needed
5. Generate a dummy database for testing:
   ```bash
   python seed_dummy_db.py --force
   ```
6. Run the app:
   ```bash
   python app.py
   ```

## How to Contribute

### Reporting Bugs
- Use the issue tracker
- Include steps to reproduce, expected vs actual behavior
- Attach screenshots if relevant

### Suggesting Features
- Open an issue with the "enhancement" label
- Describe the use case and why it would be valuable

### Making Changes
1. Create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Test thoroughly:
   - Run the app locally
   - Test both student and admin panels
   - Verify database migrations (if any)
4. Commit with a clear message
5. Push to your fork and open a pull request

### Code Style
- Follow PEP 8
- Use meaningful variable/function names
- Add comments for complex logic
- Keep templates readable and consistent with existing style

### Database Changes
- Schema changes should be added to `init_db()` in `app.py`
- Include migration logic (e.g., `ALTER TABLE` if column missing)
- Document any breaking changes

### Templates & UI
- Use existing CSS classes from `base.html` / `admin_base.html`
- Keep responsive design in mind
- Use Iconify for icons (match existing naming)

## Pull Request Process

- Ensure your PR description clearly describes the change
- Link to any related issues
- Request review from maintainers
- Keep the PR focused and reasonably sized

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Feel free to open an issue or ask in discussions. We're happy to help!
