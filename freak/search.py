


from typing import Iterable
from flask import flash, g
from sqlalchemy import Column, Select, select, or_

from .models import Guild, User, db


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


def find_guild_or_user(name: str) -> str | None:
    """
    Used in 404 error handler.

    Returns an URL to redirect or None for no redirect.
    """

    if hasattr(g, 'no_user'):
        return None

    gu = db.session.execute(select(Guild).where(Guild.name == name)).scalar()
    if gu is not None:
        flash(f'There is nothing at /{name}. Luckily, a guild with name {gu.handle()} happens to exist. Next time, remember to add + before!')
        return gu.url()

    user = db.session.execute(select(User).where(User.username == name)).scalar()
    if user is not None:
        flash(f'There is nothing at /{name}. Luckily, a user named {user.handle()} happens to exist. Next time, remember to add @ before!')
        return user.url()

    return None