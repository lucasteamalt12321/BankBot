"""
Metrics endpoint for monitoring.
Provides Prometheus-compatible metrics endpoint.
"""

import time
from flask import Flask, jsonify, Response
from database.database import get_db, User, Transaction

app = Flask(__name__)

_request_count = 0
_request_duration = 0.0


@app.route("/metrics")
def metrics():
    """Prometheus-compatible metrics endpoint."""
    global _request_count, _request_duration

    db = next(get_db())
    try:
        total_users = db.query(User).count()
        active_users = (
            db.query(User).filter(User.last_activity >= time.time() - 86400).count()
        )

        today = time.time() - 86400
        today_transactions = (
            db.query(Transaction).filter(Transaction.created_at >= today).count()
        )

        metrics_text = f"""# HELP bot_users_total Total number of users
# TYPE bot_users_total gauge
bot_users_total {total_users}

# HELP bot_active_users Users active in last 24 hours
# TYPE bot_active_users gauge
bot_active_users {active_users}

# HELP bot_transactions_total Total transactions
# TYPE bot_transactions_total counter
bot_transactions_total {today_transactions}

# HELP bot_http_requests_total HTTP requests
# TYPE bot_http_requests_total counter
bot_http_requests_total {_request_count}

# HELP bot_http_request_duration_seconds HTTP request duration
# TYPE bot_http_request_duration_seconds histogram
bot_http_request_duration_seconds_sum {_request_duration}
bot_http_request_duration_seconds_count {_request_count}
"""
        return Response(metrics_text, mimetype="text/plain")
    finally:
        db.close()


@app.route("/health")
def health():
    """Health check endpoint."""
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()
        return jsonify({"status": "healthy"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(__import__("os").getenv("METRICS_PORT", 9090)))
