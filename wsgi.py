import os

from app import app, init_db


init_db()


if __name__ == "__main__":
    from waitress import serve

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    serve(app, host=host, port=port)
