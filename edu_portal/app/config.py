import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

DB_PATH = Path(__file__).resolve().parents[2] / "eduportal.db"

NEWS_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "static" / "uploads" / "news"
VAULT_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "vault"
