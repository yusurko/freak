

from __future__ import annotations

import asyncio
from collections import namedtuple
import datetime
from functools import partial
from operator import or_
import re
from threading import Lock
from typing import Any, Callable
from quart_auth import current_user
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, and_, insert, text, \
    CheckConstraint, Date, DateTime, Boolean, func, BigInteger, \
    SmallInteger, select, update, Table
from sqlalchemy.orm import Relationship, relationship
from suou.sqlalchemy_async import SQLAlchemy
from suou import SiqType, Snowflake, Wanted, deprecated, makelist, not_implemented
from suou.sqlalchemy import create_session, declarative_base, id_column, parent_children, snowflake_column
from werkzeug.security import check_password_hash

from . import app_config
from .utils import get_remote_addr

from suou import timed_cache, age_and_days

import logging 

logger = logging.getLogger(__name__)

## Constants and enums

## NOT IN USE: User has .banned_at and .is_disabled_by_user
USER_ACTIVE   = 0
USER_INACTIVE = 1
USER_BANNED   = 2

ReportReason = namedtuple('ReportReason', 'num_code code description extra', defaults=dict(extra=None))

post_report_reasons = [
    ## emergency
    ReportReason(110, 'hate_speech', 'Extreme hate speech / terrorism'),
    ReportReason(121, 'csam', 'Child abuse or endangerment', extra=dict(suspend=True)),
    ReportReason(142, 'revenge_sxm', 'Revenge porn'),
    ReportReason(122, 'black_market', 'Sale or promotion of regulated goods (e.g. firearms)'),
    ## urgent
    ReportReason(171, 'xxx', 'Pornography'),
    ReportReason(111, 'tasteless', 'Extreme violence / gore'),
    ReportReason(180, 'impersonation', 'Impersonation'),
    ReportReason(141, 'doxing', 'Diffusion of PII (personally identifiable information)'),
    ## less urgent
    ReportReason(112, 'lgbt_hate', 'Hate speech against LGBTQ+ or women'),
    ReportReason(140, 'bullying', 'Harassment, bullying, or suicide incitement'),
    ReportReason(150, 'security_exploit', 'Dangerous security exploit or violation'),
    ReportReason(160, 'spam', 'Unsolicited advertising'),
    ReportReason(190, 'false_information', 'False or deceiving information'),
    ReportReason(123, 'copyviol', 'This is my creation and someone else is using it without my permission/license'),
    ## minor (unironically)
    ReportReason(210, 'underage', 'Presence in violation of age limits (i.e. under 13, or minor in adult spaces)', extra=dict(suspend=True))
]

REPORT_REASON_STRINGS = { **{x.num_code: x.description for x in post_report_reasons}, **{x.code: x.description for x in post_report_reasons} }

REPORT_REASONS: dict[str, int] = {x.code: x.num_code for x in post_report_reasons}

REPORT_TARGET_POST = 1
REPORT_TARGET_COMMENT = 2

REPORT_UPDATE_PENDING = 0
REPORT_UPDATE_COMPLETE = 1
REPORT_UPDATE_REJECTED = 2
REPORT_UPDATE_ON_HOLD = 3

USERNAME_RE = r'[a-z2-9_-][a-z0-9_-]+'

ILLEGAL_USERNAMES = tuple((
    ## masspings and administrative claims
    'me everyone here room all any server app dev devel develop nil none '
    'founder owner admin administrator mod modteam moderator sysop some '
    ## fictitious users and automations
    'nobody somebody deleted suspended default bot developer undefined null '
    'ai automod clanker automoderator assistant privacy anonymous removed assistance '
    ## law enforcement corps and slurs because yes
    'pedo rape rapist nigger retard ncmec police cops 911 childsafety '
    'report dmca login logout security order66 gestapo ss hitler heilhitler kgb '
    'pedophile lolicon giphy tenor csam cp pedobear lolita lolice thanos '
    'loli lolicon kkk pnf adl cop tranny google trustandsafety safety ice fbi nsa it '
    ## VVVVIP
    'potus realdonaldtrump elonmusk teddysphotos mrbeast jkrowling pewdiepie '
    'elizabethii elizabeth2 king queen pontifex hogwarts lumos alohomora isis daesh retards '
).split())

