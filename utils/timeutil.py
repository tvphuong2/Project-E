import datetime as dt

def _utcnow() -> dt.datetime:
    "Trả về thời điểm UTC hiện tại (datetime)."
    return dt.datetime.utcnow()

def _iso(d: dt.datetime) -> str:
    "Định dạng ISO UTC (không microseconds)."
    return d.replace(microsecond=0).isoformat() + "Z"
