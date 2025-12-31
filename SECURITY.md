# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately before disclosing it publicly.

### How to Report
- Send an email to: [INSERT SECURITY EMAIL]
- Include as much detail as possible:
  - Type of vulnerability
  - Steps to reproduce (if applicable)
  - Potential impact
  - Any proof-of-concept code (if safe to share)

### What to Expect
- We will acknowledge receipt within 48 hours
- We'll provide a detailed response within 7 days
- We'll notify you when a fix is released
- We'll credit you in the release notes (if you wish)

### Guidelines
- Do not open public issues for security vulnerabilities
- Do not exploit the vulnerability
- Provide responsible disclosure

## Security Best Practices for Deployments

- Change default admin credentials
- Use a strong `SECRET_KEY`
- Run in production using `wsgi.py` behind a reverse proxy
- Keep dependencies up to date
- Regularly backup the database
- Do not commit `.env` or real databases to version control

Thank you for helping keep EduPortal safe!
