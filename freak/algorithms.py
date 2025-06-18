

from flask_login import current_user
from sqlalchemy import func, select
from .models import db, Post, Guild, User

def cuser() -> User:
    return current_user if current_user.is_authenticated else None

def cuser_id() -> int:
    return current_user.id if current_user.is_authenticated else None

def public_timeline():
    return select(Post).join(User, User.id == Post.author_id).where(
        Post.privacy == 0, User.not_suspended(), Post.not_removed(), User.has_not_blocked(Post.author_id, cuser_id())
    ).order_by(Post.created_at.desc())

def topic_timeline(gname):
    return select(Post).join(Guild).join(User, User.id == Post.author_id).where(
        Post.privacy == 0, Guild.name == gname, User.not_suspended(), Post.not_removed(), User.has_not_blocked(Post.author_id, cuser_id())
    ).order_by(Post.created_at.desc())

def user_timeline(user_id):
    return select(Post).join(User, User.id == Post.author_id).where(
        Post.visible_by(cuser()), User.id == user_id, User.not_suspended(), Post.not_removed(), User.has_not_blocked(Post.author_id, cuser_id())
    ).order_by(Post.created_at.desc())

def top_guilds_query():
    q_post_count = func.count().label('post_count')
    qr = select(Guild, q_post_count)\
        .join(Post, Post.topic_id == Guild.id).group_by(Guild)\
        .having(q_post_count > 5).order_by(q_post_count.desc())
    return qr

