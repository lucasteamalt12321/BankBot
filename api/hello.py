from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "status": "ok",
        "message": "Python functions work!",
        "service": "LTHub API"
    })

# Vercel handler
handler = app
