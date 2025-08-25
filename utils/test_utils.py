import os, json, datetime as dt
from flask import current_app
from .storage import load_cards, save_cards
from .timeutil import _utcnow, _iso


def finalize_session(session_id: str, results: dict):
    """Finalize a test session: update card memory labels and user stats.

    Parameters
    ----------
    session_id: str
        ID của phiên test đã được tạo ở `/tests/start`.
    results: dict
        Mapping từ từ -> số lần trả lời sai.

    Returns
    -------
    tuple[label_summary, duration_sec, total_retakes]
        label_summary: dict tổng số từ vào mỗi nhãn bộ nhớ
        duration_sec: tổng thời gian làm bài tính bằng giây
        total_retakes: tổng số lần làm lại (số lần sai)
    """
    tests_dir = current_app.config["TESTS_DIR"]
    sess_path = os.path.join(tests_dir, f"{session_id}.json")
    if not os.path.isfile(sess_path):
        raise FileNotFoundError("session not found")

    with open(sess_path, "r", encoding="utf-8") as f:
        sess = json.load(f)
    sess["results"] = results
    with open(sess_path, "w", encoding="utf-8") as f:
        json.dump(sess, f, ensure_ascii=False, indent=2)

    data = load_cards()
    label_summary = {"LTM": 0, "STM": 0, "REVIEW": 0}
    for w in sess.get("picked_words", []):
        wrong = int(results.get(w, 0))
        label = "LTM" if wrong == 0 else ("STM" if wrong == 1 else "REVIEW")
        label_summary[label] += 1
        for c in data["cards"]:
            if c["word"].lower() == w.lower():
                c["memory_label"] = label
                c["updated_at"] = _iso(_utcnow())
                stats = c.get("stats") or {"correct": 0, "wrong": 0}
                if wrong == 0:
                    stats["correct"] = stats.get("correct", 0) + 1
                else:
                    stats["wrong"] = stats.get("wrong", 0) + 1
                c["stats"] = stats
    save_cards(data)

    total_retakes = sum(int(results.get(w, 0)) for w in sess.get("picked_words", []))
    start = sess.get("started_at")
    try:
        start_dt = dt.datetime.fromisoformat(start.replace("Z", "")) if start else None
        duration_sec = int((_utcnow() - start_dt).total_seconds()) if start_dt else None
    except Exception:
        duration_sec = None

    user_stats_path = current_app.config["USER_STATS_PATH"]
    if os.path.isfile(user_stats_path):
        with open(user_stats_path, "r", encoding="utf-8") as f:
            ustats = json.load(f)
    else:
        ustats = {"lessons": {}, "tests": []}
    ustats.setdefault("tests", []).append({
        "session_id": session_id,
        "started_at": start,
        "finished_at": _iso(_utcnow()),
        "duration_sec": duration_sec,
        "retakes": total_retakes,
        "results": {
            w: {
                "wrong": int(results.get(w, 0)),
                "label": "LTM" if int(results.get(w, 0)) == 0 else ("STM" if int(results.get(w, 0)) == 1 else "REVIEW"),
            }
            for w in sess.get("picked_words", [])
        },
    })
    with open(user_stats_path, "w", encoding="utf-8") as f:
        json.dump(ustats, f, ensure_ascii=False, indent=2)

    return label_summary, duration_sec, total_retakes
