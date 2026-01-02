import re
from pathlib import Path

from edu_portal.app import create_app


def main() -> int:
    app = create_app()

    tmpl_root = Path(__file__).resolve().parent / "templates"
    pat = re.compile(r"url_for\(\s*['\"]student\.([^'\"]+)['\"]")

    refs: dict[str, set[str]] = {}
    for p in tmpl_root.rglob("*.html"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(txt):
            ep = f"student.{m.group(1)}"
            refs.setdefault(ep, set()).add(str(p.relative_to(tmpl_root)))

    endpoints = {r.endpoint for r in app.url_map.iter_rules()}

    missing = sorted([ep for ep in refs if ep not in endpoints])

    print(f"Student endpoints referenced in templates: {len(refs)}")
    print(f"Student endpoints registered in app: {len([e for e in endpoints if e.startswith('student.')])}")

    print(f"\nMissing endpoints (referenced but not registered): {len(missing)}")
    for ep in missing:
        files = ", ".join(sorted(refs.get(ep, [])))
        print(f"- {ep} <= {files}")

    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
