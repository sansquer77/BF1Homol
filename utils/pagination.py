"""Primitivas neutras para paginação consistente."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(self.total_items / self.page_size))

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginate(page: int, page_size: int, total_items: int) -> Pagination:
    """Normaliza tamanho, total e página para uma faixa válida."""
    safe_size = max(1, min(int(page_size), 500))
    safe_total = max(0, int(total_items))
    total_pages = max(1, math.ceil(safe_total / safe_size))
    safe_page = max(1, min(int(page), total_pages))
    return Pagination(safe_page, safe_size, safe_total)
