# routes\vocab_test.py
import uuid, re
import os
from string import capwords
from flask import Blueprint, current_app, render_template, request, jsonify
from services.llm_service import LLMClient
from services.image_service import ImageFetcher
from services.tts_service import TTSService
from services.test_generator import WordSampler, ExerciseBuilder
from utils.storage import load_cards, save_cards, ensure_card_ids
from utils.session_utils import finalize_session
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
    Lưu một từ hoặc cụm từ mới từ phần bôi đen:
      - Chuẩn hoá: bỏ 's, ký tự lạ, chỉ giữ chữ cái/ dấu gạch nối và khoảng trắng
      - Tránh trùng (không phân biệt hoa/thường)
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
        return " ".join(tokens).lower()

    word = canonicalize(raw)
    if not word or len(word) < 2 or len(word) > 80:
        return jsonify({"ok": False, "error": "invalid_word", "input": raw, "normalized": word}), 400

    data = load_cards()
    if any((c.get("word","").lower() == word.lower()) for c in data["cards"]):
        # Đã có
        card = next(c for c in data["cards"] if c.get("word","").lower() == word.lower())
        return jsonify({"ok": True, "message": "Đã có trong bộ thẻ", "card": card})

    now = _iso(_utcnow())
    card = {
        "id": str(uuid.uuid4()), "word": capwords(word),
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
                "word": capwords(c.get("word","")),
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
                        "id": new_id, "word": capwords(s),
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


@bp.post("/vocab/fill_missing_all")
def vocab_fill_missing_all():
    """Fill missing fields for all cards that lack data."""
    ensure_card_ids()
    data = load_cards()
    llm: LLMClient = current_app.config["LLM_CLIENT"]
    img: ImageFetcher = current_app.config["IMG_FETCHER"]
    tts: TTSService = current_app.config["TTS_CLIENT"]
    updated_count = 0
    now = _iso(_utcnow())

    for card in data["cards"]:
        updated = False
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
            updated_count += 1

    if updated_count:
        save_cards(data)

    return jsonify({"updated": updated_count, "message": f"Filled {updated_count} cards"})


# ---------- BÀI TEST ----------
@bp.get("/test")
def get_test_page():
    "Trang bắt đầu bài test ôn từ (templates/test.html)."
    k = current_app.config.get("TEST_WORD_COUNT", 10)
    ans_map = current_app.config.get("ANSWER_REVEAL_MS", {})
    max_min = current_app.config.get("MAX_MIN", 30)
    return render_template("test.html", title="Test từ vựng", test_word_count=k, answer_ms_map=ans_map, max_min=max_min)

@bp.post("/tests/start")
def start_tests():
    "Chọn số từ theo tỉ lệ 5/30/65, sinh bài tập."
    data = load_cards()
    k = current_app.config.get("TEST_WORD_COUNT", 10)
    picked = WordSampler.sample_for_test(data["cards"], k=k)
    llm: LLMClient = current_app.config.get("LLM_CLIENT")
    enabled = current_app.config.get("ENABLED_EXERCISE_TYPES") or []
    items = ExerciseBuilder.build_for_words(picked, data["cards"], llm, enabled)

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
    body = request.get_json(force=True)
    sid = body.get("session_id")
    results = body.get("results") or {}

    try:
        label_summary, duration_sec, total_retakes = finalize_session(sid, results)
    except FileNotFoundError:
        return jsonify({"error": "session not found"}), 404

    return jsonify({
        "message": "Đã lưu kết quả",
        "label_summary": label_summary,
        "duration_sec": duration_sec,
        "retakes": total_retakes,
    })
