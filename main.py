from functools import wraps
from flask import Flask, render_template, redirect, request_started, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import smtplib
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")

login_manager = LoginManager()
login_manager.init_app(app)

ckeditor = CKEditor(app)
Bootstrap(app)


app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL1", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)



class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250),unique=True, nullable=False)
    password = db.Column(db.String(250), unique=False, nullable=False)
    username = db.Column(db.String(250), unique=True, nullable=False)
    posts = relationship("BlogPost", back_populates = "author")
    comments = relationship("Comment", back_populates = "commenter")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(250), nullable=False)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates = "posts")
    comments = relationship("Comment", back_populates = "blog_comment")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key = True)
    text = db.Column(db.Text, nullable = False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    commenter = relationship("User", back_populates = "comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    blog_comment = relationship("BlogPost", back_populates = "comments")

# db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1 and current_user.is_authenticated:
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods = ["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
            already_user = User.query.filter_by(email = form.email.data).first()
            if already_user:
                flash("You already have an account, Login instead!")
                return redirect(url_for("login"))
            user_email = form.email.data
            user_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
            user_name = form.username.data
            new_user = User(email = user_email, password = user_password, username = user_name)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)


@app.route('/login', methods = ["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email = form.email.data).first()
        if user :
                if check_password_hash(user.password, form.password.data) :
                    login_user(user)
                    return redirect(url_for("get_all_posts", user = user))
                else :
                    flash("Wrong password!")
                    return redirect(url_for("login"))
        else:
            flash("User account does not exists!")
    return render_template("login.html", form = form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods = ["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
       if not current_user.is_authenticated:
           flash("Login to comment on the post.")
           return redirect(url_for("login"))
       new_comment = Comment(text = form.comment_text.data, commenter = current_user, blog_comment = requested_post)
       db.session.add(new_comment)
       db.session.commit()
    return render_template("post.html", post=requested_post, form = form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods = ["GET", "POST"])
def contact():
    if request.method == "POST":
        with smtplib.SMTP("smtp.gmail.com") as connection :
            connection.starttls()
            connection.login(user = os.getenv("EMAIL"), password = os.getenv("PASSWORD"))
            connection.sendmail(
                                from_addr = request.form["email"],
                                to_addrs = os.getenv("EMAIL"),
                                msg = request.form["message"]) 
        return redirect(url_for("get_all_posts"))
    return render_template("contact.html")


@app.route("/new-post", methods = ["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug = True)
