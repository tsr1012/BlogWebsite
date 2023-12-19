import os
import smtplib
import sqlalchemy.exc
import gunicorn
import psycopg2
from datetime import datetime
from functools import wraps
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from libgravatar import Gravatar
from forms import BlogForm, RegisterForm, LoginForm, CommentForm

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("APP_KEY")
Bootstrap5(app)
admin_id = "admin@email.com"

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'
db = SQLAlchemy()
db.init_app(app)

# CONFIGURE FLASK LOGIN
login_manager = LoginManager()
login_manager.init_app(app)

# CKEDITOR INITIALIZATION
ckeditor = CKEditor(app)


# SENDING MAIL TO OWNER WITH USER'S DETAILS ATTACHED
def send_mail(**kwargs):
    my_mail = os.getenv("MAILID")
    with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
        connection.starttls()
        connection.login(user=my_mail, password=os.getenv("PSWRD"))
        connection.sendmail(
            from_addr=my_mail,
            to_addrs=my_mail,
            msg=f"Subject:New Message\n\n"
                f"Name: {kwargs.get('name')}\n"
                f"Email: {kwargs.get('email')}\n"
                f"Phone: {kwargs.get('phone')}\n"
                f"Message: {kwargs.get('message')}"
        )


def gravatar(email):
    grav = Gravatar(email)
    return grav.get_image(
        size=100,
        default="retro",
        force_default=False,
        rating="pg",
        filetype_extension=False,
        use_ssl=True
    )


def time_delta(time):
    td = datetime.now() - time
    years, remainder = divmod(td.days, 365)
    months, days = divmod(remainder, 30)
    weeks, days = divmod(days, 7)

    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    time_units = [
        ("year", years),
        ("month", months),
        ("week", weeks),
        ("day", days),
        ("hour", hours),
        ("minute", minutes),
        ("second", seconds)
    ]

    for unit, value in time_units:
        if value > 0:
            return f"{value} {unit + 's' if value != 1 else unit} ago."
    return "Now."


def admin_only(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.email == admin_id:
            return abort(403)
        return f(*args, **kwargs)
    return wrapper


# CONFIGURE USERS TABLE
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)

    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    # The "comment_author" refers to the author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


# CONFIGURE BLOGS TABLE
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")
    # The "parent_post" refers to the parent_post property in the Comment class.
    comments = relationship("Comment", back_populates="parent_post")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)


# CONFIGURE COMMENTS TABLE
class Comment(db.Model):
    __tablename__ = "comments"
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Create reference to the User object, the "comments" refers to the posts property in the User class.
    comment_author = relationship("User", back_populates="comments")

    # Create Foreign Key, "blog_posts.id" the blog_posts refers to the tablename of BlogPost.
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    # Create reference to the BlogPost object, the "comments" refers to the posts property in the User class.
    parent_post = relationship("BlogPost", back_populates="comments")

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(2000), nullable=False)
    date_commented = db.Column(db.DateTime, nullable=False)


# CREATE USER_LOADER CALLBACK
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


with app.app_context():
    db.create_all()


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(
            name=form.name.data,
            email=form.email.data,
            password=generate_password_hash(form.password.data, method='scrypt', salt_length=8),
        )
        try:
            db.session.add(new_user)
            db.session.commit()
        except sqlalchemy.exc.IntegrityError:
            flash("You've already signed up with that email, log in instead.")
            return redirect(url_for("login"))

        # Login user upon registering
        login_user(new_user)
        return redirect(url_for("home"))
    title_text = "ThoughtFactory - Register"
    return render_template("register.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        # Find user in db
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        # If user not in db, deny
        if not user:
            flash("That email does not exist, please try again!")
            return redirect(url_for("login"))
        # If pass incorrect, deny
        elif not check_password_hash(user.password, password):
            flash("Incorrect Password, please try again!")
            return redirect(url_for("login"))
        # If both match, proceed
        else:
            login_user(user)
            return redirect(url_for("home"))
    title_text = "ThoughtFactory - Login"
    return render_template("login.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/')
def home():
    posts = db.session.execute(db.select(BlogPost)).scalars().all()
    # Checks if the current user is admin
    admin = current_user.is_authenticated and current_user.email == admin_id
    title_text = "ThoughtFactory - Homepage"
    return render_template("index.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           is_admin=admin,
                           all_posts=posts)


@app.route('/show_post/<int:post_id>', methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    comments_data = db.session.execute(db.select(Comment).where(Comment.post_id == post_id)).scalars().all()[::-1]
    if form.validate_on_submit():
        # Only logged-in users can comment
        if current_user.is_authenticated:
            new_comment = Comment(
                text=form.comment.data,
                date_commented=datetime.now(),
                comment_author=current_user,
                parent_post=requested_post,
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You need to be logged in to comment on posts.")
            return redirect(url_for("login"))

    # Checks if the current user is admin
    admin = current_user.is_authenticated and current_user.email == admin_id
    title_text = f"Blog - {requested_post.title}"
    return render_template("post.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           is_admin=admin,
                           post=requested_post,
                           form=form,
                           comments=comments_data,
                           grav_func=gravatar,
                           td_func=time_delta)


@app.route('/add_new_post', methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = BlogForm()
    if form.validate_on_submit():
        new_blog = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            author=current_user,
            img_url=form.img_url.data,
            body=form.body.data,
            date=datetime.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_blog)
        db.session.commit()
        return redirect(url_for("home"))
    title_text = "Submit your Blog"
    return render_template("make-post.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           form=form,
                           heading="New Post")


@app.route('/edit_post/<int:post_id>', methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = BlogForm(
        title=requested_post.title,
        subtitle=requested_post.subtitle,
        author=current_user,
        img_url=requested_post.img_url,
        body=requested_post.body,
    )
    if form.validate_on_submit():
        requested_post.title = form.title.data
        requested_post.subtitle = form.subtitle.data
        requested_post.img_url = form.img_url.data
        requested_post.body = form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))
    title_text = "Edit your Blog"
    return render_template("make-post.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           form=form,
                           heading="Edit Post")


@app.route('/delete_post/<int:post_id>')
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("home"))


@app.route('/delete_comment/<int:comment_id>')
def delete_comment(comment_id):
    comment_to_delete = db.get_or_404(Comment, comment_id)
    if current_user.email == admin_id or current_user.id == comment_to_delete.author_id:
        db.session.delete(comment_to_delete)
        db.session.commit()
    return redirect(url_for("show_post", post_id=comment_to_delete.post_id))


@app.route("/about")
def about():
    title_text = "ThoughtFactory - About"
    return render_template("about.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    status = False
    if request.method == "POST":
        send_mail(
            name=request.form["name"],
            email=request.form["email"],
            phone=request.form["phone"],
            message=request.form["message"],
        )
        status = True
    title_text = "ThoughtFactory - Contact"
    return render_template("contact.html",
                           title=title_text,
                           year=datetime.today().year,
                           logged_in=current_user.is_authenticated,
                           msg_sent=status)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
