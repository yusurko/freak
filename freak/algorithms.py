

from flask_login import current_user
from sqlalchemy import and_, distinct, func, select
from suou import not_implemented

from .models import Comment, Member, Post, Guild, User



def cuser() -> User:
    return current_user.user if current_user else None

def cuser_id() -> int:
    return current_user.id if current_user else None

def public_timeline():
    return select(Post).join(User, User.id == Post.author_id).where(
        Post.privacy == 0, User.not_suspended(), Post.not_removed(), User.has_not_blocked(Post.author_id, cuser_id())
    ).order_by(Post.created_at.desc())

def topic_timeline(gname):
    return select(Post).join(Guild, Guild.id == Post.topic_id).join(User, User.id == Post.author_id).where(
        Post.privacy == 0, Guild.name == gname, User.not_suspended(), Post.not_removed(), User.has_not_blocked(Post.author_id, cuser_id())
    ).order_by(Post.created_at.desc())

def user_timeline(user: User):
    return select(Post).join(User, User.id == Post.author_id).where(
        Post.visible_by(cuser_id()), Post.author_id == user.id, User.not_suspended(), Post.not_removed(), User.has_not_blocked(Post.author_id, cuser_id())
    ).order_by(Post.created_at.desc())

def new_comments(p: Post):
    return select(Comment).join(Post, Post.id == Comment.parent_post_id).join(User, User.id == Comment.author_id
        ).where(Comment.parent_post_id == p.id, Comment.parent_comment_id == None, Comment.not_removed(), User.has_not_blocked(Comment.author_id, cuser_id())
        ).order_by(Comment.created_at.desc())

def top_guilds_query():
    q_post_count = func.count(distinct(Post.id)).label('post_count')
    q_sub_count = func.count(distinct(Member.id)).label('sub_count')
    qr = select(Guild, q_post_count, q_sub_count)\
        .join(Post, Post.topic_id == Guild.id, isouter=True)\
        .join(Member, and_(Member.guild_id == Guild.id, Member.is_subscribed == True), isouter=True)\
        .group_by(Guild).having(q_post_count > 5).order_by(q_post_count.desc(), q_sub_count.desc())
    return qr


@not_implemented()
class Algorithms:
    """
    Return SQL queries for algorithms.
    """
    def __init__(self, me: User | None):
        self.me = me
    
    