def username_is_legal(username: str) -> bool:
    if len(username) < 2 or len(username) > 100:
        return False

    if re.fullmatch(USERNAME_RE, username) is None:
        return False
    
    if username in ILLEGAL_USERNAMES:
        return False
    return True

def want_User(o: User | Any | None, *, prefix: str = '', var_name: str = '') -> User | None:
    if isinstance(o, User):
        return o
    if o is None:
        return None
    logger.warning(f'{prefix}: {repr(var_name) + " has " if var_name else ""}invalid type {o.__class__.__name__}, expected User')
    return None

## END constants and enums

Base = declarative_base(app_config.server_name, app_config.secret_key, 
    snowflake_epoch=1577833200)
db = SQLAlchemy(model_class=Base)

CSI = create_session_interactively = partial(create_session, app_config.database_url)


## .accounts requires db
#current_user: UserLoader


## Many-to-many relationship keys for some reasons have to go
## BEFORE other table definitions.
## I (Sakuragasaki46) take no accountability; blame SQLAlchemy development.

PostUpvote = Table(
    'freak_post_upvote',
    Base.metadata,
    Column('post_id', BigInteger, ForeignKey('freak_post.id'), primary_key=True),
    Column('voter_id', BigInteger, ForeignKey('freak_user.id'), primary_key=True),
    Column('is_downvote', Boolean, server_default=text('false'))
)

UserBlock = Table(
    'freak_user_block',
    Base.metadata,
    Column('actor_id', BigInteger, ForeignKey('freak_user.id'), primary_key=True),
    Column('target_id', BigInteger, ForeignKey('freak_user.id'), primary_key=True)
)


