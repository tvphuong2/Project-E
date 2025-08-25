# routes\vocab_test.py
import uuid, re
from flask import Blueprint, current_app, render_template, request, jsonify
from services.llm_service import LLMClient
from services.image_service import ImageFetcher
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
        "image_url": None, "audio_url": None,
        "created_at": now, "updated_at": now,
        "memory_label": "", "stats": {"correct": 0, "wrong": 0}
    }

    if bool(payload.get("enrich_now")):
        llm: LLMClient = current_app.config["LLM_CLIENT"]
        img = current_app.config["IMG_FETCHER"]
        tts = current_app.config["TTS_CLIENT"]
        try:
            desc = llm.describe_word(card["word"]) if current_app.config["OPENAI_KEY"] else {}
            card["pos"] = desc.get("pos",""); card["meaning_vi"] = desc.get("meaning_vi","")
            card["usage"] = desc.get("usage",""); card["phonetic"] = desc.get("phonetic","")
            card["image_url"] = img.fetch(card["word"]) if (current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]) else None
            if current_app.config["OPENAI_KEY"]:
                audio_dir = __import__("os").path.join(current_app.config["CARDS_DIR"], "audio")
                filename = f"{card['id']}.mp3"
                full = __import__("os").path.join(audio_dir, filename)
                if tts.synthesize_to_file(card["word"], full):
                    card["audio_url"] = f"/data/cards/audio/{filename}"
            card["status"] = "enrich"; card["updated_at"] = _iso(_utcnow())
        except Exception:
            pass

    data["cards"].append(card)
    save_cards(data)
    return jsonify({"ok": True, "message": "Đã lưu từ", "card": card})

@bp.post("/vocab/fill_missing/<id_or_word>")
def vocab_fill_missing(id_or_word: str):
    """Fill missing fields (pos, meaning_vi, usage, phonetic, image, audio) for a card."""
    ensure_card_ids()
    key = (id_or_word or "").strip()
    data = load_cards()
    target = None
    for c in data["cards"]:
        if str(c.get("id")) == key or str(c.get("word", "")).lower() == key.lower():
            target = c
            break
    if not target:
        return jsonify({"error": "not found"}), 404

    llm: LLMClient = current_app.config["LLM_CLIENT"]
    img: ImageFetcher = current_app.config["IMG_FETCHER"]
    tts = current_app.config["TTS_CLIENT"]
    changed = False

    if current_app.config["OPENAI_KEY"] and (not target.get("pos") or not target.get("meaning_vi") or not target.get("usage") or not target.get("phonetic")):
        try:
            desc = llm.describe_word(target["word"])
            if not target.get("pos"): target["pos"] = desc.get("pos", "")
            if not target.get("meaning_vi"): target["meaning_vi"] = desc.get("meaning_vi", "")
            if not target.get("usage"): target["usage"] = desc.get("usage", "")
            if not target.get("phonetic"): target["phonetic"] = desc.get("phonetic", "")
            changed = True
        except Exception:
            pass

    if (not target.get("image_url")) and current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]:
        try:
            target["image_url"] = img.fetch(target["word"])
            changed = True
        except Exception:
            pass

    if (not target.get("audio_url")) and current_app.config["OPENAI_KEY"]:
        audio_dir = __import__("os").path.join(current_app.config["CARDS_DIR"], "audio")
        filename = f"{target['id']}.mp3"
        full = __import__("os").path.join(audio_dir, filename)
        if tts.synthesize_to_file(target["word"], full):
            target["audio_url"] = f"/data/cards/audio/{filename}"
            changed = True

    if changed:
        if (target.get("status") or "").lower() == "raw":
            target["status"] = "enrich"
        target["updated_at"] = _iso(_utcnow())
        save_cards(data)

    return jsonify({"card": target, "updated": changed})

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
    tts = current_app.config["TTS_CLIENT"]

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
                "status": "enrich", "updated_at": now
            })
            if current_app.config["OPENAI_KEY"]:
                audio_dir = __import__("os").path.join(current_app.config["CARDS_DIR"], "audio")
                filename = f"{c['id']}.mp3"
                full = __import__("os").path.join(audio_dir, filename)
                if tts.synthesize_to_file(c["word"], full):
                    c["audio_url"] = f"/data/cards/audio/{filename}"
            changed += 1

            similars = llm.generate_similar_or_confusables(c["word"]) if current_app.config["OPENAI_KEY"] else []
            for s in similars:
                if not any(x["word"].lower() == s.lower() for x in data["cards"]):
                    desc2 = llm.describe_word(s) if current_app.config["OPENAI_KEY"] else {"pos":"", "meaning_vi":"", "usage":"", "phonetic":""}
                    img2 = img.fetch(s) if (current_app.config["G_CSE_KEY"] and current_app.config["G_CSE_CX"]) else None
                    add_id = str(uuid.uuid4())
                    audio_url = None
                    if current_app.config["OPENAI_KEY"]:
                        audio_dir = __import__("os").path.join(current_app.config["CARDS_DIR"], "audio")
                        filename = f"{add_id}.mp3"
                        full = __import__("os").path.join(audio_dir, filename)
                        if tts.synthesize_to_file(s, full):
                            audio_url = f"/data/cards/audio/{filename}"
                    data["cards"].append({
                        "id": add_id, "word": s.capitalize(),
                        "status": "additional", "origin": "auto_additional",
                        "pos": desc2.get("pos",""), "meaning_vi": desc2.get("meaning_vi",""),
                        "usage": desc2.get("usage",""), "phonetic": desc2.get("phonetic",""),
                        "image_url": img2, "audio_url": audio_url,
                        "created_at": now, "updated_at": now,
                        "memory_label": "", "stats": {"correct": 0, "wrong": 0}
                    })
    save_cards(data)
    return jsonify({"message": f"Enriched {changed} raw cards (including additional w/ details)"})


