from datetime import date
from app.data.downloader.chunks import date_chunks


def test_date_chunks_non_inclusive_boundaries():
    chunks = date_chunks(date(2024,1,1), date(2024,3,1), 30)
    assert chunks == [(date(2024,1,1), date(2024,1,31)), (date(2024,1,31), date(2024,3,1))]
