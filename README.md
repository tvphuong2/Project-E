# English Dictation (Minimal UI)

A tiny Flask app for **English dictation** + **WER checking** + **vocab cards with enrich & testing**. Single-user, file-based (JSON + media).

## Quick start

```bash
cd eng_dictation_app
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
# Add your keys:
#   - edit config.yaml (OpenAI + Google CSE)
python app.py
# visit http://127.0.0.1:5000
```

## Features (in this minimal build)

- Create lesson: upload audio + paste raw text → normalized via LLM (if key) or rules.
- Play audio (full width). Hotkeys: `=` pause & -3s, `-` -10s.
- Type transcript, press **Kiểm tra (WER)** → shows WER, S/D/I, speed, improvement and highlights (green=correct, red=wrong, `_`=missing run).
- Select a word in the textarea → **Lưu từ đã bôi đen** → adds a RAW card.
- **Ôn từ mới**: see counts; **Enrich All** → describe words (LLM), fetch 1 image per word (Google CSE), auto-generate "additional" confusing words.
- **Test** (very basic demo): pick 10 words (ratios across memory buckets are configurable), generate MCQ (vi→en) and type-from-meaning; retake-wrong-only UX is stubbed; finalize marks words as LTM (demo).

> You can extend /tests logic to track per-item correctness and apply exact LTM/STM/REVIEW rules.

## Config (config.yaml)

```yaml
openai:
  api_key: "YOUR_OPENAI_API_KEY"
  model: "gpt-4o-mini"

google_cse:
  api_key: "YOUR_GOOGLE_CSE_API_KEY"
  cx: "YOUR_GOOGLE_CSE_CX"

app:
  max_attempt_duration_min: 30
  host: "127.0.0.1"
  port: 5000
  debug: true
```

## Notes

- All data under `data/` (JSON + uploads). One lesson = one folder in `data/lessons/<id>/`.
- Normalization keeps only comma and period, lowercases for fair WER.
- Deletion runs are collapsed into a single `_` span for highlighting.

## Roadmap (placeholders ready)

- Add **cloze MCQ**.
- Track per-item correctness → exact memory labels (0 wrong → LTM; 1 wrong → STM; >1 → REVIEW).
- Reverse dictation & chat pages.
- Better image caching and download to `data/cards/images/`.
