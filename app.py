from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from PIL import Image, ImageDraw

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

# Настройка базы данных - поддержка PostgreSQL для Railway
database_url = os.environ.get('DATABASE_URL', 'sqlite:///furniture.db')
# Исправление для Heroku/Railway
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

@app.template_filter('cart_count')
def cart_count(user_id):
    return CartItem.query.filter_by(user_id=user_id).with_entities(db.func.sum(CartItem.quantity)).scalar() or 0

@app.template_filter('get_user')
def get_user(user_id):
    return User.query.get(user_id)

# Модели
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Furniture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Integer, default=0)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    furniture_id = db.Column(db.Integer, db.ForeignKey('furniture.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    furniture = db.relationship('Furniture')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    furniture_id = db.Column(db.Integer, db.ForeignKey('furniture.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    furniture = db.relationship('Furniture')

# Создаем таблицы
with app.app_context():
    db.create_all()

# Добавляем начальные товары
def add_initial_furniture():
    if Furniture.query.count() == 0:
        initial_furniture = [
            Furniture(
                name='Диван "Комфорт"',
                description='Просторный диван с мягкой обивкой, идеально подходит для гостиной',
                price=25000,
                category='living-room',
                image='images/sofa.jpg',
                stock=5
            ),
            Furniture(
                name='Кровать "Соня"',
                description='Двуспальная кровать с ортопедическим матрасом',
                price=35000,
                category='bedroom',
                image='images/bed.jpg',
                stock=3
            ),
            Furniture(
                name='Кухонный гарнитур "Стиль"',
                description='Современный кухонный гарнитур с встроенной техникой',
                price=45000,
                category='kitchen',
                image='images/kitchen.jpg',
                stock=2
            )
        ]
        db.session.add_all(initial_furniture)
        db.session.commit()

# Создаем администратора
def create_admin():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Администратор создан: admin/admin123')

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('У вас нет прав администратора', 'danger')
            return redirect(url_for('home'))
            
        return f(*args, **kwargs)
    return decorated_function

# Маршруты
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/category/<category>')
def category(category):
    furniture = Furniture.query.filter_by(category=category).all()
    return render_template('category.html', furniture=furniture, category=category)

@app.route('/add_to_cart/<int:furniture_id>', methods=['POST'])
def add_to_cart(furniture_id):
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    furniture = Furniture.query.get_or_404(furniture_id)
    cart_item = CartItem.query.filter_by(
        user_id=session['user_id'],
        furniture_id=furniture_id
    ).first()
    
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(
            user_id=session['user_id'],
            furniture_id=furniture_id,
            quantity=1
        )
        db.session.add(cart_item)
    
    db.session.commit()
    flash('Товар добавлен в корзину', 'success')
    return redirect(request.referrer or url_for('home'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    total = sum(item.furniture.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
def remove_from_cart(item_id):
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    cart_item = CartItem.query.filter_by(
        id=item_id,
        user_id=session['user_id']
    ).first_or_404()
    
    db.session.delete(cart_item)
    db.session.commit()
    
    flash('Товар удален из корзины', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    if not cart_items:
        flash('Корзина пуста', 'warning')
        return redirect(url_for('cart'))
    
    total = sum(item.furniture.price * item.quantity for item in cart_items)
    
    if request.method == 'POST':
        total_amount = total
        order = Order(
            user_id=session['user_id'],
            total_amount=total_amount,
            status='pending'
        )
        db.session.add(order)
        db.session.flush()
        
        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                furniture_id=item.furniture_id,
                quantity=item.quantity,
                price=item.furniture.price
            )
            db.session.add(order_item)
            CartItem.query.filter_by(id=item.id).delete()
        
        db.session.commit()
        flash('Заказ успешно оформлен', 'success')
        return redirect(url_for('orders'))
    
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    now = datetime.now()
    return render_template('orders.html', orders=orders, now=now, timedelta=timedelta)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
def cancel_order(order_id):
    if 'user_id' not in session:
        flash('Пожалуйста, войдите в систему', 'warning')
        return redirect(url_for('login'))
    
    order = Order.query.filter_by(id=order_id, user_id=session['user_id']).first_or_404()
    
    if order.status == 'completed':
        flash('Нельзя отменить выполненный заказ', 'danger')
        return redirect(url_for('orders'))
    
    order.status = 'cancelled'
    db.session.commit()
    
    flash('Заказ успешно отменен', 'success')
    return redirect(url_for('orders'))

@app.route('/search')
def search():
    query = request.args.get('query', '')
    category = request.args.get('category', '')
    
    furniture_query = Furniture.query
    
    if query:
        furniture_query = furniture_query.filter(
            db.or_(
                Furniture.name.ilike(f'%{query}%'),
                Furniture.description.ilike(f'%{query}%')
            )
        )
    
    if category:
        furniture_query = furniture_query.filter_by(category=category)
    
    furniture = furniture_query.all()
    return render_template('search.html', furniture=furniture, query=query, selected_category=category)

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        stock = int(request.form['stock'])
        
        # Выбираем изображение по умолчанию в зависимости от категории
        if category == 'living-room':
            image_path = 'images/sofa.jpg'
        elif category == 'bedroom':
            image_path = 'images/bed.jpg'
        elif category == 'kitchen':
            image_path = 'images/kitchen.jpg'
        else:
            image_path = 'uploads/default.jpg'
        
        # Проверяем, загружен ли файл изображения
        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            # Создаем уникальное имя файла
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
            
            # Обеспечиваем, что директория существует
            upload_dir = os.path.join('static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Полный путь для сохранения файла
            file_save_path = os.path.join(upload_dir, filename)
            
            try:
                # Сохраняем файл
                image.save(file_save_path)
                
                # Путь для базы данных (относительно static/)
                image_path = f"uploads/{filename}"
                
                print(f"Файл сохранен: {file_save_path}")
                print(f"Путь в БД: {image_path}")
            except Exception as e:
                print(f"Ошибка при сохранении изображения: {str(e)}")
                flash(f'Ошибка при сохранении изображения: {str(e)}', 'danger')
        
        furniture = Furniture(
            name=name,
            description=description,
            price=price,
            category=category,
            image=image_path,
            stock=stock
        )
        
        db.session.add(furniture)
        db.session.commit()
        flash(f'Товар успешно добавлен! Изображение: {image_path}', 'success')
        return redirect(url_for('admin'))
    
    furniture = Furniture.query.all()
    return render_template('admin.html', furniture=furniture)

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_furniture(id):
    furniture = Furniture.query.get_or_404(id)
    
    if request.method == 'POST':
        furniture.name = request.form['name']
        furniture.description = request.form['description']
        furniture.price = float(request.form['price'])
        
        # Если категория изменилась, обновляем изображение по умолчанию
        old_category = furniture.category
        furniture.category = request.form['category']
        furniture.stock = int(request.form['stock'])
        
        # Проверяем, загружен ли файл изображения
        if 'image' in request.files and request.files['image'].filename:
            image = request.files['image']
            # Создаем уникальное имя файла
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}"
            
            # Обеспечиваем, что директория существует
            upload_dir = os.path.join('static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Полный путь для сохранения файла
            file_save_path = os.path.join(upload_dir, filename)
            
            try:
                # Сохраняем файл
                image.save(file_save_path)
                
                # Путь для базы данных (относительно static/)
                image_path = f"uploads/{filename}"
                
                # Обновляем путь к изображению
                furniture.image = image_path
                
                print(f"Файл обновлен: {file_save_path}")
                print(f"Новый путь в БД: {image_path}")
            except Exception as e:
                print(f"Ошибка при сохранении изображения: {str(e)}")
                flash(f'Ошибка при сохранении изображения: {str(e)}', 'danger')
        # Если категория изменилась, но новая картинка не загружена, 
        # меняем картинку на стандартную для новой категории
        elif old_category != furniture.category:
            if furniture.category == 'living-room':
                furniture.image = 'images/sofa.jpg'
            elif furniture.category == 'bedroom':
                furniture.image = 'images/bed.jpg'
            elif furniture.category == 'kitchen':
                furniture.image = 'images/kitchen.jpg'
        
        db.session.commit()
        flash(f'Товар успешно обновлен! Изображение: {furniture.image}', 'success')
        return redirect(url_for('admin'))
    
    return render_template('edit_furniture.html', furniture=furniture)

@app.route('/admin/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_furniture(id):
    furniture = Furniture.query.get_or_404(id)
    db.session.delete(furniture)
    db.session.commit()
    flash('Товар успешно удален!', 'success')
    return redirect(url_for('admin'))

# Маршруты для авторизации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')

        if User.query.filter_by(username=username).first():
            flash('Такой пользователь уже существует')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь вы можете войти.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('Вы успешно вошли в систему!')
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы')
    return redirect(url_for('home'))

# Создаем базовый набор тестовых изображений
def create_default_images():
    # Создаем необходимые директории
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    
    # Список путей к дефолтным изображениям
    default_images = [
        'images/living-room.jpg',
        'images/bedroom.jpg', 
        'images/kitchen.jpg',
        'images/sofa.jpg',
        'images/bed.jpg',
        'uploads/default.jpg'
    ]
    
    # Создаем простые тестовые изображения, если файлы не существуют
    for img_path in default_images:
        full_path = os.path.join('static', img_path)
        if not os.path.exists(full_path):
            # Создаем директорию, если она не существует
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            try:
                # Создаем простое тестовое изображение
                # Создаем изображение 300x200 пикселей
                img = Image.new('RGB', (300, 200), color=(73, 109, 137))
                
                # Добавляем текст
                d = ImageDraw.Draw(img)
                d.text((10, 10), f"Тестовое изображение: {os.path.basename(img_path)}", fill=(255, 255, 0))
                
                # Сохраняем изображение
                img.save(full_path)
                print(f"Создано тестовое изображение: {full_path}")
            except Exception as e:
                # Если PIL не установлен или произошла ошибка, создаем пустой файл
                with open(full_path, 'wb') as f:
                    f.write(b'Test image')
                print(f"Создан пустой файл: {full_path} (Ошибка: {str(e)})")

# Проверяем и исправляем пути к изображениям в базе данных
def fix_image_paths():
    with app.app_context():
        # Получаем все товары
        furniture_items = Furniture.query.all()
        
        for item in furniture_items:
            # Проверяем существование файла изображения
            full_path = os.path.join('static', item.image)
            if not os.path.exists(full_path):
                print(f"Файл изображения не найден: {full_path}")
                
                # Устанавливаем изображение по умолчанию в зависимости от категории
                if item.category == 'living-room':
                    new_path = 'images/sofa.jpg'
                elif item.category == 'bedroom':
                    new_path = 'images/bed.jpg'
                elif item.category == 'kitchen':
                    new_path = 'images/kitchen.jpg'
                else:
                    new_path = 'uploads/default.jpg'
                
                # Обновляем путь к изображению
                item.image = new_path
                print(f"Обновлен путь к изображению для товара '{item.name}': {new_path}")
        
        # Сохраняем изменения в базе данных
        db.session.commit()
        print("Пути к изображениям обновлены")

# Флаг для проверки, были ли инициализированы данные
_is_initialized = False

# Функция для выполнения перед каждым запросом
@app.before_request
def initialize_on_first_request():
    global _is_initialized
    if not _is_initialized and os.environ.get('RAILWAY_ENVIRONMENT'):
        print("Инициализация приложения на Railway...")
        create_default_images()
        with app.app_context():
            try:
                db.create_all()
                # Добавляем начальные данные только если таблицы пустые
                if User.query.count() == 0:
                    create_admin()
                if Furniture.query.count() == 0:
                    add_initial_furniture()
                fix_image_paths()
                print("Инициализация базы данных завершена")
            except Exception as e:
                print(f"Ошибка при инициализации базы данных: {str(e)}")
        _is_initialized = True

if __name__ == '__main__':
    # Локальная разработка
    create_default_images()
    
    with app.app_context():
        db.create_all()
        add_initial_furniture()
        create_admin()
        fix_image_paths()
    
    # Определение порта для Railway или локального запуска
    port = int(os.environ.get('PORT', 5000))
    
    # Запуск приложения
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        # Production - режим для Railway
        app.run(host='0.0.0.0', port=port)
    else:
        # Режим разработки
        app.run(debug=True, port=port) 