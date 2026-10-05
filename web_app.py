import logging
import os
from flask import Flask, render_template, request, jsonify
from pipeline import run_and_deliver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400

    result = run_and_deliver(to_email=email)
    return jsonify(result), 200 if result["ok"] else 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  AI Weekly Digest is running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
