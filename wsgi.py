"""WSGI entry point for long-running hosts (RelaxDev/gunicorn)."""

from api.index import app

__all__ = ["app"]