class User(Base):
    __tablename__ = 'freak_user'
    __table_args__ = (
        ## XXX this constraint (and the other three at Post, Guild and Comment) cannot be removed!!
        UniqueConstraint('id', name='user_id_uniq'),
    )

    id = snowflake_column()

    username = Column(String(32), CheckConstraint(text("username = lower(username) and username ~ '^[a-z0-9_-]+$'"), name="user_username_valid"), unique=True, nullable=False)
    display_name = Column(String(64), nullable=False)
    passhash = Column(String(256), nullable=False)
    email = Column(String(256), CheckConstraint(text("email IS NULL OR (email = lower(email) AND email LIKE '_%@_%.__%')"), name='user_email_valid'), nullable=True)
    gdpr_birthday = Column(Date, nullable=False)
    joined_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    joined_ip = Column(String(64), default=get_remote_addr, nullable=False)
    is_administrator = Column(Boolean, server_default=text('false'), nullable=False)
    is_disabled_by_user = Column(Boolean, server_default=text('false'), nullable=False)
    karma = Column(BigInteger, server_default=text('0'), nullable=False)
    legacy_id = Column(BigInteger, nullable=True)
    
    # pronouns must be set via suou.dei.Pronoun.from_short()
    pronouns = Column(Integer, server_default=text('0'), nullable=False)
    biography = Column(String(1024), nullable=True)
    color_theme = Column(SmallInteger, nullable=False, server_default=text('0'))

    # moderation
    banned_at = Column(DateTime, nullable=True)
    banned_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_banner_id'), nullable=True)
    banned_reason = Column(SmallInteger, server_default=text('0'), nullable=True)
    banned_until = Column(DateTime, nullable=True)
    banned_message = Column(String(256), nullable=True)

    # invites
    is_approved = Column(Boolean, server_default=text('false'), nullable=False)
    invited_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_inviter_id'), nullable=True)
    
    # utilities
    ## XXX posts and comments relationships are temporarily disabled because they make
    ## SQLAlchemy fail initialization of models — bricking the app.
    ## Posts are queried manually anyway
    #posts = relationship("Post", primaryjoin=lambda: #back_populates='author', pr)
    upvoted_posts = relationship("Post", secondary=PostUpvote, back_populates='upvoters', lazy='selectin')
    #comments = relationship("Comment", back_populates='author', lazy='selectin')
    
    @property
    def is_disabled(self):
        now = datetime.datetime.now()
        return (
            # suspended
            (self.banned_at is not None and (self.banned_until is None or self.banned_until >= now)) or 
            # self-disabled
            self.is_disabled_by_user
        )

    @property
    def is_active(self):
        return not self.is_disabled

    @property
    @deprecated('shadowed by UserLoader.is_authenticated(), and always true')
    def is_authenticated(self):
        return True

    @property
    @deprecated('no more in use since switch to Quart')
    def is_anonymous(self):
        return False

    @deprecated('this representation uses decimal, URLs use b32l')
    def get_id(self):
        return str(self.id)

    def url(self):
        return f'/@{self.username}'

    @timed_cache(ttl=3600)
    def age(self):
        return age_and_days(self.gdpr_birthday)[0]

    def simple_info(self, *, typed = False):
        """
        Return essential informations for representing a user in the REST
        """
        ## XXX change func name?
        gg = dict(
            id = Snowflake(self.id).to_b32l(),
            username = self.username,
            display_name = self.display_name,
            age = self.age(),
            badges = self.badges(),

        )
        if typed:
            gg['type'] = 'user'
        return gg

    @deprecated('updates may be not atomic. DO NOT USE until further notice')
    async def reward(self, points=1):
        """
        Manipulate a user's karma on the fly
        """
        with Lock():
            async with db as session:
                await session.execute(update(User).where(User.id == self.id).values(karma = self.karma + points))
                await session.commit()

    def can_create_guild(self):
        ## TODO make guild creation requirements fully configurable
        return self.karma > app_config.create_guild_threshold or self.is_administrator

    can_create_community = deprecated('use .can_create_guild()')(can_create_guild)

    def handle(self):
        return f'@{self.username}'

    def check_password(self, password):
        return check_password_hash(self.passhash, password)

    @classmethod
    @timed_cache(1800, async_=True)
    async def active_count(cls) -> int:
        active_th = datetime.datetime.now() - datetime.timedelta(days=30)
        async with db as session:
            count = (await session.execute(select(func.count(User.id)).select_from(cls).join(Post, Post.author_id == User.id).where(Post.created_at >= active_th).group_by(User.id))).scalar()
        return count

    def __repr__(self):
        return f'<{self.__class__.__name__} id:{self.id!r} username:{self.username!r}>'

    @classmethod
    def not_suspended(cls):
        return or_(User.banned_at == None, User.banned_until <= datetime.datetime.now())

    async def has_blocked(self, other: User | None) -> bool:
        if not want_User(other, var_name='other', prefix='User.has_blocked()'):
            return False
        async with db as session:
            block_exists = (await session.execute(select(UserBlock).where(UserBlock.c.actor_id == self.id, UserBlock.c.target_id == other.id))).scalar()
        return bool(block_exists)

    async def is_blocked_by(self, other: User | None) -> bool:
        if not want_User(other, var_name='other', prefix='User.is_blocked_by()'):
            return False
        async with db as session:
            block_exists = (await session.execute(select(UserBlock).where(UserBlock.c.actor_id == other.id, UserBlock.c.target_id == self.id))).scalar()
        return bool(block_exists)

    def has_blocked_q(self, other_id: int):
        return select(UserBlock).where(UserBlock.c.actor_id == self.id, UserBlock.c.target_id == other_id).exists()

    def blocked_by_q(self, other_id: int):
        return select(UserBlock).where(UserBlock.c.actor_id == other_id, UserBlock.c.target_id == self.id).exists()

    @not_implemented()
    def end_friendship(self, other: User):
        """
        Remove any relationship between two users.
        Executed before block.
        """
        # TODO implement in 0.5
        ...

    def has_subscriber(self, other: User) -> bool:
        # TODO implement in 0.5
        return False #bool(session.execute(select(Friendship).where(...)).scalar())

    @classmethod
    def has_not_blocked(cls, actor: int, target: int):
        """
        Filter out a content if the author has blocked current user.  Returns a query.
        
        XXX untested.
        """

        # TODO add recognition
        actor_id = actor
        target_id = target

        qq= ~select(UserBlock).where(UserBlock.c.actor_id == actor_id, UserBlock.c.target_id == target_id).exists()
        return qq

    async def recompute_karma(self):
        """
        Recompute karma as of 0.4.0 karma handling
        """
        async with db as session:
            c = 0
            c += session.execute(select(func.count('*')).select_from(Post).where(Post.author == self)).scalar()
            c += session.execute(select(func.count('*')).select_from(PostUpvote).join(Post).where(Post.author == self, PostUpvote.c.is_downvote == False)).scalar()
            c -= session.execute(select(func.count('*')).select_from(PostUpvote).join(Post).where(Post.author == self, PostUpvote.c.is_downvote == True)).scalar()
            self.karma = c

        return c

    ## TODO are coroutines cacheable?
    @timed_cache(60, async_=True)
    async def strike_count(self) -> int:
        async with db as session:
            return (await session.execute(select(func.count('*')).select_from(UserStrike).where(UserStrike.user_id == self.id))).scalar()

    async def moderates(self, gu: Guild) -> bool:
        async with db as session:
            ## owner
            if gu.owner_id == self.id:
                return True
            ## admin or global mod
            if self.is_administrator:
                return True
            memb = (await session.execute(select(Member).where(Member.user_id == self.id, Member.guild_id == gu.id))).scalar()

            if memb is None:
                return False
            return memb.is_moderator

        ## TODO check banship?

    @makelist
    def badges(self, /):
        if self.is_administrator:
            yield 'administrator'

    badges: Callable[[], list[str]]

    @classmethod
    async def get_by_username(cls, name: str):
        """
        Get a user by its username, 
        """
        user_q = select(User).where(User.username == name)
        try:
            if current_user:
                user_q = user_q.where(~select(UserBlock).where(UserBlock.c.target_id == current_user.id).exists())
        except Exception as e:
            logger.error(f'{e}')

        async with db as session:
            user = (await session.execute(user_q)).scalar()
        return user

