from flask import Blueprint, render_template, redirect, abort, request
from flask_login import current_user

from ..search import SearchQuery
from ..models import Post, db, Topic
from ..algorithms import public_timeline, top_guilds_query, topic_timeline

bp = Blueprint('frontpage', __name__)

@bp.route('/')
def homepage():
    top_communities = [(x[0], x[1], 0) for x in 
            db.session.execute(top_guilds_query().limit(10)).fetchall()]

    if current_user and current_user.is_authenticated:
        # renders user's own timeline
        # TODO this is currently the public timeline.
        

        return render_template('feed.html', feed_type='foryou', l=db.paginate(public_timeline()),
            top_communities=top_communities)
    else:
        # Show a landing page to anonymous users.
        return render_template('landing.html', top_communities=top_communities)


@bp.route('/explore/')
def explore():
    return render_template('feed.html', feed_type='explore', l=db.paginate(public_timeline()))


@bp.route('/+<name>/')
def topic_feed(name):
    topic: Topic = db.session.execute(db.select(Topic).where(Topic.name == name)).scalar()

    if topic is None:
        abort(404)

    posts = db.paginate(topic_timeline(name))

    return render_template(
        'feed.html', feed_type='topic', feed_title=f'{topic.display_name} (+{topic.name})', l=posts, topic=topic)

@bp.route('/r/<name>/')
def topic_feed_r(name):
    return redirect('/+' + name + '/'), 302


@bp.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        q = request.form["q"]
        if q:
            results = db.paginate(SearchQuery(q).select(Post, [Post.title]).order_by(Post.created_at.desc()))
        else:
            results = None
        return render_template(
                "search.html",
                results=results,
                q = q
            )
    return render_template("search.html")
