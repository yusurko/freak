

from __future__ import annotations

from collections import namedtuple
import datetime
from functools import partial
from operator import or_
import re
from threading import Lock
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, insert, text, \
    CheckConstraint, Date, DateTime, Boolean, func, BigInteger, \
    SmallInteger, select, update, Table
from sqlalchemy.orm import Relationship, relationship
from flask_sqlalchemy import SQLAlchemy
from flask_login import AnonymousUserMixin
from suou import SiqType, Snowflake, Wanted, deprecated, not_implemented
from suou.sqlalchemy import create_session, declarative_base, id_column, parent_children, snowflake_column
from werkzeug.security import check_password_hash

from freak import app_config
from .utils import age_and_days, get_remote_addr, timed_cache


## Constants and enums

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
    'nobody deleted suspended default bot developer undefined null '
    'ai automod automoderator assistant privacy anonymous removed assistance '
    ## law enforcement corps and slurs because yes
    'pedo rape rapist nigger retard ncmec police cops 911 childsafety '
    'report dmca login logout security order66 gestapo ss hitler heilhitler kgb '
    'pedophile lolicon giphy tenor csam cp pedobear lolita lolice thanos '
    'loli kkk pnf adl cop tranny google trustandsafety safety ice fbi nsa it '
    ## VVVVIP
    'potus realdonaldtrump elonmusk teddysphotos mrbeast jkrowling pewdiepie '
    'elizabethii king queen pontifex hogwarts lumos alohomora isis daesh '
).split())

def username_is_legal(username: str) -> bool:
    if len(username) < 2 or len(username) > 100:
        return False

    if re.fullmatch(USERNAME_RE, username) is None:
        return False
    
    if username in ILLEGAL_USERNAMES:
        return False
    return True

## END constants and enums

Base = declarative_base(app_config.domain_name, app_config.secret_key, 
    snowflake_epoch=1577833200)
db = SQLAlchemy(model_class=Base)

CSI = create_session_interactively = partial(create_session, app_config.database_url)


