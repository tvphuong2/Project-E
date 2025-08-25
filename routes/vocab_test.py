# routes\vocab_test.py
import uuid, re
import os
from flask import Blueprint, current_app, render_template, request, jsonify
from services.llm_service import LLMClient
from services.image_service import ImageFetcher
from services.tts_service import TTSService
from services.test_generator import WordSampler, ExerciseBuilder
from utils.storage import load_cards, save_cards, ensure_card_ids
from utils.timeutil import _utcnow, _iso

bp = Blueprint("vocab_test", __name__)

# ---------- ÔN TỪ ----------
@bp.get("/vocab")
def vocab_page():
    "Trang Ôn từ: giao diện danh sách + panel chi tiết (templates/vocab.html)."
    return render_template("vocab.html", title="Ôn từ mới")

@bp.get("/vocab/summary")
def vocab_summary():
    "Tóm tắt thẻ: đếm theo status & memory_label; trả cả danh sách thẻ."
    ensure_card_ids()
    data = load_cards()
    counts = {"raw": 0, "enrich": 0, "additional": 0, "LTM": 0, "STM": 0, "REVIEW": 0}
    for c in data["cards"]:
        s = (c.get("status") or "").lower()
        if s == "raw": counts["raw"] += 1
        if s == "enrich": counts["enrich"] += 1
        if s == "additional": counts["additional"] += 1
        mem = (c.get("memory_label") or "").upper()
        if mem == "LTM": counts["LTM"] += 1
        if mem == "STM": counts["STM"] += 1
        if mem in ("", "REVIEW") or not mem: counts["REVIEW"] += 1
    return jsonify({"counts": counts, "cards": data["cards"]})

@bp.get("/vocab/card/<id_or_word>")
def vocab_card_detail(id_or_word):
    "Lấy chi tiết 1 thẻ theo id; nếu không thấy thì thử theo word (không phân biệt hoa/thường)."
    ensure_card_ids()
    key = (id_or_word or "").strip()
    data = load_cards()
    for c in data["cards"]:
        if str(c.get("id", "")).strip() == key:
            return jsonify(c)
    for c in data["cards"]:
        if str(c.get("word", "")).strip().lower() == key.lower():
            return jsonify(c)
    return jsonify({"error": "not found"}), 404

@bp.post("/vocab/save_selection")
def vocab_save_selection():
    """
    Lưu một từ mới từ phần bôi đen:
      - Chuẩn hoá token (loại bỏ 's, lấy token chữ dài nhất, giữ gạch nối)
      - Tránh trùng (case-insensitive)
      - Tùy chọn enrich ngay nếu payload.enrich_now = true
    """
    ensure_card_ids()
    payload = request.get_json(force=True, silent=True) or {}
    raw = (payload.get("word") or payload.get("text") or "").strip()
    if not raw:
        return jsonify({"ok": False, "error": "empty_input"}), 400

    def canonicalize(text: str) -> str:
        t = (text or "").strip()
        t = t.replace("’", "'").replace("‘","'").replace("“", '"').replace("”", '"')
        t = re.sub(r"'s\\b", "", t, flags=re.IGNORECASE)
        import re as _re
        tokens = _re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", t)
        if not tokens: return ""
        return max(tokens, key=len).lower().strip("-")

    word = canonicalize(raw)
    if not word or len(word) < 2 or len(word) > 40:
        return jsonify({"ok": False, "error": "invalid_word", "input": raw, "normalized": word}), 400

    data = load_cards()
    if any((c.get("word","").lower() == word.lower()) for c in data["cards"]):
        # Đã có
        card = next(c for c in data["cards"] if c.get("word","").lower() == word.lower())
        return jsonify({"ok": True, "message": "Đã có trong bộ thẻ", "card": card})

    now = _iso(_utcnow())
    card = {
        "id": str(uuid.uuid4()), "word": word.capitalize(),
        "status": "raw", "origin": "manual",
        "pos": "", "meaning_vi": "", "usage": "", "phonetic": "",
        "image_url": None,
        "audio_url": None,
        "created_at": now, "updated_at": now,
        "memory_label": "", "stats": {"correct": 0, "wrong": 0}
    }

    if bool(payload.get("enrich_now")):
        llm: LLMClient = current_app.config["LLM_CLIENT"]
        img = current_app.config["IMG_FETCHER"]
        tts: TTSService = current_app.config["TTS_CLIENT"]
        try:
            desc = llm.describe_word(card["word"]) if current_app.config["OPENAI_KEY"] else {}
            card["pos"] = desc.get("pos",""); card["meaning_vi"] = desc.get("meaning_vi","")
            card["usage"] = desc.get("usage",""); card["phonetic"] = desc.get("phonetic","")
            card["image_url"] = img.fetch(card["word"]) if (current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]) else None
            if current_app.config["OPENAI_KEY"]:
                aud_path = os.path.join(current_app.config["CARDS_DIR"], "audio", f"{card['id']}.mp3")
                if tts.synthesize(card["word"], aud_path):
                    card["audio_url"] = f"/data/cards/audio/{card['id']}.mp3"
            card["status"] = "enrich"; card["updated_at"] = _iso(_utcnow())
        except Exception:
            pass

    data["cards"].append(card)
    save_cards(data)
    return jsonify({"ok": True, "message": "Đã lưu từ", "card": card})

