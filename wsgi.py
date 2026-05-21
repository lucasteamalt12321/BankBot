"""WSGI entry point for Render (gunicorn)."""
from app import create_app

app = create_app()
