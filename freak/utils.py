
import datetime
import functools
import math
import os
import time
import re
from quart import request
from suou import deprecated, twocolon_list as _twocolon_list

@deprecated('replaced by suou.age_and_days()')
def age_and_days(date: datetime.datetime, now: datetime.datetime | None = None) -> tuple[int, int]:
    if now is None:
        now = datetime.date.today()
    y = now.year - date.year - ((now.month, now.day) < (date.month, date.day))
    d = (now - datetime.date(date.year + y, date.month, date.day)).days
    return y, d

def get_remote_addr():
    if request.remote_addr in ('127.0.0.1', '::1') and os.getenv('APP_IS_BEHIND_PROXY'):
        return request.headers.getlist('X-Forwarded-For')[0]
    return request.remote_addr

@deprecated('replaced by suou.timed_cache()')
def timed_cache(ttl: int, maxsize: int = 128, typed: bool = False):
    def decorator(func):
        start_time = None

        @functools.lru_cache(maxsize, typed)
        def inner_wrapper(ttl_period: int, *a, **k):
            return func(*a, **k)

        @functools.wraps(func)
        def wrapper(*a, **k):
            nonlocal start_time
            if not start_time:
                start_time = int(time.time())
            return inner_wrapper(math.floor((time.time() - start_time) // ttl), *a, **k)
        return wrapper
    return decorator

def is_b32l(username: str) -> bool:
    return re.fullmatch(r'[a-z2-7]+', username)

twocolon_list = deprecated('import from suou instead')(_twocolon_list)

async def get_request_form() -> dict:
    """
    Get the request form as HTTP x-www-form-urlencoded dict

    NEW 0.5.0
    """
    return dict(await request.form)