@bp.post("/vocab/enrich_all")
def vocab_enrich_all():
    """
    Enrich tất cả thẻ RAW:
      - điền pos/meaning_vi/usage/phonetic bằng LLM (nếu có key)
      - lấy 1 ảnh (nếu có Google CSE)
      - sinh 'additional' (confusable) và cũng enrich đầy đủ
    """
    ensure_card_ids()
    data = load_cards()
    llm: LLMClient = current_app.config["LLM_CLIENT"]
    img: ImageFetcher = current_app.config["IMG_FETCHER"]
    tts: TTSService = current_app.config["TTS_CLIENT"]

    changed = 0
    now = _iso(_utcnow())
    for c in list(data["cards"]):
        if (c.get("status") or "").lower() == "raw":
            desc = llm.describe_word(c["word"]) if current_app.config["OPENAI_KEY"] else {"pos":"", "meaning_vi":"", "usage":"", "phonetic":""}
            c.update({
                "word": c.get("word","").capitalize(),
                "pos": desc.get("pos",""),
                "meaning_vi": desc.get("meaning_vi",""),
                "usage": desc.get("usage",""),
                "phonetic": desc.get("phonetic",""),
                "image_url": img.fetch(c["word"]) if (current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]) else None,
                "audio_url": None,
                "status": "enrich", "updated_at": now
            })
            if current_app.config["OPENAI_KEY"]:
                aud_path = os.path.join(current_app.config["CARDS_DIR"], "audio", f"{c['id']}.mp3")
                if tts.synthesize(c["word"], aud_path):
                    c["audio_url"] = f"/data/cards/audio/{c['id']}.mp3"
            changed += 1

            similars = llm.generate_similar_or_confusables(c["word"]) if current_app.config["OPENAI_KEY"] else []
            for s in similars:
                if not any(x["word"].lower() == s.lower() for x in data["cards"]):
                    desc2 = llm.describe_word(s) if current_app.config["OPENAI_KEY"] else {"pos":"", "meaning_vi":"", "usage":"", "phonetic":""}
                    img2 = img.fetch(s) if (current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]) else None
                    new_id = str(uuid.uuid4())
                    audio_url = None
                    if current_app.config["OPENAI_KEY"]:
                        aud_path2 = os.path.join(current_app.config["CARDS_DIR"], "audio", f"{new_id}.mp3")
                        if tts.synthesize(s, aud_path2):
                            audio_url = f"/data/cards/audio/{new_id}.mp3"
                    data["cards"].append({
                        "id": new_id, "word": s.capitalize(),
                        "status": "additional", "origin": "auto_additional",
                        "pos": desc2.get("pos",""), "meaning_vi": desc2.get("meaning_vi",""),
                        "usage": desc2.get("usage",""), "phonetic": desc2.get("phonetic",""),
                        "image_url": img2,
                        "audio_url": audio_url,
                        "created_at": now, "updated_at": now,
                        "memory_label": "", "stats": {"correct": 0, "wrong": 0}
                    })
    save_cards(data)
    return jsonify({"message": f"Enriched {changed} raw cards (including additional w/ details)"})


@bp.post("/vocab/fill_missing/<id_or_word>")
def vocab_fill_missing(id_or_word):
    """Fill missing fields (meaning, pos, image, audio) for a single card."""
    ensure_card_ids()
    key = (id_or_word or "").strip()
    data = load_cards()
    card = None
    for c in data["cards"]:
        if str(c.get("id")) == key or str(c.get("word", "")).lower() == key.lower():
            card = c
            break
    if not card:
        return jsonify({"error": "not found"}), 404

    llm: LLMClient = current_app.config["LLM_CLIENT"]
    img: ImageFetcher = current_app.config["IMG_FETCHER"]
    tts: TTSService = current_app.config["TTS_CLIENT"]
    updated = False
    now = _iso(_utcnow())

    try:
        if current_app.config["OPENAI_KEY"] and (not card.get("pos") or not card.get("meaning_vi") or not card.get("usage") or not card.get("phonetic")):
            desc = llm.describe_word(card["word"])
            card["pos"] = card.get("pos") or desc.get("pos", "")
            card["meaning_vi"] = card.get("meaning_vi") or desc.get("meaning_vi", "")
            card["usage"] = card.get("usage") or desc.get("usage", "")
            card["phonetic"] = card.get("phonetic") or desc.get("phonetic", "")
            updated = True
    except Exception:
        pass

    if not card.get("image_url") and current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]:
        try:
            card["image_url"] = img.fetch(card["word"])
            if card["image_url"]:
                updated = True
        except Exception:
            pass

    if not card.get("audio_url") and current_app.config["OPENAI_KEY"]:
        aud_path = os.path.join(current_app.config["CARDS_DIR"], "audio", f"{card['id']}.mp3")
        if tts.synthesize(card["word"], aud_path):
            card["audio_url"] = f"/data/cards/audio/{card['id']}.mp3"
            updated = True

    if updated:
        card["updated_at"] = now
        save_cards(data)

    return jsonify({"card": card, "updated": updated})


