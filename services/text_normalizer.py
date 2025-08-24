import re
from typing import Optional
from num2words import num2words

CONTRACTIONS = {
  "i'm":"i am","you're":"you are","he's":"he is","she's":"she is","it's":"it is",
  "we're":"we are","they're":"they are","i've":"i have","we've":"we have","they've":"they have",
  "i'd":"i would","you'd":"you would","he'd":"he would","she'd":"she would","we'd":"we would","they'd":"they would",
  "i'll":"i will","you'll":"you will","he'll":"he will","she'll":"she will","we'll":"we will","they'll":"they will",
  "don't":"do not","didn't":"did not","won't":"will not","can't":"cannot","cannot":"cannot",
  "isn't":"is not","aren't":"are not","wasn't":"was not","weren't":"were not",
  "shouldn't":"should not","couldn't":"could not","wouldn't":"would not",
  "'em":"them","let's":"let us","gonna":"going to","wanna":"want to","ain't":"is not"
}

def _expand_numbers(text: str) -> str:
    def repl(m):
        num = m.group(0)
        try:
            return num2words(int(num))
        except:
            try:
                return num2words(float(num))
            except:
                return num
    return re.sub(r"\d+(?:\.\d+)?", repl, text)

def normalize_text_basic(text: str) -> str:
    t = text.strip()
    # normalize unicode quotes to ascii
    t = t.replace("’", "'").replace("‘","'").replace("“", '"').replace("”", '"')
    t = t.lower()
    # expand contractions
    for c, full in CONTRACTIONS.items():
        t = re.sub(rf"\b{re.escape(c)}\b", full, t)
    t = _expand_numbers(t)
    # remove special chars but keep comma and period
    t = re.sub(r"[^a-z0-9,\.\s]", " ", t)
    # collapse spaces
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_for_scoring(text: str, llm=None) -> str:
    """
    If llm is provided, you can add stronger cleanup/paraphrase. For now we do rule-based.
    Keeping only comma and period. Lowercase for fair WER.
    """
    return normalize_text_basic(text)
