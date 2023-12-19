from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, TextAreaField
from wtforms.validators import InputRequired, URL, Email, Length
from flask_ckeditor import CKEditorField


# CONFIGURE WTFORM FOR CREATING A BLOG POST
class BlogForm(FlaskForm):
    title = StringField(label="Blog Post Title", validators=[InputRequired()])
    subtitle = StringField(label="Subtitle", validators=[InputRequired()])
    img_url = StringField(label="Blog Image URL", validators=[InputRequired(), URL()])
    body = CKEditorField(label="Blog Content", validators=[InputRequired()])
    submit = SubmitField(label="Submit Post", render_kw={"class": "btn btn-primary text-uppercase"})


class RegisterForm(FlaskForm):
    name = StringField(label="Name", validators=[InputRequired("Enter your name first!")])
    email = StringField(label="Email", validators=[InputRequired("Enter your Email!"), Email()])
    password = PasswordField(label="Password", validators=[InputRequired("Enter a Password"), Length(min=8, max=20)])
    submit = SubmitField(label="Sign Me Up!", render_kw={"class": "btn btn-primary text-uppercase"})


class LoginForm(FlaskForm):
    email = StringField(label="Email", validators=[InputRequired("Enter your Email!"), Email()])
    password = PasswordField(label="Password", validators=[InputRequired("Enter a Password")])
    submit = SubmitField(label="Let Me In!", render_kw={"class": "btn btn-primary text-uppercase"})


class CommentForm(FlaskForm):
    comment = TextAreaField(label="Comment",
                            validators=[InputRequired("Can't submit an empty comment!"), Length(max=2000)],
                            render_kw={"placeholder": "Type your comment"})
    submit = SubmitField(label="Submit Comment", render_kw={"class": "btn btn-primary text-uppercase px-3 py-2"})
