

from flask import Blueprint, redirect, url_for
from flask_restx import Resource
from sqlalchemy import select
from suou import Snowflake
from suou.flask_sqlalchemy import require_auth

from suou.flask_restx import Api

from ..models import Post, User, db

rest_bp = Blueprint('rest', __name__, url_prefix='/v1')
rest = Api(rest_bp)

auth_required = require_auth(User, db)

@rest.route('/nurupo')
class Nurupo(Resource):
    def get(self):
        return dict(nurupo='ga')

## TODO coverage of REST is still partial, but it's planned
## to get complete sooner or later

## XXX there is a bug in suou.sqlalchemy.auth_required() — apparently, /user/@me does not
## redirect, neither is able to get user injected.
## Auth-based REST endpoints won't be fully functional until 0.6 in most cases

@rest.route('/user/@me')
class UserInfoMe(Resource):
    @auth_required(required=True)
    def get(self, user: User):
        return redirect(url_for('rest.UserInfo', user.id)), 302

@rest.route('/user/<b32l:id>')
class UserInfo(Resource):
    def get(self, id: int):
        ## TODO sanizize REST to make blocked users inaccessible
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
