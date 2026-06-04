from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
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
    character_name = StringField('Персонаж (опционально)')
    timestamp = StringField('Таймкод (опционально)', render_kw={"placeholder": "чч:мм:сс"})
    movie_id = SelectField('Фильм', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить цитату')
    
    def __init__(self, *args, **kwargs):
        super(QuoteForm, self).__init__(*args, **kwargs)
        self.movie_id.choices = [(0, '-- Выберите фильм --')] + [(m.id, m.title) for m in Movie.query.order_by('title').all()]

class MovieForm(FlaskForm):
    title = StringField('Название фильма', validators=[DataRequired()])
    release_year = StringField('Год выпуска')
    director = StringField('Режиссёр')
    genre_id = SelectField('Жанр', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Добавить фильм')
    
    def __init__(self, *args, **kwargs):
        super(MovieForm, self).__init__(*args, **kwargs)
        self.genre_id.choices = [(0, '-- Выберите жанр --')] + [(g.id, g.name) for g in Genre.query.order_by('name').all()]

class GenreForm(FlaskForm):
    name = StringField('Название жанра', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Добавить жанр')