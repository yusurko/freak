

import datetime
import logging
import enum
import re

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from suou import age_and_days
from suou.sqlalchemy.asyncio import AsyncSession
from werkzeug.security import generate_password_hash
from .models import REPORT_REASONS, User, db
from quart_auth import AuthUser, Action as _Action
from quart_wtf.utils import validate_csrf 

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

class RegisterIn(BaseModel):
    username: str
    display_name: str = ""
    password: str
    confirm_password: str
    email: str | None = None
    birthday: str
    invite_code: str | None = None

class RegisterStatus(enum.Enum):
    SUCCESS = 0
    ERROR = 1
    USERNAME_TAKEN = 2
    IP_BANNED = 3
    USERNAME_INVALID = 4
    PASSWORD_INVALID = 5
    DATE_INVALID = 6

async def validate_register(data: RegisterIn) -> RegisterStatus | dict:
    f = {}

    try:
        birthday = datetime.date.fromisoformat(data.birthday)
        birthday_age = age_and_days(birthday)

        if birthday_age == (0, 0):
            return RegisterStatus.DATE_INVALID
        if birthday_age < (14,):
            f['banned_at'] = datetime.datetime.now()
            f['banned_reason'] = REPORT_REASONS['underage']
    except ValueError:
        return RegisterStatus.DATE_INVALID

    f['username'] = data.username.lower()
    if not re.fullmatch('[a-z0-9_-]+', f['username']):
        return RegisterStatus.USERNAME_INVALID
    f['display_name'] = data.display_name

    if not data.password or data.password != data.confirm_password:
        return RegisterStatus.PASSWORD_INVALID
    f['passhash'] = generate_password_hash(data.password)

    f['email'] = data.email

    async with db as session:
        # TODO check ip ban
        # TODO implement IpBan table

        # TODO check invite code [will be implemented in 0.6]

        pass

    return f


class UserLoader(AuthUser):
    """
    Loads user from the session.

    *WARNING* requires to be awaited before request before usage!

    Actual User object is at .user; other attributes are proxied.
    """
    def __init__(self, auth_id: str | None, action: _Action= _Action.PASS):
        self._auth_id = auth_id
        self._auth_obj = None
        self._auth_sess: AsyncSession | None = None
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

    @property
    def session(self):
        return self._auth_sess

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
    color_theme: int
