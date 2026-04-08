"""WSGI entry point – initialises DB on cold start."""
import db
db.init_db()

from app import app  # noqa: E402  (import after init)

if __name__ == "__main__":
    app.run()
