from flask import Flask, jsonify, render_template
import backend.state as state
from backend.db import get_conn, init_db, get_session_history, get_session, get_session_readings
from backend.config import DB_PATH

def create_app(db_path: str = DB_PATH) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    conn = get_conn(db_path)
    init_db(conn)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def api_status():
        return jsonify(state.get_state())

    @app.get("/api/session/current")
    def api_session_current():
        return jsonify(state.get_session_state())

    @app.get("/api/session/history")
    def api_session_history():
        return jsonify(get_session_history(conn))

    @app.get("/api/session/<session_id>")
    def api_session_detail(session_id):
        session = get_session(conn, session_id)
        if session is None:
            return jsonify({"error": "not found"}), 404
        readings = get_session_readings(conn, session_id)
        return jsonify({"session": session, "readings": readings})

    @app.post("/api/zero")
    def api_zero():
        state.request_zero()
        return jsonify({"ok": True})

    return app
