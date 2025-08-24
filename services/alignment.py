from dataclasses import dataclass
from typing import List, Tuple, Dict

@dataclass
class AlignmentResult:
    ops: List[Tuple[str, str, str]]  # (op, ref_tok or "", hyp_tok or "")
    S: int
    D: int
    I: int
    N: int
    WER: float

def tokenize_words(text: str) -> List[str]:
    # simple whitespace tokenization
    return [t for t in text.strip().split() if t]

def _levenshtein_ops(ref: List[str], hyp: List[str]) -> List[Tuple[str, str, str]]:
    # DP edit distance with backtrace at word level
    n, m = len(ref), len(hyp)
    dp = [[0]*(m+1) for _ in range(n+1)]
    bt = [[None]*(m+1) for _ in range(n+1)]  # store 'M','S','I','D'
    for i in range(1, n+1):
        dp[i][0] = i
        bt[i][0] = 'D'
    for j in range(1, m+1):
        dp[0][j] = j
        bt[0][j] = 'I'
    for i in range(1, n+1):
        for j in range(1, m+1):
            cost_sub = 0 if ref[i-1] == hyp[j-1] else 1
            choices = [
                (dp[i-1][j-1] + cost_sub, 'M' if cost_sub==0 else 'S'),
                (dp[i][j-1] + 1, 'I'),
                (dp[i-1][j] + 1, 'D'),
            ]
            dp[i][j], bt[i][j] = min(choices, key=lambda x: x[0])
    # backtrace
    ops: List[Tuple[str,str,str]] = []
    i, j = n, m
    while i>0 or j>0:
        op = bt[i][j]
        if op == 'M':
            ops.append(('M', ref[i-1], hyp[j-1]))
            i -= 1; j -= 1
        elif op == 'S':
            ops.append(('S', ref[i-1], hyp[j-1]))
            i -= 1; j -= 1
        elif op == 'I':
            ops.append(('I', '', hyp[j-1]))
            j -= 1
        elif op == 'D':
            ops.append(('D', ref[i-1], ''))
            i -= 1
        else:
            break
    ops.reverse()
    return ops

def collapse_deletions_to_single_underscore(ops: List[Tuple[str,str,str]]) -> List[Tuple[str,str,str]]:
    out = []
    missing_run = False
    for op, rt, ht in ops:
        if op == "D":
            if not missing_run:
                out.append(("_", "", ""))  # one underscore to cover any length run
                missing_run = True
        else:
            missing_run = False
            out.append((op, rt, ht))
    return out

def align_and_score(ref_tokens: List[str], hyp_tokens: List[str]) -> AlignmentResult:
    ops = _levenshtein_ops(ref_tokens, hyp_tokens)
    N = len(ref_tokens)
    S = sum(1 for op,_,_ in ops if op == 'S')
    D = sum(1 for op,_,_ in ops if op == 'D')
    I = sum(1 for op,_,_ in ops if op == 'I')
    WER = (S + D + I) / max(1, N)
    return AlignmentResult(ops=ops, S=S, D=D, I=I, N=N, WER=WER)

def spans_for_highlight(ops: List[Tuple[str,str,str]]):
    spans = []
    for op, rt, ht in ops:
        if op == 'M':
            spans.append({"token": ht, "status":"correct"})
        elif op in ('S','I'):
            spans.append({"token": ht if ht else rt, "status":"wrong"})
        elif op == '_':
            spans.append({"token": "_", "status":"missing"})
        elif op == 'D':
            # D will be collapsed later; keep as missing if not collapsed
            spans.append({"token": "_", "status":"missing"})
    return spans
