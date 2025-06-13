

from flask_login import current_user
from sqlalchemy import func, select
from .models import db, Post, Topic, User

def cuser() -> User:
    return current_user if current_user.is_authenticated else None

def public_timeline():
    return select(Post).join(User, User.id == Post.author_id).where(
        Post.privacy == 0, User.not_suspended(), Post.not_removed()
    ).order_by(Post.created_at.desc())

def topic_timeline(topic_name):
    return select(Post).join(Topic).join(User, User.id == Post.author_id).where(
        Post.privacy == 0, Topic.name == topic_name, User.not_suspended(), Post.not_removed()
    ).order_by(Post.created_at.desc())

def user_timeline(user_id):
    return select(Post).join(User, User.id == Post.author_id).where(
        Post.visible_by(cuser()), User.id == user_id, User.not_suspended(), Post.not_removed()
    ).order_by(Post.created_at.desc())

def top_guilds_query():
    q_post_count = func.count().label('post_count')
    qr = select(Topic, q_post_count)\
        .join(Post, Post.topic_id == Topic.id).group_by(Topic)\
        .having(q_post_count > 5).order_by(q_post_count.desc())
    return qr

