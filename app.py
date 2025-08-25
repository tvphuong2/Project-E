import os, json, uuid, yaml
from flask import Flask, send_from_directory
from services.llm_service import LLMClient
from services.image_service import ImageFetcher
from services.tts_service import TTSService

def create_app():
    BASE = os.path.dirname(__file__)
    CONF_PATH = os.path.join(BASE, "config.yaml")
    CONF = {}
    if os.path.isfile(CONF_PATH):
        with open(CONF_PATH, "r", encoding="utf-8") as f:
            CONF = yaml.safe_load(f) or {}

    app = Flask(__name__)

    # ---- App config (đường dẫn & tham số) ----
    app.config.update(
        BASE_DIR=BASE,
        DATA_DIR=os.path.join(BASE, "data"),
        LESSON_DIR=os.path.join(BASE, "data", "lessons"),
        CARDS_DIR=os.path.join(BASE, "data", "cards"),
        TESTS_DIR=os.path.join(BASE, "data", "tests"),
        USER_STATS_PATH=os.path.join(BASE, "data", "user_stats.json"),
        OPENAI_KEY=CONF.get("openai", {}).get("api_key"),
        OPENAI_MODEL=CONF.get("openai", {}).get("model", "gpt-4o-mini"),
        G_CSE_KEY=CONF.get("google_cse", {}).get("api_key"),
        G_CSE_CX=CONF.get("google_cse", {}).get("cx"),
        MAX_MIN=int(CONF.get("app", {}).get("max_attempt_duration_min", 30)),
        TEST_WORD_COUNT=int(CONF.get("app", {}).get("test_word_count", 10)),
        ANSWER_REVEAL_MS=int(CONF.get("app", {}).get("answer_reveal_ms", 1200)),
        OPENAI_TTS_MODEL=CONF.get("openai", {}).get("tts_model", "gpt-4o-mini-tts"),
        ENABLED_EXERCISE_TYPES=CONF.get("app", {}).get("enabled_exercise_types", []),
    )

    # ---- Clients (LLM / Image) ----
    app.config["LLM_CLIENT"] = LLMClient(
        api_key=app.config["OPENAI_KEY"],
        model=app.config["OPENAI_MODEL"]
    )
    app.config["IMG_FETCHER"] = ImageFetcher(
        api_key=app.config["G_CSE_KEY"],
        cx=app.config["G_CSE_CX"]
    )
    app.config["TTS_CLIENT"] = TTSService(
        api_key=app.config["OPENAI_KEY"],
        model=app.config["OPENAI_TTS_MODEL"]
    )

    # ---- Active session store (in-memory) ----
    app.extensions["active_sessions"] = {}  # {lesson_id: {session_id, started_at, expires_at}}

    # ---- Bootstrap dữ liệu & file ----
    from utils.storage import bootstrap_data_dirs
    bootstrap_data_dirs(app)

    # ---- Blueprints ----
    from routes.dictation import bp as dictation_bp
    from routes.vocab_test import bp as vocab_test_bp
    app.register_blueprint(dictation_bp)
    app.register_blueprint(vocab_test_bp)

    # ---- Static serving cho /data (audio/images) ----
    @app.route("/data/<path:path>")
    def serve_data(path: str):
        full = os.path.join(app.config["DATA_DIR"], path)
        directory = os.path.dirname(full)
        filename = os.path.basename(full)
        return send_from_directory(directory, filename, as_attachment=False)

    return app

# Entrypoint
if __name__ == "__main__":
    app = create_app()
    host = "127.0.0.1"
    port = 5000
    debug = True
    try:
        import yaml
        with open(os.path.join(app.config["BASE_DIR"], "config.yaml"), "r", encoding="utf-8") as f:
            CONF = yaml.safe_load(f) or {}
        host = CONF.get("app", {}).get("host", host)
        port = int(CONF.get("app", {}).get("port", port))
        debug = bool(CONF.get("app", {}).get("debug", debug))
    except Exception:
        pass
    app.run(host=host, port=port, debug=debug)