# UserBlock table is at the top !!

## END User

ModeratorInfo = namedtuple('ModeratorInfo', 'user is_owner')

class Guild(Base):
    __tablename__ = 'freak_topic'
    __table_args__ = (
        UniqueConstraint('id', name='topic_id_uniq'),
    )

    id = snowflake_column()
    
    name = Column(String(32), CheckConstraint(text("name = lower(name) AND name ~ '^[a-z0-9_-]+$'"), name='topic_name_valid'), unique=True, nullable=False)
    display_name = Column(String(64), nullable=False)
    description = Column(String(4096), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp(), index=True, nullable=False)
    owner_id = Column(BigInteger, ForeignKey('freak_user.id', name='topic_owner_id'), nullable=True)
    language = Column(String(16), server_default=text("'en-US'"))
    # true: prevent non-members from participating
    is_restricted = Column(Boolean, server_default=text('false'), nullable=False)
    # false: make the guild invite-only
    is_public = Column(Boolean, server_default=text('true'), nullable=False)

    # MUST NOT be filled in on post-0.2 instances
    legacy_id = Column(BigInteger, nullable=True)
    
    def url(self):
        return f'/+{self.name}'

    def handle(self):
        return f'+{self.name}'

    async def subscriber_count(self):
        async with db as session:
            count = (await session.execute(select(func.count('*')).select_from(Member).where(Member.guild == self, Member.is_subscribed == True))).scalar()
        return count

    # utilities
    owner = relationship(User, foreign_keys=owner_id, lazy='selectin')
    posts = relationship('Post', back_populates='guild', lazy='selectin')

    async def post_count(self):
        async with db as session:
            return (await session.execute(select(func.count('*')).select_from(Post).where(Post.guild == self))).scalar()

    async def has_subscriber(self, other: User) -> bool:
        if not want_User(other, var_name='other', prefix='Guild.has_subscriber()'):
            return False
        async with db as session:
            sub_ex = (await session.execute(select(Member).where(Member.user_id == other.id, Member.guild_id == self.id, Member.is_subscribed == True))).scalar()
        return bool(sub_ex)

    async def has_exiled(self, other: User) -> bool:
        if not want_User(other, var_name='other', prefix='Guild.has_exiled()'):
            return False
        async with db as session:
            u = (await session.execute(select(Member).where(Member.user_id == other.id, Member.guild_id == self.id))).scalar()
        return u.is_banned if u else False

    async def allows_posting(self, other: User) -> bool:
        async with db as session:
            # control owner_id instead of owner: the latter causes MissingGreenletError
            if self.owner_id is None:
                return False
            if other.is_disabled:
                return False
            mem: Member | None = (await session.execute(select(Member).where(Member.user_id == other.id, Member.guild_id == self.id))).scalar()
            if mem and mem.is_banned:
                return False
            if await other.moderates(self):
                return True
            if self.is_restricted:
                return (mem and mem.is_approved)
            return True

    async def moderators(self):
        async with db as session:
            if self.owner_id:
                owner = (await session.execute(select(User).where(User.id == self.owner_id))).scalar()
                yield ModeratorInfo(owner, True)
            for mem in (await session.execute(select(Member).where(Member.guild_id == self.id, Member.is_moderator == True))).scalars():
                if mem.user != self.owner and not mem.is_banned:
                    yield ModeratorInfo(mem.user, False)
    
    async def update_member(self, u: User | Member, /, **values):
        if isinstance(u, User):
            async with db as session:
                m = (await session.execute(select(Member).where(Member.user_id == u.id, Member.guild_id == self.id))).scalar()
                if m is None:
                    m = (await session.execute(insert(Member).values(
                        guild_id = self.id,
                        user_id = u.id,
                        **values
                    ).returning(Member))).scalar()
                    if m is None:
                        raise RuntimeError
                    return m
        else:
            m = u
        if len(values):
            async with db as session:
                session.execute(update(Member).where(Member.user_id == u.id, Member.guild_id == self.id).values(**values))
        return m

    def simple_info(self, *, typed=False):
        """
        Return essential informations for representing a guild in the REST
        """
        ## XXX change func name?
        gg = dict(
            id = Snowflake(self.id).to_b32l(),
            name = self.name,
            display_name = self.display_name,
            badges = []
        )
        if typed:
            gg['type'] = 'guild'
        return gg

    async def sub_info(self):
        """
        Guild info including subscriber count.
        """
        gg = self.simple_info()
        gg['subscriber_count'] = await self.subscriber_count()
        gg['post_count'] = await self.post_count()
        return gg
        

