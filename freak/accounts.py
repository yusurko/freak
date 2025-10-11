

import logging
import enum

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from .models import User, db
from quart_auth import AuthUser, Action as _Action

logger = logging.getLogger(__name__)

class LoginStatus(enum.Enum):
    SUCCESS = 0
    ERROR = 1
    SUSPENDED = 2
    PASS_EXPIRED = 3

def check_login(user: User | None, password: str) -> LoginStatus:
    try:
        if user is None:
            return LoginStatus.ERROR
        if ('$' not in user.passhash) and user.email:
            return LoginStatus.PASS_EXPIRED
        if not user.is_active:
            return LoginStatus.SUSPENDED
        if user.check_password(password):
            return LoginStatus.SUCCESS
    except Exception as e:
        logger.error(f'{e}')
    return LoginStatus.ERROR


class UserLoader(AuthUser):
    """
    Loads user from the session.

    *WARNING* requires to be awaited before request before usage!

    Actual User object is at .user; other attributes are proxied.
    """
    def __init__(self, auth_id: str | None, action: _Action= _Action.PASS):
        self._auth_id = auth_id
        self._auth_obj = None
        self._auth_sess = None
        self.action = action
    
    @property
    def auth_id(self) -> str | None:
        return self._auth_id

    @property
    async def is_authenticated(self) -> bool:
        await self._load()
        return self._auth_id is not None

    async def _load(self):
        if self._auth_obj is None and self._auth_id is not None:
            async with db as session:
                self._auth_obj = (await session.execute(select(User).where(User.id == int(self._auth_id)))).scalar()
                if self._auth_obj is None:
                    raise RuntimeError('failed to fetch user')

    def __getattr__(self, key):
        if self._auth_obj is None:
            raise RuntimeError('user is not loaded')
        return getattr(self._auth_obj, key)

    def __bool__(self):
        return self._auth_obj is not None

    async def _unload(self):
        # user is not expected to mutate
        if self._auth_sess:
            await self._auth_sess.rollback()

    @property
    def user(self):
        return self._auth_obj

    id: int
    username: str
    display_name: str
    theme_color: int
