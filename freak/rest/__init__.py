

from flask import Blueprint
from flask_restx import Resource, Api
from sqlalchemy import select
from suou import Snowflake

from ..models import Post, User, db

rest_bp = Blueprint('rest', __name__, url_prefix='/v1')
rest = Api(rest_bp)

@rest.route('/nurupo')
class Nurupo(Resource):
    def get(self):
        return dict(nurupo='ga')

## TODO coverage of REST is still partial, but it's planned
## to get complete sooner or later

@rest.route('/user/<b32l:id>')
class UserInfo(Resource):
    def get(self, id: int):
        u: User | None = db.session.execute(select(User).where(User.id == id)).scalar()
        if u is None:
            return dict(error='User not found'), 404
        uj = dict(
            id = f'{Snowflake(u.id):l}',
            username = u.username,
            display_name = u.display_name,
            joined_at = u.joined_at.isoformat('T'),
            karma = u.karma,
            age = u.age()
        )
        return dict(users={f'{Snowflake(id):l}': uj})

@rest.route('/post/<b32l:id>')
class SinglePost(Resource):
    def get(self, id: int):
        p: Post | None = db.session.execute(select(Post).where(Post.id == id)).scalar()
        if p is None:
            return dict(error='Not found'), 404
        pj = dict(
            id = f'{Snowflake(p.id):l}',
            title = p.title,
            author = p.author.simple_info(),
            to = p.topic_or_user().handle(),
            created_at = p.created_at.isoformat('T')
        )

        return dict(posts={f'{Snowflake(id):l}': pj})