Topic = deprecated('renamed to Guild')(Guild)

## END Guild

class Member(Base):
    """
    User-Guild relationship. NEW in 0.4.0.
    """
    __tablename__ = 'freak_member'
    __table_args__ = (
        UniqueConstraint('user_id', 'guild_id', name='member_user_topic'),
    )

    ## Newer tables use SIQ. Older tables will gradually transition to SIQ as well.
    id = id_column(SiqType.MANYTOMANY)
    user_id = Column(BigInteger, ForeignKey('freak_user.id'))
    guild_id = Column(BigInteger, ForeignKey('freak_topic.id'))
    is_approved = Column(Boolean, server_default=text('false'), nullable=False)
    is_subscribed = Column(Boolean, server_default=text('false'), nullable=False)
    is_moderator = Column(Boolean, server_default=text('false'), nullable=False)

    # moderation
    banned_at = Column(DateTime, nullable=True)
    banned_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_banner_id'), nullable=True)
    banned_reason = Column(SmallInteger, server_default=text('0'), nullable=True)
    banned_until = Column(DateTime, nullable=True)
    banned_message = Column(String(256), nullable=True)

    user = relationship(User, primaryjoin = lambda: User.id == Member.user_id, lazy='selectin')
    guild = relationship(Guild, lazy='selectin')
    banned_by = relationship(User, primaryjoin = lambda: User.id == Member.banned_by_id, lazy='selectin')

    @property
    def is_banned(self):
        return self.banned_at is not None and (self.banned_until is None or self.banned_until <= datetime.datetime.now())


POST_TYPE_DEFAULT = 0
POST_TYPE_LINK = 1
    