# ---------- BÀI TEST ----------
#
# Các hàm xử lý route dưới đây trước đây được đặt tên bắt đầu bằng
# ``test_*``.  Điều này vô tình khiến ``pytest`` hiểu đây là các testcase
# và cố gắng chạy chúng mà không có ngữ cảnh Flask thích hợp, dẫn tới lỗi
# "Working outside of application/request context" khi chạy kiểm thử.
#
# Đổi tên các hàm để tránh bị thu thập bởi ``pytest``.  Để giữ nguyên tên
# endpoint (phục vụ ``url_for`` nếu được dùng ở nơi khác) chúng ta chỉ định
# tham số ``endpoint`` trong decorator.

@bp.get("/test", endpoint="test_page")
def vocab_test_page():
    "Trang bắt đầu bài test ôn từ (templates/test.html)."
    return render_template("test.html", title="Test từ vựng")

@bp.post("/tests/start", endpoint="tests_start")
def vocab_tests_start():
    "Chọn 10 từ theo tỉ lệ 5/30/65, sinh bài tập (MCQ + gõ từ)."
    data = load_cards()
    picked = WordSampler.sample_for_test(data["cards"], k=10)
    items = ExerciseBuilder.build_for_words(picked, data["cards"])
    __import__('random').shuffle(items)

    session_id = str(uuid.uuid4())
    sess_path = __import__("os").path.join(current_app.config["TESTS_DIR"], f"{session_id}.json")
    with open(sess_path, "w", encoding="utf-8") as f:
        import json
        json.dump({"session_id": session_id, "picked_words": [x["word"] for x in picked], "items": items, "answers": []}, f, ensure_ascii=False, indent=2)

    return jsonify({"session_id": session_id, "picked_words": [x["word"] for x in picked], "items": items})

@bp.post("/tests/finalize", endpoint="tests_finalize")
def vocab_tests_finalize():
    """
    Chốt phiên test (DEMO):
      - hiện tại gắn nhãn LTM cho các từ đã pick (bạn có thể nâng cấp logic wrong-only/nhãn sau).
    """
    import os, json
    body = request.get_json(force=True)
    sid = body.get("session_id")
    sess_path = os.path.join(current_app.config["TESTS_DIR"], f"{sid}.json")
    if not os.path.isfile(sess_path):
        return jsonify({"error": "session not found"}), 404

    with open(sess_path, "r", encoding="utf-8") as f:
        sess = json.load(f)
    data = load_cards()
    for w in sess.get("picked_words", []):
        for c in data["cards"]:
            if c["word"].lower() == w.lower():
                c["memory_label"] = "LTM"
                c["updated_at"] = _iso(_utcnow())
    save_cards(data)
    return jsonify({"message": "Cập nhật nhãn (demo) xong"})