# the BaseModel() class will be removed in 0.5
from .iding import new_id
@deprecated('id_column() and explicit id column are better. Will be removed in 0.5')
class BaseModel(Base):
    __abstract__ = True
    id = Column(BigInteger, primary_key=True, default=new_id)

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
    upvoted_posts = relationship("Post", secondary=PostUpvote, back_populates='upvoters')
    #comments = relationship("Comment", back_populates='author')
    
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
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def url(self):
        return f'/@{self.username}'

    @timed_cache(ttl=3600)
    def age(self):
        return age_and_days(self.gdpr_birthday)[0]

    def simple_info(self):
        """
        Return essential informations for representing a user in the REST
        """
        ## XXX change func name?
        return dict(
            id = Snowflake(self.id).to_b32l(),
            username = self.username,
            display_name = self.display_name,
            age = self.age()
            ## TODO add badges?
        )

    def reward(self, points=1):
        """
        Manipulate a user's karma on the fly
        """
        with Lock():
            db.session.execute(update(User).where(User.id == self.id).values(karma = self.karma + points))
            db.session.commit()

    def can_create_guild(self):
        ## TODO make guild creation requirements fully configurable
        return self.karma > app_config.create_guild_threshold or self.is_administrator

    can_create_community = deprecated('use .can_create_guild()')(can_create_guild)

    def handle(self):
        return f'@{self.username}'

    def check_password(self, password):
        return check_password_hash(self.passhash, password)

    @classmethod
    @timed_cache(1800)
    def active_count(cls) -> int:
        active_th = datetime.datetime.now() - datetime.timedelta(days=30)
        return db.session.execute(select(func.count(User.id)).select_from(cls).join(Post, Post.author_id == User.id).where(Post.created_at >= active_th).group_by(User.id)).scalar()

    def __repr__(self):
        return f'<{self.__class__.__name__} id:{self.id!r} username:{self.username!r}>'

    @classmethod
    def not_suspended(cls):
        return or_(User.banned_at == None, User.banned_until <= datetime.datetime.now())

    def has_blocked(self, other: User | None) -> bool:
        if other is None or not other.is_authenticated:
            return False
        return bool(db.session.execute(select(UserBlock).where(UserBlock.c.actor_id == self.id, UserBlock.c.target_id == other.id)).scalar())

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
        return False #bool(db.session.execute(select(Friendship).where(...)).scalar())

    @classmethod
    def has_not_blocked(cls, actor, target):
        """
        Filter out a content if the author has blocked current user.  Returns a query.
        
        XXX untested.
        """

        # TODO add recognition
        actor_id = actor
        target_id = target

        qq= ~select(UserBlock).where(UserBlock.c.actor_id == actor_id, UserBlock.c.target_id == target_id).exists()
        return qq

    def recompute_karma(self):
        c = 0
        c += db.session.execute(select(func.count('*')).select_from(Post).where(Post.author == self)).scalar()
        c += db.session.execute(select(func.count('*')).select_from(PostUpvote).join(Post).where(Post.author == self, PostUpvote.c.is_downvote == False)).scalar()
        c -= db.session.execute(select(func.count('*')).select_from(PostUpvote).join(Post).where(Post.author == self, PostUpvote.c.is_downvote == True)).scalar()

        self.karma = c

    @timed_cache(60)
    def strike_count(self) -> int:
        return db.session.execute(select(func.count('*')).select_from(UserStrike).where(UserStrike.user_id == self.id)).scalar()

    def moderates(self, gu: Guild) -> bool:
        ## owner
        if gu.owner_id == self.id:
            return True
        ## admin or global mod
        if self.is_administrator:
            return True
        memb = db.session.execute(select(Member).where(Member.user_id == self.id, Member.guild_id == gu.id)).scalar()

        if memb is None:
            return False
        return memb.is_moderator

        ## TODO check banship?

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

    def subscriber_count(self):
        return db.session.execute(select(func.count('*')).select_from(Member).where(Member.guild == self, Member.is_subscribed == True)).scalar()

    # utilities
    owner = relationship(User, foreign_keys=owner_id)
    posts = relationship('Post', back_populates='guild')

    def has_subscriber(self, other: User) -> bool:
        if other is None or not other.is_authenticated:
            return False
        return bool(db.session.execute(select(Member).where(Member.user_id == other.id, Member.guild_id == self.id, Member.is_subscribed == True)).scalar())

    def has_exiled(self, other: User) -> bool:
        if other is None or not other.is_authenticated:
            return False
        u = db.session.execute(select(Member).where(Member.user_id == other.id, Member.guild_id == self.id)).scalar()
        return u.is_banned if u else False

    def allows_posting(self, other: User) -> bool:
        if self.owner is None:
            return False
        if other.is_disabled:
            return False
        mem: Member | None = db.session.execute(select(Member).where(Member.user_id == other.id, Member.guild_id == self.id)).scalar() if other else None
        if mem and mem.is_banned:
            return False
        if other.moderates(self):
            return True
        if self.is_restricted:
            return (mem and mem.is_approved)
        return True


    def moderators(self):
        if self.owner:
            yield ModeratorInfo(self.owner, True)
        for mem in db.session.execute(select(Member).where(Member.guild_id == self.id, Member.is_moderator == True)).scalars():
            if mem.user != self.owner and not mem.is_banned:
                yield ModeratorInfo(mem.user, False)
    
    def update_member(self, u: User | Member, /, **values):
        if isinstance(u, User):
            m = db.session.execute(select(Member).where(Member.user_id == u.id, Member.guild_id == self.id)).scalar()
            if m is None:
                m = db.session.execute(insert(Member).values(
                    guild_id = self.id,
                    user_id = u.id,
                    **values
                ).returning(Member)).scalar()
                if m is None:
                    raise RuntimeError
                return m
        else:
            m = u
        if len(values):
            db.session.execute(update(Member).where(Member.user_id == u.id, Member.guild_id == self.id).values(**values))
        return m
        

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

    user = relationship(User, primaryjoin = lambda: User.id == Member.user_id)
    guild = relationship(Guild)
    banned_by = relationship(User, primaryjoin = lambda: User.id == Member.banned_by_id)

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
    author: Relationship[User] = relationship("User", lazy='selectin', foreign_keys=[author_id])#, back_populates="posts")
    guild: Relationship[Guild] = relationship("Guild", back_populates="posts", lazy='selectin')
    comments = relationship("Comment", back_populates="parent_post")
    upvoters = relationship("User", secondary=PostUpvote, back_populates='upvoted_posts')

    def topic_or_user(self) -> Guild | User:
        return self.guild or self.author
    
    def url(self):
        return self.topic_or_user().url() + '/comments/' + Snowflake(self.id).to_b32l() + '/' + (self.slug or '')
    
    @not_implemented('slugify is not a dependency as of now')
    def generate_slug(self) -> str:
        return "slugify.slugify(self.title, max_length=64)"

    def upvotes(self) -> int:
        return (db.session.execute(select(func.count('*')).select_from(PostUpvote).where(PostUpvote.c.post_id == self.id, PostUpvote.c.is_downvote == False)).scalar()
            - db.session.execute(select(func.count('*')).select_from(PostUpvote).where(PostUpvote.c.post_id == self.id, PostUpvote.c.is_downvote == True)).scalar())

    def upvoted_by(self, user: User | AnonymousUserMixin | None):
        if not user or not user.is_authenticated:
            return 0
        v: PostUpvote | None = db.session.execute(select(PostUpvote.c).where(PostUpvote.c.voter_id == user.id, PostUpvote.c.post_id == self.id)).fetchone()
        if v:
            if v.is_downvote:
                return -1
            return 1
        return 0

    def top_level_comments(self, limit=None):
        return db.session.execute(select(Comment).where(Comment.parent_comment == None, Comment.parent_post == self).order_by(Comment.created_at.desc()).limit(limit)).scalars()

    def report_url(self) -> str:
        return f'/report/post/{Snowflake(self.id):l}'

    def report_count(self) -> int:
        return db.session.execute(select(func.count('*')).select_from(PostReport).where(PostReport.target_id == self.id, ~PostReport.update_status.in_((1, 2)))).scalar()

    @classmethod
    @timed_cache(1800)
    def count(cls):
        return db.session.execute(select(func.count('*')).select_from(cls)).scalar()

    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None

    @classmethod
    def not_removed(cls):
        return Post.removed_at == None

    @classmethod
    def visible_by(cls, user_id: int | None):
        return or_(Post.author_id == user_id, Post.privacy.in_((0, 1)))


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

    author = relationship('User', foreign_keys=[author_id])#, back_populates='comments')
    parent_post: Relationship[Post] = relationship("Post", back_populates="comments", foreign_keys=[parent_post_id])
    parent_comment, child_comments = parent_children('comment', parent_remote_side=Wanted('id'))

    def url(self):
        return self.parent_post.url() + f'/comment/{Snowflake(self.id):l}'

    def report_url(self) -> str:
        return f'/report/comment/{Snowflake(self.id):l}' 

    def report_count(self) -> int:
        return db.session.execute(select(func.count('*')).select_from(PostReport).where(PostReport.target_id == self.id, ~PostReport.update_status.in_((1, 2)))).scalar()
    
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

    author = relationship('User')
    
    def target(self):
        if self.target_type == REPORT_TARGET_POST:
            return db.session.execute(select(Post).where(Post.id == self.target_id)).scalar()
        elif self.target_type == REPORT_TARGET_COMMENT:
            return db.session.execute(select(Comment).where(Comment.id == self.target_id)).scalar()
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

    user = relationship(User, primaryjoin= lambda: User.id == UserStrike.user_id)
    issued_by = relationship(User, primaryjoin= lambda: User.id == UserStrike.issued_by_id)

# PostUpvote table is at the top !!


