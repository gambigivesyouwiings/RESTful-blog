from flask import Flask, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from datetime import datetime
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from sqlalchemy.exc import IntegrityError
from functools import wraps
from flask import abort
import requests
import bleach
from flask_gravatar import Gravatar
import os
from dotenv import load_dotenv

load_dotenv("C:/Users/User/PycharmProjects/environment variables/.env")


# strips invalid tags/attributes
def strip_invalid_html(content):
    allowed_tags = ['a', 'abbr', 'acronym', 'address', 'b', 'br', 'div', 'dl', 'dt',
                    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
                    'li', 'ol', 'p', 'pre', 'q', 's', 'small', 'strike',
                    'span', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th',
                    'thead', 'tr', 'tt', 'u', 'ul']

    allowed_attrs = {
        'a': ['href', 'target', 'title'],
        'img': ['src', 'alt', 'width', 'height'],
    }

    cleaned = bleach.clean(content,
                           tags=allowed_tags,
                           attributes=allowed_attrs,
                           strip=True)

    return cleaned


# Gets data from api so as to initialize database
# posts = requests.get("https://api.npoint.io/88c2c1f644ef334058be").json()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("secret_key")
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)
# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy()
db.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user.id != 1:
            abort(403)
        return f(*args, **kwargs)

    return wrapper


# CONFIGURE TABLE
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # This is the parent class ID
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("Users", back_populates="posts")
    comments = relationship("Comments", back_populates="parent_post", cascade="all, delete")


class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    name = db.Column(db.String(250), unique=False, nullable=False)
    password = db.Column(db.String(250), unique=False, nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comments", cascade="all, delete", back_populates="comment_author")


class Comments(UserMixin, db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250), unique=False, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    comment_author = relationship("Users", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments", passive_deletes=True)


# with app.app_context():
#     db_posts = db.session.query(BlogPost).all()
#     for post in posts:
#         article = BlogPost(id=post["id"], title=post["title"], subtitle=post["subtitle"], date=post["date"],
#                            body=post["body"],
#                            img_url="https://images.fineartamerica.com/images-medium-large-5/cactus-blooms-peter-tellone.jpg")
#         db.session.add(article)
#         db.session.commit()
# WTForm


@app.route('/')
def get_all_posts():
    db_posts = db.session.query(BlogPost).all()
    return render_template("index.html", all_posts=db_posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        user = Users()
        user.name = request.form.get("name")
        user.email = request.form.get("email")
        password = request.form.get("password")
        hashed_password = generate_password_hash(password)
        user.password = hashed_password
        user.id = Users.query.count() + 1
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            flash('User already exists! Try logging instead')
            return redirect(url_for('login'))
        flash("successfully registered")
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "POST":
        user_email = request.form.get("email")
        user_password = request.form.get("password")
        try:
            user = db.session.query(Users).filter_by(email=user_email).first()
            pwhash = user.password
            check = check_password_hash(pwhash, user_password)

        except AttributeError:
            flash("That email seems to not be in our database")
            return redirect(url_for('login'))

        else:
            if check:
                login_user(user)
                print(user.name)
                return redirect(url_for('get_all_posts', name=user.name))
            else:
                flash("That password is not correct")
                return redirect(url_for('login'))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:index>", methods=["GET", "POST"])
def show_post(index):
    db_posts = db.session.query(BlogPost).all()
    all_comments = db.session.query(Comments).all()
    comment_form = CommentForm()
    requested_post = None
    blog_comments = []
    for blog_post in db_posts:
        if blog_post.id == index:
            requested_post = blog_post

    for comment in all_comments:
        if comment.post_id == requested_post.id:
            blog_comments.append(comment)

    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comments()
        new_comment.comment_author = current_user
        # new_comment.id = Comments.query.count()+1
        new_comment.parent_post = requested_post
        new_comment.text = request.form.get("body")

        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", index=requested_post.id))

    return render_template("post.html", post=requested_post, form=comment_form, blog_comments=blog_comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["POST", "GET"])
@login_required
def new():
    form = CreatePostForm()
    if request.method == "POST":
        num = BlogPost.query.count()
        print(num)
        x = datetime.now()
        full_date = x.strftime("%d %B %Y")
        form_body_content = request.form.get("body")
        body = strip_invalid_html(content=form_body_content)
        new_article = BlogPost(title=request.form.get("title"),
                               subtitle=request.form.get("subtitle"),
                               body=body,
                               author=current_user,
                               img_url=request.form.get("img_url"),
                               date=full_date
                               )
        db.session.add(new_article)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, heading="New")


@app.route("/edit-post/<int:index>", methods=["GET", "POST"])
@admin_only
def edit(index):
    edit_form = CreatePostForm(
        title=request.args.get("title"),
        img_url=request.args.get("img_url"),
        subtitle=request.args.get("subtitle"),
        author=request.args.get("author"),
        body=request.args.get("body")
    )
    if request.method == "POST":
        blog_to_edit = db.session.query(BlogPost).filter_by(id=index).first()
        edit_body_content = request.form.get("body")
        body = strip_invalid_html(content=edit_body_content)
        blog_to_edit.title = request.form.get("title")
        blog_to_edit.img_url = request.form.get("img_url")
        blog_to_edit.subtitle = request.form.get("subtitle")
        blog_to_edit.body = body
        blog_to_edit.author = current_user
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=edit_form, heading="Edit")


@app.route("/delete/<int:post_id>", methods=["GET", "POST"])
@admin_only
def delete(post_id):
    blog_to_delete = db.session.query(BlogPost).filter_by(id=post_id).first()
    db.session.delete(blog_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_posts"))


@app.route("/delete-comment/<int:post_id>/<int:comment_id>", methods=["GET", "POST"])
@login_required
def delete_comment(post_id, comment_id):
    comment_to_delete = Comments.query.get(comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', index=post_id))


@app.errorhandler(403)
def page_not_found(e):
    # note that we set the 403 status explicitly
    return render_template('403.html'), 403


if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

# This was for initializing the database
# with app.app_context():
# db_posts = db.session.query(BlogPost).all()
# for post in posts:
#     article = BlogPost(id=post["id"], title=post["title"], subtitle=post["subtitle"], date=post["date"],
#                        body=post["body"], author=post["author"],
#                        img_url="https://images.fineartamerica.com/images-medium-large-5/cactus-blooms-peter-tellone.jpg")
#     db.session.add(article)
#     db.session.commit()


#     db.create_all()
