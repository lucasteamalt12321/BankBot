from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "status": "ok",
        "message": "Python functions work!",
        "service": "BankBot API"
    })

# Vercel handler
handler = app