# ---------- BÀI TEST ----------
@bp.get("/test")
def get_test_page():
    "Trang bắt đầu bài test ôn từ (templates/test.html)."
    k = current_app.config.get("TEST_WORD_COUNT", 10)
    ans = current_app.config.get("ANSWER_REVEAL_MS", 1200)
    return render_template("test.html", title="Test từ vựng", test_word_count=k, answer_ms=ans)

@bp.post("/tests/start")
def start_tests():
    "Chọn số từ theo tỉ lệ 5/30/65, sinh bài tập."
    data = load_cards()
    k = current_app.config.get("TEST_WORD_COUNT", 10)
    picked = WordSampler.sample_for_test(data["cards"], k=k)
    llm: LLMClient = current_app.config.get("LLM_CLIENT")
    items = ExerciseBuilder.build_for_words(picked, data["cards"], llm)

    session_id = str(uuid.uuid4())
    sess_path = __import__("os").path.join(current_app.config["TESTS_DIR"], f"{session_id}.json")
    with open(sess_path, "w", encoding="utf-8") as f:
        import json
        json.dump({
            "session_id": session_id,
            "picked_words": [x["word"] for x in picked],
            "items": items,
            "started_at": _iso(_utcnow()),
            "answers": []
        }, f, ensure_ascii=False, indent=2)

    return jsonify({"session_id": session_id, "picked_words": [x["word"] for x in picked], "items": items})

@bp.post("/tests/finalize")
def finalize_tests():
    """Finalize test session: update memory labels & save history."""
    import os, json, datetime as dt
    body = request.get_json(force=True)
    sid = body.get("session_id")
    results = body.get("results") or {}
    sess_path = os.path.join(current_app.config["TESTS_DIR"], f"{sid}.json")
    if not os.path.isfile(sess_path):
        return jsonify({"error": "session not found"}), 404

    with open(sess_path, "r", encoding="utf-8") as f:
        sess = json.load(f)
    sess["results"] = results
    with open(sess_path, "w", encoding="utf-8") as f:
        json.dump(sess, f, ensure_ascii=False, indent=2)

    data = load_cards()
    label_summary = {"LTM":0, "STM":0, "REVIEW":0}
    for w in sess.get("picked_words", []):
        wrong = int(results.get(w, 0))
        label = "LTM" if wrong == 0 else ("STM" if wrong == 1 else "REVIEW")
        label_summary[label] += 1
        for c in data["cards"]:
            if c["word"].lower() == w.lower():
                c["memory_label"] = label
                c["updated_at"] = _iso(_utcnow())
                stats = c.get("stats") or {"correct":0, "wrong":0}
                if wrong == 0:
                    stats["correct"] = stats.get("correct",0) + 1
                else:
                    stats["wrong"] = stats.get("wrong",0) + 1
                c["stats"] = stats
    save_cards(data)

    # compute stats
    total_retakes = sum(int(results.get(w,0)) for w in sess.get("picked_words", []))
    start = sess.get("started_at")
    try:
        start_dt = dt.datetime.fromisoformat(start.replace('Z','')) if start else None
        duration_sec = int((_utcnow() - start_dt).total_seconds()) if start_dt else None
    except Exception:
        duration_sec = None

    # append to user stats history
    usp = current_app.config["USER_STATS_PATH"]
    if os.path.isfile(usp):
        with open(usp, "r", encoding="utf-8") as f:
            ustats = json.load(f)
    else:
        ustats = {"lessons": {}, "tests": []}
    ustats.setdefault("tests", []).append({
        "session_id": sid,
        "started_at": start,
        "finished_at": _iso(_utcnow()),
        "duration_sec": duration_sec,
        "retakes": total_retakes,
        "results": {w: {"wrong": int(results.get(w,0)), "label": "LTM" if int(results.get(w,0)) == 0 else ("STM" if int(results.get(w,0)) == 1 else "REVIEW")} for w in sess.get("picked_words", [])}
    })
    with open(usp, "w", encoding="utf-8") as f:
        json.dump(ustats, f, ensure_ascii=False, indent=2)

    return jsonify({"message": "Đã lưu kết quả", "label_summary": label_summary, "duration_sec": duration_sec, "retakes": total_retakes})
