import random
from typing import List, Dict

from services.llm_service import LLMClient

class WordSampler:
    @staticmethod
    def sample_for_test(cards: List[Dict], k: int = 10) -> List[Dict]:
        # Split by memory_label
        LTM = [c for c in cards if c.get("memory_label") == "LTM"]
        STM = [c for c in cards if c.get("memory_label") == "STM"]
        REV = [c for c in cards if c.get("memory_label") in (None, "", "REVIEW")]
        # quotas 5%, 30%, 65% of k
        q_ltm = max(0, round(0.05 * k))
        q_stm = max(0, round(0.30 * k))
        q_rev = k - q_ltm - q_stm
        pick = []
        random.shuffle(LTM); random.shuffle(STM); random.shuffle(REV)
        pick.extend(LTM[:q_ltm])
        pick.extend(STM[:q_stm])
        pick.extend(REV[:q_rev])
        # if not enough, top up
        pool = [c for c in cards if c not in pick]
        while len(pick) < k and pool:
            pick.append(pool.pop())
        return pick[:k]

class ExerciseBuilder:
    @staticmethod
    def build_vi2en_mcq(word: Dict, distractors: List[str]) -> Dict:
        options = distractors[:3] + [word["word"]]
        random.shuffle(options)
        return {
            "type": "vi2en_mcq",
            "word": word["word"],
            "prompt_vi": word.get("meaning_vi", "(no meaning)"),
            "options": options,
            "answer": word["word"],
            "pos": word.get("pos", ""),
            "audio_url": word.get("audio_url"),
        }

    @staticmethod
    def build_type_from_meaning(word: Dict) -> Dict:
        return {
            "type": "type_from_meaning",
            "word": word["word"],
            "prompt_vi": word.get("meaning_vi", "(no meaning)"),
            "pos": word.get("pos", ""),
            "audio_url": word.get("audio_url"),
        }

    @staticmethod
    def build_vi_sentence_input(word: Dict, llm: LLMClient) -> Dict:
        pair = llm.generate_sentence_pair(word["word"]) if llm else {"vi": "", "en": ""}
        return {
            "type": "vi_sentence_input",
            "word": word["word"],
            "prompt_vi": pair.get("vi", ""),
            "answer": pair.get("en", ""),
            "pos": word.get("pos", ""),
        }

    @staticmethod
    def build_en_vi_match(word: Dict, all_words: List[Dict], llm: LLMClient):
        similars = llm.generate_similar_or_confusables(word["word"]) if llm else []
        words = [word["word"]] + similars[:4]
        if len(words) < 5:
            return None
        pairs = []
        for w in words:
            card = next((c for c in all_words if c["word"].lower() == w.lower()), None)
            meaning = card.get("meaning_vi", "") if card else ""
            pos = card.get("pos", "") if card else ""
            if (not meaning or not pos) and llm:
                desc = llm.describe_word(w)
                if not meaning:
                    meaning = desc.get("meaning_vi", "")
                if not pos:
                    pos = desc.get("pos", "")
            pairs.append({"en": w, "vi": meaning, "pos": pos})
        en_words = [p["en"] for p in pairs]
        vi_meanings = [p["vi"] for p in pairs]
        pos_map = {p["en"]: p["pos"] for p in pairs}
        random.shuffle(en_words)
        random.shuffle(vi_meanings)
        mapping = {p["en"]: p["vi"] for p in pairs}
        return {
            "type": "en_vi_match",
            "word": word["word"],
            "en_words": en_words,
            "vi_meanings": vi_meanings,
            "pairs": mapping,
            "pos_map": pos_map,
            "audio_url": word.get("audio_url"),
        }

    @staticmethod
    def build_audio_to_en(word: Dict) -> Dict:
        return {
            "type": "audio2en_input",
            "word": word["word"],
            "audio_url": word.get("audio_url"),
            "pos": word.get("pos", ""),
        }

    @staticmethod
    def build_for_words(words: List[Dict], all_words: List[Dict], llm: LLMClient, enabled_types: List[str]) -> List[Dict]:
        """Create exercises for each word, filtered by enabled_types."""
        all_lex = [w["word"] for w in all_words]
        enabled = set(enabled_types or [])
        if not enabled:
            enabled = {"vi2en_mcq", "type_from_meaning", "vi_sentence_input", "en_vi_match", "audio2en_input"}
        items = []
        for w in words:
            others = [x for x in all_lex if x.lower() != w["word"].lower()]
            random.shuffle(others)
            if "vi2en_mcq" in enabled:
                items.append(ExerciseBuilder.build_vi2en_mcq(w, others))
            if "type_from_meaning" in enabled:
                items.append(ExerciseBuilder.build_type_from_meaning(w))
            if "vi_sentence_input" in enabled:
                items.append(ExerciseBuilder.build_vi_sentence_input(w, llm))
            if "en_vi_match" in enabled:
                match = ExerciseBuilder.build_en_vi_match(w, all_words, llm)
                if match:
                    items.append(match)
            if "audio2en_input" in enabled and w.get("audio_url"):
                items.append(ExerciseBuilder.build_audio_to_en(w))
        random.shuffle(items)
        return items
