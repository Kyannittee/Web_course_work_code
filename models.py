from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# Модель пользователя
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Связи
    quotes = db.relationship('Quote', backref='author', lazy=True, cascade='all, delete-orphan')
    movies_added = db.relationship('Movie', backref='added_by_user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.login}>'

# Модель жанра
class Genre(db.Model):
    __tablename__ = 'genres'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    movies = db.relationship('Movie', backref='genre', lazy=True)
    
    def __repr__(self):
        return f'<Genre {self.name}>'

# Модель фильма
class Movie(db.Model):
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    release_year = db.Column(db.Integer)
    director = db.Column(db.String(255))
    genre_id = db.Column(db.Integer, db.ForeignKey('genres.id', ondelete='SET NULL'))
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Связь с цитатами
    quotes = db.relationship('Quote', backref='movie', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Movie {self.title}>'

# Модель цитаты
class Quote(db.Model):
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    character_name = db.Column(db.String(255))
    timestamp = db.Column(db.String(20))
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    def __repr__(self):
        return f'<Quote {self.text[:50]}...>'