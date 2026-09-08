from services.logs_read_service import _pagination


def test_log_pagination_clamps_page_and_size_deterministically():
    assert _pagination(101, 99, 500) == {"page": 1, "page_size": 200, "total": 101, "total_pages": 1}
    assert _pagination(101, 3, 50) == {"page": 3, "page_size": 50, "total": 101, "total_pages": 3}
    assert _pagination(0, 8, 50) == {"page": 1, "page_size": 50, "total": 0, "total_pages": 1}
