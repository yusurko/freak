

from __future__ import annotations

from collections import namedtuple
import datetime
from functools import lru_cache
from operator import or_
from threading import Lock
from sqlalchemy import Column, String, ForeignKey, and_, text, \
    CheckConstraint, Date, DateTime, Boolean, func, BigInteger, \
    SmallInteger, select, insert, update, create_engine, Table
from sqlalchemy.orm import Relationship, declarative_base, relationship
from flask_sqlalchemy import SQLAlchemy
from flask_login import AnonymousUserMixin
from werkzeug.security import check_password_hash
import os
from .iding import new_id, id_to_b32l
from .utils import age_and_days, get_remote_addr, timed_cache


## Constants and enums

USER_ACTIVE   = 0
USER_INACTIVE = 1
USER_BANNED   = 2

ReportReason = namedtuple('ReportReason', 'num_code code description')

post_report_reasons = [
    ReportReason(110, 'hate_speech', 'Extreme hate speech / terrorism'),
    ReportReason(121, 'csam', 'Child abuse or endangerment'),
    ReportReason(142, 'revenge_sxm', 'Revenge porn'),
    ReportReason(122, 'black_market', 'Sale or promotion of regulated goods (e.g. firearms)'),
    ReportReason(171, 'xxx', 'Pornography'),
    ReportReason(111, 'tasteless', 'Extreme violence / gore'),
    ReportReason(180, 'impersonation', 'Impersonation'),
    ReportReason(141, 'doxing', 'Diffusion of PII (personally identifiable information)'),
    ReportReason(123, 'copyviol', 'This is my creation and someone else is using it without my permission/license'),
    ReportReason(140, 'bullying', 'Harassment, bullying, or suicide incitement'),
    ReportReason(112, 'lgbt_hate', 'Hate speech against LGBTQ+ or women'),
    ReportReason(150, 'security_exploit', 'Dangerous security exploit or violation'),
    ReportReason(190, 'false_information', 'False or deceiving information'),
    ReportReason(210, 'underage', 'Presence in violation of age limits (i.e. under 13, or minor in adult spaces)')
]

REPORT_REASON_STRINGS = { **{x.num_code: x.description for x in post_report_reasons}, **{x.code: x.description for x in post_report_reasons} }

REPORT_REASONS = {x.code: x.num_code for x in post_report_reasons}

REPORT_TARGET_POST = 1
REPORT_TARGET_COMMENT = 2

REPORT_UPDATE_PENDING = 0
REPORT_UPDATE_COMPLETE = 1
REPORT_UPDATE_REJECTED = 2
REPORT_UPDATE_ON_HOLD = 3

## END constants and enums

Base = declarative_base()
db = SQLAlchemy(model_class=Base)

def create_session_interactively():
    '''Create a session for querying the database in Python REPL.'''
    engine = create_engine(os.getenv('DATABASE_URL'))
    return db.Session(bind = engine)

CSI = create_session_interactively

## TODO replace with suou.declarative_base() - upcoming 0.4
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
    Column('is_downvote', Boolean, server_default=text('0'))
)

class User(BaseModel):
    __tablename__ = 'freak_user'

    id = Column(BigInteger, primary_key=True, default=new_id, unique=True)

    username = Column(String(32), CheckConstraint(text("username = lower(username) and username ~ '^[a-z0-9_-]+$'"), name="user_username_valid"), unique=True, nullable=False)
    display_name = Column(String(64), nullable=False)
    passhash = Column(String(256), nullable=False)
    email = Column(String(256), CheckConstraint(text("email IS NULL OR (email = lower(email) AND email LIKE '_%@_%.__%')"), name='user_email_valid'), nullable=True)
    gdpr_birthday = Column(Date, nullable=False)
    joined_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    joined_ip = Column(String(64), default=get_remote_addr, nullable=False)
    is_administrator = Column(Boolean, server_default=text('0'), nullable=False)
    is_disabled_by_user = Column(Boolean, server_default=text('0'), nullable=False)
    karma = Column(BigInteger, server_default=text('0'), nullable=False)
    legacy_id = Column(BigInteger, nullable=True)
    # TODO add pronouns and biography (upcoming 0.4)

    # moderation
    banned_at = Column(DateTime, nullable=True)
    banned_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_banner_id'), nullable=True)
    banned_reason = Column(SmallInteger, server_default=text('0'), nullable=True)
    banned_until = Column(DateTime, nullable=True)
    banned_message = Column(String(256), nullable=True)
    
    # utilities
    #posts = relationship("Post", back_populates='author', )
    upvoted_posts = relationship("Post", secondary=PostUpvote, back_populates='upvoters')
    #comments = relationship("Comment", back_populates='author')
    ## XXX posts and comments relationships are temporarily disabled because they make
    ## SQLAlchemy fail initialization of models — bricking the app.
    ## Posts are queried manually anyway

    @property
    def is_disabled(self):
        return self.banned_at is not None or self.is_disabled_by_user

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
            id = id_to_b32l(self.id),
            username = self.username,
            display_name = self.display_name,
            age = self.age()
            ## TODO add badges?
        )

    def reward(self, points=1):
        with Lock():
            db.session.execute(update(User).where(User.id == self.id).values(karma = self.karma + points))
            db.session.commit()

    def can_create_community(self):
        return self.karma > 15

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