class Post(Base):
    __tablename__ = 'freak_post'
    __table_args__ = (
        UniqueConstraint('id', name='post_id_uniq'),
    )

    id = snowflake_column()

    slug = Column(String(64), CheckConstraint("slug IS NULL OR (slug = lower(slug) AND slug ~ '^[a-z0-9_-]+$')", name='post_slug_valid'), nullable=True)
    title = Column(String(256), nullable=False)
    post_type = Column(SmallInteger, server_default=text('0'))
    author_id = Column(BigInteger, ForeignKey('freak_user.id', name='post_author_id'), nullable=True)
    topic_id = Column('topic_id', BigInteger, ForeignKey('freak_topic.id', name='post_topic_id'), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    created_ip = Column(String(64), default=get_remote_addr, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    privacy = Column(SmallInteger, server_default=text('0'))
    is_locked = Column(Boolean, server_default=text('false'))

    source_url = Column(String(1024), nullable=True)
    text_content = Column(String(65536), nullable=True)

    legacy_id = Column(BigInteger, nullable=True)

    removed_at = Column(DateTime, nullable=True)
    removed_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_banner_id'), nullable=True)
    removed_reason = Column(SmallInteger, nullable=True)

    # utilities
    author: Relationship[User] = relationship("User", foreign_keys=[author_id], lazy='selectin')#, back_populates="posts")
    guild: Relationship[Guild] = relationship("Guild", back_populates="posts", lazy='selectin')
    comments = relationship("Comment", back_populates="parent_post", lazy='selectin')
    upvoters = relationship("User", secondary=PostUpvote, back_populates='upvoted_posts', lazy='selectin')

    async def comment_count(self):
        async with db as session:
            return (await session.execute(select(func.count('*')).select_from(Comment).where(Comment.parent_post == self))).scalar()

    def topic_or_user(self) -> Guild | User:
        return self.guild or self.author
    
    def url(self):
        return self.topic_or_user().url() + '/comments/' + Snowflake(self.id).to_b32l() + '/' + (self.slug or '')
    
    @not_implemented('slugify is not a dependency as of now')
    def generate_slug(self) -> str:
        return "slugify.slugify(self.title, max_length=64)"

    async def upvotes(self) -> int:
        async with db as session:
            upv = (await session.execute(select(func.count('*')).select_from(PostUpvote).where(PostUpvote.c.post_id == self.id, PostUpvote.c.is_downvote == False))).scalar()
            dwv = (await session.execute(select(func.count('*')).select_from(PostUpvote).where(PostUpvote.c.post_id == self.id, PostUpvote.c.is_downvote == True))).scalar()
        return upv - dwv

    async def upvoted_by(self, user: User | None):
        if not want_User(user, var_name='user', prefix='Post.upvoted_by()'):
            return 0
        async with db as session:
            v = (await session.execute(select(PostUpvote.c.is_downvote).where(PostUpvote.c.voter_id == user.id, PostUpvote.c.post_id == self.id))).fetchone()
            if v is None:
                return 0
            if v == (True,):
                return -1
            if v == (False,):
                return 1
            logger.warning(f'unexpected value: {v}')
            return 0

    async def top_level_comments(self, limit=None):
        async with db as session:
            return (await session.execute(select(Comment).where(Comment.parent_comment == None, Comment.parent_post == self).order_by(Comment.created_at.desc()).limit(limit))).scalars()

    def report_url(self) -> str:
        return f'/report/post/{Snowflake(self.id):l}'

    async def report_count(self) -> int:
        async with db as session: return (await session.execute(select(func.count('*')).select_from(PostReport).where(PostReport.target_id == self.id, ~PostReport.update_status.in_((1, 2))))).scalar()

    @classmethod
    @timed_cache(1800, async_=True)
    async def count(cls):
        async with db as session:
            return (await session.execute(select(func.count('*')).select_from(cls))).scalar()

    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None

    @classmethod
    def not_removed(cls):
        return Post.removed_at == None

    @classmethod
    def visible_by(cls, user_id: int | None):
        return or_(Post.author_id == user_id, Post.privacy == 0)
        #return or_(Post.author_id == user_id, and_(Post.privacy.in_((0, 1)), ~Post.author.has_blocked_q(user_id)))

    def is_text_post(self):
        return self.post_type == POST_TYPE_DEFAULT

    def feed_info(self):
        return dict(
            id=Snowflake(self.id).to_b32l(),
            slug = self.slug,
            title = self.title,
            author = self.author.simple_info(),
            to = self.topic_or_user().simple_info(),
            created_at = self.created_at
        )

    async def feed_info_counts(self):
        pj = self.feed_info()
        if self.is_text_post():
            pj['content'] = self.text_content[:181]
        (pj['comment_count'], pj['votes'], pj['my_vote']) = await asyncio.gather(
            self.comment_count(), 
            self.upvotes(),
            self.upvoted_by(current_user.user)
        )
        return pj

class Comment(Base):
    __tablename__ = 'freak_comment'
    __table_args__ = (
        UniqueConstraint('id', name='comment_id_uniq'),
    )

    id = snowflake_column()

    author_id = Column(BigInteger, ForeignKey('freak_user.id', name='comment_author_id'), nullable=True)
    parent_post_id = Column(BigInteger, ForeignKey('freak_post.id', name='comment_parent_post_id', ondelete='cascade'), nullable=False)
    parent_comment_id = Column(BigInteger, ForeignKey('freak_comment.id', name='comment_parent_comment_id'), nullable=True)
    text_content = Column(String(16384), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), index=True)
    created_ip = Column(String(64), default=get_remote_addr, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    is_locked = Column(Boolean, server_default=text('false'))

    ## DO NOT FILL IN! intended for 0.2 or earlier
    legacy_id = Column(BigInteger, nullable=True)

    removed_at = Column(DateTime, nullable=True)
    removed_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_banner_id'), nullable=True)
    removed_reason = Column(SmallInteger, nullable=True)

    author = relationship('User', foreign_keys=[author_id], lazy='selectin')#, back_populates='comments')
    parent_post: Relationship[Post] = relationship("Post", back_populates="comments", foreign_keys=[parent_post_id], lazy='selectin')
    parent_comment, child_comments = parent_children('comment', parent_remote_side=Wanted('id'))

    def url(self):
        return self.parent_post.url() + f'/comment/{Snowflake(self.id):l}'

    def report_url(self) -> str:
        return f'/report/comment/{Snowflake(self.id):l}' 

    async def report_count(self) -> int:
        async with db as session:
            return (await session.execute(select(func.count('*')).select_from(PostReport).where(PostReport.target_id == self.id, ~PostReport.update_status.in_((1, 2))))).scalar()
    
    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None

    @classmethod
    def not_removed(cls):
        return Post.removed_at == None

class PostReport(Base):
    __tablename__ = 'freak_postreport'

    id = snowflake_column()
    
    author_id = Column(BigInteger, ForeignKey('freak_user.id', name='report_author_id'), nullable=True)
    target_type = Column(SmallInteger, nullable=False)
    target_id = Column(BigInteger, nullable=False)
    reason_code = Column(SmallInteger, nullable=False)
    update_status = Column(SmallInteger, server_default=text('0')) 
    created_at = Column(DateTime, server_default=func.current_timestamp())
    created_ip = Column(String(64), default=get_remote_addr, nullable=False)

    author = relationship('User', lazy='selectin')
    
    async def target(self):
        async with db as session:
            if self.target_type == REPORT_TARGET_POST:
                return (await session.execute(select(Post).where(Post.id == self.target_id))).scalar()
            elif self.target_type == REPORT_TARGET_COMMENT:
                return (await session.execute(select(Comment).where(Comment.id == self.target_id))).scalar()
            else:
                return self.target_id

    def is_critical(self):
        return self.reason_code in (
            121, 142, 210
        )

class UserStrike(Base):
    __tablename__ = 'freak_user_strike'

    id = id_column(SiqType.MULTI)

    user_id = Column(BigInteger, ForeignKey('freak_user.id', ondelete='cascade'), nullable=False)
    target_type = Column(SmallInteger, nullable=False)
    target_id = Column(BigInteger, nullable=False)
    target_content = Column(String(4096), nullable=True)
    reason_code = Column(SmallInteger, nullable=False)
    issued_at = Column(DateTime, server_default=func.current_timestamp())
    issued_by_id = Column(BigInteger, ForeignKey('freak_user.id'), nullable=True)

    user = relationship(User, primaryjoin= lambda: User.id == UserStrike.user_id, lazy='selectin')
    issued_by = relationship(User, primaryjoin= lambda: User.id == UserStrike.issued_by_id, lazy='selectin')

# PostUpvote table is at the top !!



