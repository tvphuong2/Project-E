import os, json, uuid
from flask import current_app

def cards_path() -> str:
    "Đường dẫn file cards.json dựa trên app.config."
    return os.path.join(current_app.config["CARDS_DIR"], "cards.json")

def bootstrap_data_dirs(app):
    """
    Tạo thư mục data/lessons, data/cards, data/tests và file khởi tạo nếu thiếu.
    Gọi lúc khởi tạo app để tránh lỗi FileNotFound.
    """
    for k in ("LESSON_DIR", "CARDS_DIR", "TESTS_DIR"):
        os.makedirs(app.config[k], exist_ok=True)
    # cards.json
    cp = os.path.join(app.config["CARDS_DIR"], "cards.json")
    if not os.path.isfile(cp):
        with open(cp, "w", encoding="utf-8") as f:
            json.dump({"cards": []}, f, ensure_ascii=False, indent=2)
    # user_stats.json
    usp = app.config["USER_STATS_PATH"]
    if not os.path.isfile(usp):
        with open(usp, "w", encoding="utf-8") as f:
            json.dump({"lessons": {}, "tests": []}, f, ensure_ascii=False, indent=2)

def load_cards() -> dict:
    "Đọc toàn bộ dữ liệu thẻ từ cards.json."
    with open(cards_path(), "r", encoding="utf-8") as f:
        return json.load(f)

def save_cards(data: dict) -> None:
    "Ghi dữ liệu thẻ vào cards.json."
    with open(cards_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_card_ids() -> None:
    "Đảm bảo mỗi thẻ đều có id; nếu thiếu thì cấp mới và lưu lại."
    data = load_cards()
    changed = False
    for c in data.get("cards", []):
        if not c.get("id"):
            c["id"] = str(uuid.uuid4())
            changed = True
    if changed:
        save_cards(data)
