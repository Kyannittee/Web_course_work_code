from flask import Flask, render_template, redirect, url_for, flash, request, Response, jsonify
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Genre, Movie, Quote
from forms import RegistrationForm, LoginForm, QuoteForm, MovieForm, GenreForm
from functools import wraps
from sqlalchemy import func, extract
from datetime import datetime
import csv
import json
from io import StringIO
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv

load_dotenv()

# Инициализация расширений
login_manager = LoginManager()
csrf = CSRFProtect()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Доступ запрещён. Требуются права администратора.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def create_app():
    app = Flask(__name__)

    # 1. Секретный ключ
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

    # 2. Адрес базы данных
    database_url = os.environ.get('DATABASE_URL')

    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        # Если DATABASE_URL нет, пробуем собрать из отдельных переменных (локальная разработка)
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_password = os.environ.get('DB_PASSWORD', '')
        db_name = os.environ.get('DB_NAME', 'quote_db')

        if not db_password:
            raise ValueError("DB_PASSWORD environment variable is not set for local development!")

        app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Инициализация расширений
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    csrf.init_app(app)

    def nl2br(value):
        if value:
            return value.replace('\n', '<br>')
        return value
    
    app.jinja_env.filters['nl2br'] = nl2br
    
    # Загрузка пользователя по ID (для Flask-Login)
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Главная страница (список цитат пользователя)
    @app.route('/')
    @login_required
    def index():
        quotes = Quote.query.filter_by(user_id=current_user.id).order_by(Quote.created_at.desc()).all()
        return render_template('index.html', quotes=quotes)
    
    # Добавление новой цитаты
    @app.route('/quote/add', methods=['GET', 'POST'])
    @login_required
    def add_quote():
        form = QuoteForm()
        
        # Передаём жанры для формы добавления фильма
        genres = Genre.query.order_by(Genre.name).all()
    
        if form.validate_on_submit():
            quote = Quote(
                text=form.text.data,
                character_name=form.character_name.data,
                timestamp=form.timestamp.data,
                movie_id=form.movie_id.data,
                user_id=current_user.id
            )
            db.session.add(quote)
            db.session.commit()
            flash('Цитата успешно добавлена!', 'success')
            return redirect(url_for('index'))
        
        return render_template('add_quote.html', form=form, genres=genres)
    
    # Детальный просмотр цитаты
    @app.route('/quote/<int:id>')
    @login_required
    def quote_detail(id):
        quote = Quote.query.get_or_404(id)
        
        # Проверка: цитата принадлежит текущему пользователю или админу
        if quote.user_id != current_user.id and current_user.role != 'admin':
            flash('У вас нет прав для просмотра этой цитаты', 'danger')
            return redirect(url_for('index'))
        
        return render_template('quote_detail.html', quote=quote)
    
    # Редактирование цитаты
    @app.route('/quote/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    def edit_quote(id):
        quote = Quote.query.get_or_404(id)
    
        # Проверка: цитата принадлежит текущему пользователю
        if quote.user_id != current_user.id and current_user.role != 'admin':
            flash('У вас нет прав для редактирования этой цитаты', 'danger')
            return redirect(url_for('index'))
        
        form = QuoteForm(obj=quote)
    
        if form.validate_on_submit():
            quote.text = form.text.data
            quote.character_name = form.character_name.data
            quote.timestamp = form.timestamp.data
            quote.movie_id = form.movie_id.data
            db.session.commit()
            flash('Цитата обновлена!', 'success')
            return redirect(url_for('index'))
        
        return render_template('edit_quote.html', form=form, quote=quote)

    # Удаление цитаты
    @app.route('/quote/delete/<int:id>')
    @login_required
    def delete_quote(id):
        quote = Quote.query.get_or_404(id)
        
        if quote.user_id != current_user.id and current_user.role != 'admin':
            flash('У вас нет прав для удаления этой цитаты', 'danger')
            return redirect(url_for('index'))
    
        db.session.delete(quote)
        db.session.commit()
        flash('Цитата удалена!', 'success')
        return redirect(url_for('index'))
    
    # Регистрация
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = RegistrationForm()  
        if form.validate_on_submit():
            hashed_password = generate_password_hash(form.password.data)
            user = User(login=form.login.data, password_hash=hashed_password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Добро пожаловать, {user.login}!', 'success')
            return redirect(url_for('index'))
        return render_template('register.html', form=form)
    
    # Вход
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(login=form.login.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                flash(f'Добро пожаловать, {user.login}!', 'success')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Неверный логин или пароль', 'danger')
        return render_template('login.html', form=form)
    
    # Выход
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('login'))
    
    @app.route('/movie/add/ajax', methods=['POST'])
    @login_required
    def add_movie_ajax():
        try:
            data = request.get_json()
            
            title = data.get('title')
            if not title:
                return jsonify({'success': False, 'error': 'Название фильма обязательно'})
            
            if len(title) >    100:
                return jsonify({'success': False, 'error': 'Название не может быть длиннее 255 символов'})
            
            # Проверка режиссёра
            director = data.get('director')
            if director and len(director) > 100:
                return jsonify({'success': False, 'error': 'Имя режиссёра не может быть длиннее 255 символов'})
            
            from datetime import datetime
            current_year = datetime.now().year
            
            release_year = data.get('release_year')
            if release_year:
                try:
                    release_year = int(release_year)
                    if release_year < 1888 or release_year > current_year:
                        return jsonify({'success': False, 'error': f'Год должен быть между 1888 и {current_year}'})
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'error': 'Год должен быть числом'})
            else:
                release_year = None
            
            # Проверка существующего фильма
            existing_movie = Movie.query.filter_by(title=title).first()
            if existing_movie:
                return jsonify({
                    'success': True,
                    'movie_id': existing_movie.id,
                    'movie_title': existing_movie.title,
                    'exists': True
                })
            
            genre_id = data.get('genre_id')
            if not genre_id:
                return jsonify({'success': False, 'error': 'Выберите жанр'})
            
            movie = Movie(
                title=title,
                release_year=release_year,
                director=director,
                genre_id=int(genre_id),
                added_by=current_user.id
            )
            db.session.add(movie)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'movie_id': movie.id,
                'movie_title': movie.title
            })
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Админ-панель (главная страница)
    @app.route('/admin')
    @login_required
    @admin_required
    def admin_panel():
        return redirect(url_for('admin_movies'))

    # Управление фильмами
    @app.route('/admin/movies')
    @login_required
    @admin_required
    def admin_movies():
        movies = Movie.query.order_by(Movie.title).all()
        return render_template('admin_movies.html', movies=movies)
    
    # Добавление фильма (админ)
    @app.route('/admin/movie/add', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_movie_add():
        form = MovieForm()
        if form.validate_on_submit():
            # ПРОВЕРКА: существует ли уже такой фильм (регистронезависимо)
            from sqlalchemy import func
            existing = Movie.query.filter(func.lower(Movie.title) == func.lower(form.title.data)).first()
            if existing:
                flash(f'Фильм "{form.title.data}" уже существует!', 'danger')
                return render_template('admin_movie_add.html', form=form)
            
            movie = Movie(
                title=form.title.data,
                release_year=form.release_year.data if form.release_year.data else None,
                director=form.director.data,
                genre_id=form.genre_id.data,
                added_by=current_user.id
            )
            db.session.add(movie)
            db.session.commit()
            flash(f'Фильм "{movie.title}" добавлен!', 'success')
            return redirect(url_for('admin_movies'))
        return render_template('admin_movie_add.html', form=form)

    # Редактирование фильма (админ)
    @app.route('/admin/movie/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_movie_edit(id):
        movie = Movie.query.get_or_404(id)
        form = MovieForm(obj=movie)
        
        if form.validate_on_submit():
            new_title = form.title.data
            
            # Проверяем, существует ли фильм с таким названием (кроме текущего)
            existing_movie = Movie.query.filter(
                Movie.title == new_title,
                Movie.id != id
            ).first()
        
            if existing_movie:
                # Найден дубликат, Предлагаем объединить
                return render_template('admin_merge_movies.html',
                                    old_movie=movie,
                                    new_movie=existing_movie,
                                    form=form)
            
            # Нет дубликата - просто обновляем
            movie.title = new_title
            movie.release_year = form.release_year.data if form.release_year.data else None
            movie.director = form.director.data
            movie.genre_id = form.genre_id.data
            db.session.commit()
            flash(f'Фильм "{movie.title}" обновлён!', 'success')
            return redirect(url_for('admin_movies'))
        
        return render_template('admin_movie_edit.html', form=form, movie=movie)
    
    @app.route('/admin/merge_movies', methods=['POST'])
    @login_required
    @admin_required
    def admin_merge_movies():
        old_movie_id = request.form.get('old_movie_id')
        new_movie_id = request.form.get('new_movie_id')
        action = request.form.get('action')
        
        old_movie = Movie.query.get_or_404(old_movie_id)
        new_movie = Movie.query.get_or_404(new_movie_id)
        
        if action == 'merge':
            # Переносим все цитаты на новый фильм
            Quote.query.filter_by(movie_id=old_movie_id).update({'movie_id': new_movie_id})
        
            # Удаляем дубликат
            db.session.delete(old_movie)
            db.session.commit()
            
            flash(f'Фильмы объединены! Цитаты перенесены в "{new_movie.title}"', 'success')
            
        elif action == 'rename':
            # Просто переименовываем, не объединяя
            old_movie.title = new_movie.title + " (дубликат)"
            db.session.commit()
            flash(f'Фильм переименован в "{old_movie.title}"', 'warning')
        
        return redirect(url_for('admin_movies'))

    # Удаление фильма (админ)
    @app.route('/admin/movie/delete/<int:id>')
    @login_required
    @admin_required
    def admin_movie_delete(id):
        movie = Movie.query.get_or_404(id)
        title = movie.title
        db.session.delete(movie)
        db.session.commit()
        flash(f'Фильм "{title}" удалён!', 'success')
        return redirect(url_for('admin_movies'))

    # Управление жанрами
    @app.route('/admin/genres')
    @login_required
    @admin_required
    def admin_genres():
        genres = Genre.query.order_by(Genre.name).all()
        return render_template('admin_genres.html', genres=genres)

    # Добавление жанра
    @app.route('/admin/genre/add', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_genre_add():
        form = GenreForm()
        if form.validate_on_submit():
            existing = Genre.query.filter_by(name=form.name.data).first()
            if existing:
                flash('Такой жанр уже существует!', 'danger')
                return render_template('admin_genre_form.html', form=form, title='Добавить жанр')
            
            genre = Genre(name=form.name.data)
            db.session.add(genre)
            db.session.commit()
            flash(f'Жанр "{genre.name}" добавлен!', 'success')
            return redirect(url_for('admin_genres'))
        return render_template('admin_genre_form.html', form=form, title='Добавить жанр')

    # Редактирование жанра
    @app.route('/admin/genre/edit/<int:id>', methods=['GET', 'POST'])
    @login_required
    @admin_required
    def admin_genre_edit(id):
        genre = Genre.query.get_or_404(id)
        form = GenreForm(obj=genre)
        
        if form.validate_on_submit():
            # Проверяем, существует ли жанр с таким именем (кроме текущего)
            existing_genre = Genre.query.filter(
                Genre.name == form.name.data,
                Genre.id != id
            ).first()
            
            if existing_genre:
                flash(f'Жанр "{form.name.data}" уже существует!', 'danger')
                return render_template('admin_genre_form.html', form=form, title='Редактировать жанр')
            
            genre.name = form.name.data
            db.session.commit()
            flash(f'Жанр переименован в "{genre.name}"!', 'success')
            return redirect(url_for('admin_genres'))
        
        return render_template('admin_genre_form.html', form=form, title='Редактировать жанр')

    # Удаление жанра
    @app.route('/admin/genre/delete/<int:id>')
    @login_required
    @admin_required
    def admin_genre_delete(id):
        genre = Genre.query.get_or_404(id)
        name = genre.name
        db.session.delete(genre)
        db.session.commit()
        flash(f'Жанр "{name}" удалён!', 'success')
        return redirect(url_for('admin_genres'))
    
    @app.route('/analytics')
    @login_required
    def analytics():
        months_ru = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        
        # ========== ЛИЧНАЯ АНАЛИТИКА (для всех пользователей) ==========
        # Топ-5 фильмов пользователя
        user_top_movies = db.session.query(
            Movie.title, 
            func.count(Quote.id).label('count')
        ).join(Quote, Movie.id == Quote.movie_id
        ).filter(Quote.user_id == current_user.id
        ).group_by(Movie.id
        ).order_by(func.count(Quote.id).desc()
        ).limit(5).all()
    
        # Жанры пользователя
        user_genre_stats = db.session.query(
            Genre.name,
            func.count(Quote.id).label('count')
        ).join(Movie, Genre.id == Movie.genre_id
        ).join(Quote, Movie.id == Quote.movie_id
        ).filter(Quote.user_id == current_user.id
        ).group_by(Genre.name).all()
    
        # Динамика пользователя по месяцам
        user_monthly_data = db.session.query(
            extract('month', Quote.created_at).label('month'),
            func.count(Quote.id).label('count')
        ).filter(Quote.user_id == current_user.id
        ).group_by('month').order_by('month').all()
        
        user_monthly_counts = [0] * 12
        for month, count in user_monthly_data:
            user_monthly_counts[int(month)-1] = count
    
        user_movie_titles = [m[0] for m in user_top_movies]
        user_movie_counts = [m[1] for m in user_top_movies]
        
        user_genre_names = [g[0] for g in user_genre_stats]
        user_genre_counts = [g[1] for g in user_genre_stats]
        
        # ОБЩАЯ АНАЛИТИКА (только для администратора) 
        if current_user.role == 'admin':
            # Топ-5 фильмов в системе
            admin_top_movies = db.session.query(
                Movie.title, 
                func.count(Quote.id).label('count')
            ).join(Quote, Movie.id == Quote.movie_id
            ).group_by(Movie.id
            ).order_by(func.count(Quote.id).desc()
            ).limit(5).all()
        
            # Жанры в системе
            admin_genre_stats = db.session.query(
                Genre.name,
                func.count(Quote.id).label('count')
            ).join(Movie, Genre.id == Movie.genre_id
            ).join(Quote, Movie.id == Quote.movie_id
            ).group_by(Genre.name).all()
        
            # Динамика в системе по месяцам
            admin_monthly_data = db.session.query(
                extract('month', Quote.created_at).label('month'),
                func.count(Quote.id).label('count')
            ).group_by('month').order_by('month').all()
        
            # Топ-5 активных пользователей
            top_users = db.session.query(
                User.login,
                func.count(Quote.id).label('count')
            ).join(Quote, User.id == Quote.user_id
            ).group_by(User.id
            ).order_by(func.count(Quote.id).desc()
            ).limit(5).all()
        
            admin_monthly_counts = [0] * 12
            for month, count in admin_monthly_data:
                admin_monthly_counts[int(month)-1] = count
            
            admin_movie_titles = [m[0] for m in admin_top_movies]
            admin_movie_counts = [m[1] for m in admin_top_movies]
            
            admin_genre_names = [g[0] for g in admin_genre_stats]
            admin_genre_counts = [g[1] for g in admin_genre_stats]
        
            user_names = [u[0] for u in top_users]
            user_counts = [u[1] for u in top_users]
            
            show_admin_stats = True
        else:
            show_admin_stats = False
    
        return render_template('analytics.html',
                            # Личная аналитика
                            user_movie_titles=user_movie_titles,
                            user_movie_counts=user_movie_counts,
                            user_genre_names=user_genre_names,
                            user_genre_counts=user_genre_counts,
                            user_monthly_counts=user_monthly_counts,
                            # Общая аналитика (только для админа)
                            show_admin_stats=show_admin_stats,
                            admin_movie_titles=admin_movie_titles if show_admin_stats else [],
                            admin_movie_counts=admin_movie_counts if show_admin_stats else [],
                            admin_genre_names=admin_genre_names if show_admin_stats else [],
                            admin_genre_counts=admin_genre_counts if show_admin_stats else [],
                            admin_monthly_counts=admin_monthly_counts if show_admin_stats else [],
                            user_names=user_names if show_admin_stats else [],
                            user_counts=user_counts if show_admin_stats else [],
                            months_ru=months_ru)
    
    @app.route('/export/csv')
    @login_required
    def export_csv():
        quotes = Quote.query.filter_by(user_id=current_user.id).all()
        
        # Создаём CSV в памяти
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['Фильм', 'Цитата', 'Персонаж', 'Таймкод', 'Дата добавления'])
        
        for quote in quotes:
            writer.writerow([
                quote.movie.title if quote.movie else '',
                quote.text,
                quote.character_name or '',
                quote.timestamp or '',
                quote.created_at.strftime('%d.%m.%Y %H:%M')
            ])
        
        output = si.getvalue().encode('utf-8-sig')
        return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=quotes.csv'})

    @app.route('/export/json')
    @login_required
    def export_json():
        quotes = Quote.query.filter_by(user_id=current_user.id).all()
        
        data = []
        for quote in quotes:
            data.append({
                'фильм': quote.movie.title if quote.movie else None,
                'цитата': quote.text,
                'персонаж': quote.character_name,
                'таймкод': quote.timestamp,
                'дата_добавления': quote.created_at.strftime('%d.%m.%Y %H:%M')
            })
    
        return Response(json.dumps(data, ensure_ascii=False, indent=2), 
                    mimetype='application/json', 
                    headers={'Content-Disposition': 'attachment; filename=quotes.json'})
    
    # Разрешённые расширения
    ALLOWED_EXTENSIONS = {'csv', 'json'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route('/import', methods=['GET', 'POST'])
    @login_required
    @csrf.exempt
    def import_quotes():
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('Файл не выбран', 'danger')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('Файл не выбран', 'danger')
                return redirect(request.url)
        
            if not allowed_file(file.filename):
                flash('Неподдерживаемый формат. Используйте CSV или JSON', 'danger')
                return redirect(request.url)
            
            content = file.read().decode('utf-8-sig')
            
            if file.filename.endswith('.csv'):
                import csv
                from io import StringIO
                
                reader = csv.DictReader(StringIO(content))
                imported = 0
                duplicated = 0
            
                fieldnames = reader.fieldnames
                if not fieldnames:
                    flash('CSV файл не содержит заголовков', 'danger')
                    return redirect(request.url)
                
                # Определяем заголовки
                title_field = None
                quote_field = None
                char_field = None
                time_field = None
            
                for field in fieldnames:
                    if field.lower() in ['фильм', 'movie', 'название']:
                        title_field = field
                    if field.lower() in ['цитата', 'quote', 'текст']:
                        quote_field = field
                    if field.lower() in ['персонаж', 'character']:
                        char_field = field
                    if field.lower() in ['таймкод', 'timestamp', 'time']:
                        time_field = field
            
                if not title_field or not quote_field:
                    flash('CSV файл должен содержать колонки "фильм" и "цитата"', 'danger')
                    return redirect(request.url)
                
                for row in reader:
                    movie_title = row.get(title_field, '').strip()
                    quote_text = row.get(quote_field, '').strip()
                    character = row.get(char_field, '').strip() if char_field else ''
                    timestamp = row.get(time_field, '').strip() if time_field else ''
                
                    if not movie_title or not quote_text:
                        continue
                    
                    # Ищем или создаём фильм
                    movie_obj = Movie.query.filter_by(title=movie_title).first()
                    if not movie_obj:
                        movie_obj = Movie(title=movie_title, added_by=current_user.id)
                        db.session.add(movie_obj)
                        db.session.commit()
                
                    # Проверяем на дубликат
                    existing = Quote.query.filter_by(
                        text=quote_text,
                        movie_id=movie_obj.id,
                        user_id=current_user.id
                    ).first()
                    
                    if existing:
                        duplicated += 1
                        continue
                
                    quote = Quote(
                        text=quote_text,
                        character_name=character,
                        timestamp=timestamp,
                        movie_id=movie_obj.id,
                        user_id=current_user.id
                    )
                    db.session.add(quote)
                    imported += 1
                
                db.session.commit()
            
                if duplicated > 0:
                    flash(f'Импортировано {imported} цитат. Пропущено дубликатов: {duplicated}', 'warning')
                else:
                    flash(f'Импортировано {imported} цитат из CSV', 'success')
                
            elif file.filename.endswith('.json'):
                import json
                data = json.loads(content)
                imported = 0
                duplicated = 0
            
                for item in data:
                    movie_title = item.get('фильм') or item.get('Фильм') or item.get('movie') or ''
                    quote_text = item.get('цитата') or item.get('Цитата') or item.get('quote') or ''
                    character = item.get('персонаж') or item.get('Персонаж') or item.get('character') or ''
                    timestamp = item.get('таймкод') or item.get('Таймкод') or item.get('timestamp') or ''
                    
                    if not movie_title or not quote_text:
                        continue
                
                    movie_obj = Movie.query.filter_by(title=movie_title).first()
                    if not movie_obj:
                        movie_obj = Movie(title=movie_title, added_by=current_user.id)
                        db.session.add(movie_obj)
                        db.session.commit()
                    
                    existing = Quote.query.filter_by(
                        text=quote_text,
                        movie_id=movie_obj.id,
                        user_id=current_user.id
                    ).first()
                
                    if existing:
                        duplicated += 1
                        continue
                    
                    quote = Quote(
                        text=quote_text,
                        character_name=character,
                        timestamp=timestamp,
                        movie_id=movie_obj.id,
                        user_id=current_user.id
                    )
                    db.session.add(quote)
                    imported += 1
                
                db.session.commit()
                
                if duplicated > 0:
                    flash(f'Импортировано {imported} цитат. Пропущено дубликатов: {duplicated}', 'warning')
                else:
                    flash(f'Импортировано {imported} цитат из JSON', 'success')
        
            return redirect(url_for('index'))
    
        return render_template('import.html')

    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'now': datetime.now()}
    
    return app

app = create_app()

if __name__ == '__main__':
    # Проверяем наличие секретного ключа
    if not os.environ.get('SECRET_KEY'):
        print(" WARNING: SECRET_KEY not set! Using default (insecure)")
    
    # Проверяем пароль БД
    if not os.environ.get('DB_PASSWORD'):
        print("ERROR: DB_PASSWORD environment variable is not set!")
        exit(1)
    
    with app.app_context():
        db.create_all()
        
        # Добавляем жанры, если их нет
        if Genre.query.count() == 0:
            genres = ['Фантастика', 'Драма', 'Комедия', 'Триллер', 'Ужасы', 'Боевик', 'Мелодрама']
            for name in genres:
                db.session.add(Genre(name=name))
            db.session.commit()
            print("Добавлены начальные жанры")
        else:
            print(f"Найдено {Genre.query.count()} жанров в базе данных")
    
    print("Запуск приложения...")
    app.run(debug=True)
