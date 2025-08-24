import random
from typing import List, Dict

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
            "prompt_vi": word.get("meaning_vi","(no meaning)"),
            "options": options,
            "answer": word["word"]
        }

    @staticmethod
    def build_type_from_meaning(word: Dict) -> Dict:
        return {
            "type": "type_from_meaning",
            "word": word["word"],
            "prompt_vi": word.get("meaning_vi","(no meaning)"),
        }

    @staticmethod
    def build_for_words(words: List[Dict], all_words: List[Dict]) -> List[Dict]:
        # For each word, create 2 exercises: vi2en_mcq and type_from_meaning
        all_lex = [w["word"] for w in all_words]
        items = []
        for w in words:
            # distractors from other words or near-miss strings
            others = [x for x in all_lex if x.lower()!=w["word"].lower()]
            random.shuffle(others)
            items.append(ExerciseBuilder.build_vi2en_mcq(w, others))
            items.append(ExerciseBuilder.build_type_from_meaning(w))
        return items
