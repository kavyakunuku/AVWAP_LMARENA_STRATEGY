from datetime import date, timedelta


def date_chunks(from_date: date, to_date: date, max_days: int) -> list[tuple[date, date]]:
    """Return non-overlapping [start, end) chunks. Dhan toDate is non-inclusive for historical endpoints."""
    if to_date <= from_date:
        raise ValueError("to_date must be after from_date")
    chunks=[]
    cur=from_date
    while cur < to_date:
        nxt = min(cur + timedelta(days=max_days), to_date)
        chunks.append((cur,nxt))
        cur=nxt
    return chunks