class Topic(BaseModel):
    __tablename__ = 'freak_topic'

    id = Column(BigInteger, primary_key=True, default=new_id, unique=True)
    
    name = Column(String(32), CheckConstraint(text("name = lower(name) AND name ~ '^[a-z0-9_-]+$'"), name='topic_name_valid'), unique=True, nullable=False)
    display_name = Column(String(64), nullable=False)
    description = Column(String(4096), nullable=True)
    created_at = Column(DateTime, server_default=func.current_timestamp(), index=True, nullable=False)
    owner_id = Column(BigInteger, ForeignKey('freak_user.id', name='topic_owner_id'), nullable=True)
    language = Column(String(16), server_default=text("'en-US'"))
    privacy = Column(SmallInteger, server_default=text('0'))

    legacy_id = Column(BigInteger, nullable=True)
    
    def url(self):
        return f'/+{self.name}'

    def handle(self):
        return f'+{self.name}'

    # utilities
    posts = relationship('Post', back_populates='topic')


POST_TYPE_DEFAULT = 0
POST_TYPE_LINK = 1
    
class Post(BaseModel):
    __tablename__ = 'freak_post'

    id = Column(BigInteger, primary_key=True, default=new_id, unique=True)

    slug = Column(String(64), CheckConstraint("slug IS NULL OR (slug = lower(slug) AND slug ~ '^[a-z0-9_-]+$')", name='post_slug_valid'), nullable=True)
    title = Column(String(256), nullable=False)
    post_type = Column(SmallInteger, server_default=text('0'))
    author_id = Column(BigInteger, ForeignKey('freak_user.id', name='post_author_id'), nullable=True)
    topic_id = Column(BigInteger, ForeignKey('freak_topic.id', name='post_topic_id'), nullable=True)
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
    topic = relationship("Topic", back_populates="posts", lazy='selectin')
    comments = relationship("Comment", back_populates="parent_post")
    upvoters = relationship("User", secondary=PostUpvote, back_populates='upvoted_posts')

    def topic_or_user(self) -> Topic | User:
        return self.topic or self.author
    
    def url(self):
        return self.topic_or_user().url() + '/comments/' + id_to_b32l(self.id) + '/' + (self.slug or '')
    
    def generate_slug(self):
        return slugify.slugify(self.title, max_length=64)

    def upvotes(self) -> int:
        return (db.session.execute(select(func.count('*')).select_from(PostUpvote).where(PostUpvote.c.post_id == self.id, PostUpvote.c.is_downvote == False)).scalar()
            - db.session.execute(select(func.count('*')).select_from(PostUpvote).where(PostUpvote.c.post_id == self.id, PostUpvote.c.is_downvote == True)).scalar())

    def upvoted_by(self, user: User | AnonymousUserMixin | None):
        if not user or not user.is_authenticated:
            return 0
        v = db.session.execute(db.select(PostUpvote.c).where(PostUpvote.c.voter_id == user.id, PostUpvote.c.post_id == self.id)).fetchone()
        if v:
            if v.is_downvote:
                return -1
            return 1
        return 0

    def top_level_comments(self, limit=None):
        return db.session.execute(select(Comment).where(Comment.parent_comment == None, Comment.parent_post == self).order_by(Comment.created_at.desc()).limit(limit)).scalars()

    def report_url(self) -> str:
        return '/report/post/' + id_to_b32l(self.id)

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
    def visible_by(cls, user: User):
        return or_(Post.author_id == user.id, Post.privacy.in_((0, 1)))


class Comment(BaseModel):
    __tablename__ = 'freak_comment'

    # tweak to allow remote_side to work
    ## XXX will be changed in 0.4 to suou.id_column()
    id = Column(BigInteger, primary_key=True, default=new_id, unique=True)

    author_id = Column(BigInteger, ForeignKey('freak_user.id', name='comment_author_id'), nullable=True)
    parent_post_id = Column(BigInteger, ForeignKey('freak_post.id', name='comment_parent_post_id'), nullable=False)
    parent_comment_id = Column(BigInteger, ForeignKey('freak_comment.id', name='comment_parent_comment_id'), nullable=True)
    text_content = Column(String(16384), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), index=True)
    created_ip = Column(String(64), default=get_remote_addr, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    is_locked = Column(Boolean, server_default=text('false'))

    legacy_id = Column(BigInteger, nullable=True)

    removed_at = Column(DateTime, nullable=True)
    removed_by_id = Column(BigInteger, ForeignKey('freak_user.id', name='user_banner_id'), nullable=True)
    removed_reason = Column(SmallInteger, nullable=True)

    author = relationship('User', foreign_keys=[author_id])#, back_populates='comments')
    parent_post = relationship("Post", back_populates="comments", foreign_keys=[parent_post_id])
    parent_comment = relationship("Comment", back_populates="child_comments", remote_side=[id])
    child_comments = relationship("Comment", back_populates="parent_comment")

    def url(self):
        return self.parent_post.url() + '/comment/' + id_to_b32l(self.id)

    def report_url(self) -> str:
        return '/report/comment/' + id_to_b32l(self.id)

    def report_count(self) -> int:
        return db.session.execute(select(func.count('*')).select_from(PostReport).where(PostReport.target_id == self.id, ~PostReport.update_status.in_((1, 2)))).scalar()
    
    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None

    @classmethod
    def not_removed(cls):
        return Post.removed_at == None

class PostReport(BaseModel):
    __tablename__ = 'freak_postreport'
    
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

# PostUpvote table is at the top !!


