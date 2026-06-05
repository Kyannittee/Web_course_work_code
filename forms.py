from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp, NumberRange, EqualTo, ValidationError
from models import User, Genre, Movie  

class RegistrationForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired(), Length(min=3, max=100)])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтверждение пароля', 
                                     validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')
    
    def validate_login(self, login):
        user = User.query.filter_by(login=login.data).first()
        if user:
            raise ValidationError('Этот логин уже занят. Выберите другой.')

class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class QuoteForm(FlaskForm):
    text = TextAreaField('Текст цитаты', validators=[DataRequired()])
    character_name = StringField('Персонаж', validators=[
        Optional(),
        Length(max=100, message='Имя персонажа не может быть длиннее 100 символов')
    ])
    timestamp = StringField('Таймкод', validators=[
        Optional(),
        Regexp(r'^\d{1,2}:\d{2}(:\d{2})?$', 
               message='Таймкод должен быть в формате MM:SS или HH:MM:SS')
    ])
    movie_id = SelectField('Фильм', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить цитату')
    
    def __init__(self, *args, **kwargs):
        super(QuoteForm, self).__init__(*args, **kwargs)
        self.movie_id.choices = [(0, '-- Выберите фильм --')] + [(m.id, m.title) for m in Movie.query.order_by('title').all()]

class MovieForm(FlaskForm):
    title = StringField('Название фильма', validators=[DataRequired()])
    release_year = IntegerField('Год выпуска', validators=[
        Optional(),
        NumberRange(min=1888, max=2026, 
                   message='Год должен быть между 1888 и 2026')
    ])
    director = StringField('Режиссёр', validators=[
        Optional(),
        Length(max=100, message='Имя режиссёра не может быть длиннее 100 символов')
    ])
    genre_id = SelectField('Жанр', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Добавить фильм')
    
    def __init__(self, *args, **kwargs):
        super(MovieForm, self).__init__(*args, **kwargs)
        self.genre_id.choices = [(0, '-- Выберите жанр --')] + [(g.id, g.name) for g in Genre.query.order_by('name').all()]

class GenreForm(FlaskForm):
    name = StringField('Название жанра', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Добавить жанр')
