# routes\dictation.py
import os, uuid, json
from flask import Blueprint, current_app, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from services.alignment import tokenize_words, align_and_score
from services.text_normalizer import normalize_for_scoring
from services.stats_service import SpeedCalculator, ProgressTracker
from utils.timeutil import _utcnow, _iso

bp = Blueprint("dictation", __name__)

@bp.get("/")
def index():
    """
    Trang chủ: liệt kê bài học có sẵn và form tạo bài học mới.
    Đọc meta từng bài trong data/lessons/<id>/lesson.json và render templates/index.html
    """
    lessons = []
    lesson_dir = current_app.config["LESSON_DIR"]
    if os.path.isdir(lesson_dir):
        for d in sorted(os.listdir(lesson_dir), reverse=True):
            meta = os.path.join(lesson_dir, d, "lesson.json")
            if os.path.isfile(meta):
                with open(meta, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                    lessons.append({"id": obj["id"], "title": obj["title"], "created_at": obj["created_at"]})
    return render_template("index.html", lessons=lessons, title="Trang chủ")

@bp.post("/lessons/create")
def create_lesson():
    """
    Tạo bài học mới:
      - Lưu audio vào data/lessons/<uuid>/
      - Chuẩn hoá transcript tham chiếu (ưu tiên LLM nếu có key; fallback rule-based)
      - Ghi lesson.json
      - Redirect sang trang lesson/<id>
    """
    title = request.form.get("title", "Untitled").strip() or "Untitled"
    media = request.files.get("media")
    text = request.form.get("text", "")
    if not (media and text):
        return "Missing media or text", 400

    lid = str(uuid.uuid4())
    ldir = os.path.join(current_app.config["LESSON_DIR"], lid)
    os.makedirs(ldir, exist_ok=True)

    safe_name = secure_filename(media.filename) or f"media_{lid}"
    media_path_fs = os.path.join(ldir, safe_name)
    media.save(media_path_fs)

    llm = current_app.config["LLM_CLIENT"]
    if current_app.config["OPENAI_KEY"]:
        ref_norm = normalize_for_scoring(llm.normalize_text(text))
    else:
        ref_norm = normalize_for_scoring(text)

    rel_path = os.path.relpath(media_path_fs, current_app.config["BASE_DIR"]).replace("\\", "/")
    field = "video_path" if media.mimetype.startswith("video") else "audio_path"
    obj = {
        "id": lid,
        "title": title,
        field: rel_path,
        "text_original": text,
        "text_normalized": ref_norm,
        "n_ref_words": len(tokenize_words(ref_norm)),
        "created_at": _iso(_utcnow()),
        "attempts": [],
    }
    with open(os.path.join(ldir, "lesson.json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return redirect(url_for("dictation.lesson", id=lid))

@bp.get("/lesson/<id>")
def lesson(id: str):
    """
    Hiển thị trang bài học: audio player + textarea + nút kiểm tra.
    """
    meta = os.path.join(current_app.config["LESSON_DIR"], id, "lesson.json")
    if not os.path.isfile(meta):
        return "Not found", 404
    with open(meta, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return render_template("lesson.html", lesson=obj, title=obj["title"])

@bp.post("/lesson/<id>/start")
def lesson_start(id: str):
    """
    Bắt đầu 1 session 30': lưu vào bộ nhớ tạm app.extensions['active_sessions'].
    Trả về session_id + thời gian còn lại.
    """
    meta = os.path.join(current_app.config["LESSON_DIR"], id, "lesson.json")
    if not os.path.isfile(meta):
        return jsonify({"error": "lesson not found"}), 404

    now = _utcnow()
    expires = now + __import__("datetime").timedelta(minutes=current_app.config["MAX_MIN"])
    sid = str(uuid.uuid4())
    current_app.extensions["active_sessions"][id] = {"session_id": sid, "started_at": now, "expires_at": expires}
    return jsonify({
        "session_id": sid,
        "started_at": _iso(now),
        "expires_at": _iso(expires),
        "remaining_sec": int((expires - now).total_seconds()),
    })

@bp.post("/lesson/<id>/check")
def lesson_check(id: str):
    """
    Trong session đang chạy: tính WER và highlight tại chỗ (không lưu attempt).
    Chuẩn hoá văn bản theo luật (không dùng LLM) trước khi so sánh.
    """
    body = request.get_json(force=True)
    user_text = body.get("user_text", "")
    session_id = body.get("session_id")
    sess = current_app.extensions["active_sessions"].get(id)

    if not sess or sess.get("session_id") != session_id:
        return jsonify({"error": "no active session"}), 400

    now = _utcnow()
    if now >= sess["expires_at"]:
        return jsonify({"error": "session expired"}), 400

    meta = os.path.join(current_app.config["LESSON_DIR"], id, "lesson.json")
    if not os.path.isfile(meta):
        return jsonify({"error": "lesson not found"}), 404
    with open(meta, "r", encoding="utf-8") as f:
        obj = json.load(f)

    ref = normalize_for_scoring(obj.get("text_normalized") or obj.get("text_original", ""))
    hyp = normalize_for_scoring(user_text)

    ref_toks = tokenize_words(ref)
    hyp_toks = tokenize_words(hyp)

    ar = align_and_score(ref_toks, hyp_toks)

    spans = []
    for op, rt, ht in ar.ops:
        if op == "M":
            spans.append({"token": ht, "status": "correct", "correct": ht})
        elif op == "S":
            spans.append({"token": ht, "status": "wrong", "correct": rt})
        elif op == "I":
            spans.append({"token": ht, "status": "wrong", "correct": ""})
        elif op == "D":
            spans.append({"token": "_", "status": "missing", "correct": rt})

    correct = sum(1 for op, _, _ in ar.ops if op == "M")
    wrong = sum(1 for op, _, _ in ar.ops if op in ("S", "I"))
    missing = sum(1 for op, _, _ in ar.ops if op == "D")

    elapsed = (now - sess["started_at"]).total_seconds()
    duration = min(elapsed, current_app.config["MAX_MIN"] * 60)
    speed = SpeedCalculator.compute(correct, wrong, missing, duration)

    stats = {
        "n_ref_words": len(ref_toks), "n_hyp_words": len(hyp_toks),
        "S": ar.S, "D": ar.D, "I": ar.I, "WER": ar.WER,
        "speed_score": speed, "improvement_pct": 0.0, "duration_sec": duration
    }
    return jsonify({"stats": stats, "spans": spans})

@bp.post("/lesson/<id>/finalize")
def lesson_finalize(id: str):
    """
    Kết thúc session: lưu attempt vào lesson.json và trả lại đáp án đã chuẩn hoá.
    Việc chuẩn hoá chỉ dùng luật, không gọi LLM.
    """
    body = request.get_json(force=True)
    user_text = body.get("user_text", "")
    session_id = body.get("session_id")
    sess = current_app.extensions["active_sessions"].get(id)

    if not sess or sess.get("session_id") != session_id:
        return jsonify({"error": "no active session"}), 400

    meta = os.path.join(current_app.config["LESSON_DIR"], id, "lesson.json")
    if not os.path.isfile(meta):
        return jsonify({"error": "lesson not found"}), 404
    with open(meta, "r", encoding="utf-8") as f:
        obj = json.load(f)

    ref = normalize_for_scoring(obj.get("text_normalized") or obj.get("text_original", ""))
    hyp = normalize_for_scoring(user_text)

    ref_toks = tokenize_words(ref)
    hyp_toks = tokenize_words(hyp)
    ar = align_and_score(ref_toks, hyp_toks)

    correct = sum(1 for op, _, _ in ar.ops if op == "M")
    wrong = sum(1 for op, _, _ in ar.ops if op in ("S", "I"))
    missing = sum(1 for op, _, _ in ar.ops if op == "D")

    now = _utcnow()
    elapsed = (now - sess["started_at"]).total_seconds()
    duration = min(elapsed, current_app.config["MAX_MIN"] * 60)
    speed = SpeedCalculator.compute(correct, wrong, missing, duration)

    prev_wer = obj["attempts"][-1]["stats"]["WER"] if obj.get("attempts") else None
    improvement = ProgressTracker.compute_improvement(prev_wer, ar.WER) if prev_wer is not None else 0.0

    attempt = {
        "attempt_id": str(uuid.uuid4()),
        "started_at": _iso(sess["started_at"]),
        "ended_at": _iso(min(now, sess["expires_at"])),
        "duration_sec": duration,
        "stats": {
            "n_ref_words": len(ref_toks), "n_hyp_words": len(hyp_toks),
            "S": ar.S, "D": ar.D, "I": ar.I, "WER": ar.WER,
            "speed_score": speed, "improvement_pct": improvement
        },
    }
    obj.setdefault("attempts", []).append(attempt)
    with open(meta, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

    current_app.extensions["active_sessions"].pop(id, None)
    return jsonify({"message": "finalized", "answer": ref, "stats": attempt["stats"]})
