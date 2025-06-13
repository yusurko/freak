


from typing import Iterable
from sqlalchemy import Column, Select, select, or_


class SearchQuery:
    keywords: Iterable[str]

    def __init__(self, keywords: str | Iterable[str]):
        if isinstance(keywords, str):
            keywords = keywords.split()
        self.keywords = keywords
    def select(self, table: type, attrs: Iterable[Column]) -> Select:
        if not attrs:
            raise TypeError
        sq: Select = select(table)
        for kw in self.keywords:
            or_cond = []
            for attr in attrs:
                or_cond.append(attr.ilike(f"%{kw.replace('%', r'\%')}%"))
            sq = sq.where(or_(*or_cond) if len(or_cond) > 1 else or_cond[0])
        return sq

