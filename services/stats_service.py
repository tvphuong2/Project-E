class SpeedCalculator:
    @staticmethod
    def compute(correct: int, wrong: int, missing: int, duration_sec: float) -> float:
        dur = max(1.0, float(duration_sec))
        return (correct - (wrong + missing)) / dur

class ProgressTracker:
    @staticmethod
    def compute_improvement(prev_WER: float, curr_WER: float) -> float:
        if prev_WER <= 0:
            return 0.0
        change = prev_WER - curr_WER
        return (change / prev_WER) * 100.0
