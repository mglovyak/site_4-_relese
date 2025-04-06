from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from PIL import Image, ImageDraw
from werkzeug.utils import secure_filename
from mail_config import init_mail, send_notification
import time

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
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
db = SQLAlchemy(app)

mail = init_mail(app)

@app.template_filter('cart_count')
def cart_count(user_id):
    return CartItem.query.filter_by(user_id=user_id).with_entities(db.func.sum(CartItem.quantity)).scalar() or 0

@app.context_processor
def utility_processor():
    def get_categories():
        return Category.query.order_by(Category.name).all()
    
    def cart_count(user_id):
        return CartItem.query.filter_by(user_id=user_id).count()
    
    def get_user(user_id):
        return User.query.get(user_id)
    
    return dict(
        get_categories=get_categories,
        cart_count=cart_count,
        get_user=get_user
    )

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

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    furniture = db.relationship('Furniture', backref='category_rel', lazy=True)

class Furniture(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
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

# Добавляем начальные категории
def add_initial_categories():
    if Category.query.count() == 0:
        categories = [
            Category(name='Гостиная', slug='living-room', description='Мебель для гостиной'),
            Category(name='Спальня', slug='bedroom', description='Мебель для спальни'),
            Category(name='Кухня', slug='kitchen', description='Мебель для кухни'),
            Category(name='Ванная', slug='bathroom', description='Мебель для ванной'),
            Category(name='Офис', slug='office', description='Офисная мебель'),
            Category(name='Детская', slug='children', description='Мебель для детской комнаты'),
            Category(name='Прихожая', slug='hallway', description='Мебель для прихожей и коридора'),
            Category(name='Балкон и терраса', slug='outdoor', description='Мебель для балкона и террасы'),
            Category(name='Мягкая мебель', slug='soft-furniture', description='Диваны, кресла и пуфы')
        ]
        db.session.add_all(categories)
        db.session.commit()

# Добавляем начальные товары
def add_initial_furniture():
    if Furniture.query.count() == 0:
        try:
            # Получаем категории
            categories = {cat.slug: cat.id for cat in Category.query.all()}
            
            if not categories:
                print("Ошибка: категории не найдены")
                return

            initial_furniture = [
                Furniture(
                    name='Диван "Комфорт"',
                    description='Просторный диван с мягкой обивкой',
                    price=25000,
                    category_id=categories['living-room'],
                    image='images/living-room.jpg',
                    stock=5
                ),
                Furniture(
                    name='Кровать "Соня"',
                    description='Двуспальная кровать с ортопедическим матрасом',
                    price=35000,
                    category_id=categories['bedroom'],
                    image='images/bedroom.jpg',
                    stock=3
                ),
                Furniture(
                    name='Кухонный гарнитур "Стиль"',
                    description='Современный кухонный гарнитур',
                    price=45000,
                    category_id=categories['kitchen'],
                    image='images/kitchen.jpg',
                    stock=2
                ),
                Furniture(
                    name='Шкаф для ванной "Волна"',
                    description='Влагостойкий шкаф для ванной комнаты',
                    price=15000,
                    category_id=categories['bathroom'],
                    image='images/bathroom.jpg',
                    stock=4
                ),
                Furniture(
                    name='Письменный стол "Профи"',
                    description='Эргономичный офисный стол',
                    price=12000,
                    category_id=categories['office'],
                    image='images/office.jpg',
                    stock=6
                ),
                Furniture(
                    name='Детская кровать "Сказка"',
                    description='Красивая и безопасная кровать для детей',
                    price=18000,
                    category_id=categories['children'],
                    image='images/children.jpg',
                    stock=3
                ),
                Furniture(
                    name='Шкаф для прихожей "Визит"',
                    description='Вместительный шкаф с зеркалом для прихожей',
                    price=22000,
                    category_id=categories['hallway'],
                    image='images/hallway.jpg',
                    stock=4
                ),
                Furniture(
                    name='Комплект для балкона "Бриз"',
                    description='Легкий и стильный комплект мебели для балкона',
                    price=15000,
                    category_id=categories['outdoor'],
                    image='images/outdoor.jpg',
                    stock=2
                ),
                Furniture(
                    name='Диван-кровать "Комфорт Люкс"',
                    description='Удобный раскладной диван с механизмом еврокнижка',
                    price=45000,
                    category_id=categories['soft-furniture'],
                    image='images/soft-furniture.jpg',
                    stock=3
                )
            ]
            
            print("Добавление начальных товаров...")
            for item in initial_furniture:
                print(f"Добавление {item.name} для категории {item.category_id}")
                db.session.add(item)
            
            db.session.commit()
            print("Начальные товары успешно добавлены")
        except Exception as e:
            print(f"Ошибка при добавлении начальных товаров: {str(e)}")
            import traceback
            print(traceback.format_exc())
            db.session.rollback()

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
    category_obj = Category.query.filter_by(slug=category).first_or_404()
    furniture = Furniture.query.filter_by(category_id=category_obj.id).all()
    return render_template('category.html', furniture=furniture, category=category_obj)

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

def send_order_notification(order):
    """Отправка уведомления админу о новом заказе"""
    admin = User.query.filter_by(is_admin=True).first()
    if not admin:
        return
    
    items_list = "\n".join([
        f"- {item.furniture.name} (количество: {item.quantity}, цена: {item.price} ₽)"
        for item in order.items
    ])
    
    customer = User.query.get(order.user_id)
    
    subject = f"Новый заказ #{order.id}"
    body = f"""
    Поступил новый заказ!
    
    Номер заказа: {order.id}
    Покупатель: {customer.username}
    Email покупателя: {customer.email}
    Сумма заказа: {order.total_amount} ₽
    
    Товары в заказе:
    {items_list}
    
    Для просмотра деталей заказа перейдите по ссылке:
    {url_for('admin_order_detail', id=order.id, _external=True)}
    """
    
    send_notification(subject, admin.email, body)

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
        
        # Отправляем уведомление админу
        send_order_notification(order)
        
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
    category_slug = request.args.get('category', '')
    
    furniture_query = Furniture.query
    
    if query:
        furniture_query = furniture_query.filter(
            db.or_(
                Furniture.name.ilike(f'%{query}%'),
                Furniture.description.ilike(f'%{query}%')
            )
        )
    
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first()
        if category:
            furniture_query = furniture_query.filter_by(category_id=category.id)
    
    furniture = furniture_query.all()
    return render_template('search.html', furniture=furniture, query=query, selected_category=category_slug)

def handle_image_upload(image_file, default_category_path):
    """Обработка загрузки изображения"""
    if image_file and image_file.filename:
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image_file.filename}")
        upload_dir = os.path.join('static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        try:
            image_file.save(file_path)
            return f"uploads/{filename}"
        except Exception as e:
            print(f"Ошибка при сохранении изображения: {str(e)}")
            flash(f'Ошибка при сохранении изображения: {str(e)}', 'danger')
            return default_category_path
    return default_category_path

@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        stock = int(request.form['stock'])
        
        # Определяем изображение по умолчанию для категории
        default_image = {
            'living-room': 'images/sofa.jpg',
            'bedroom': 'images/bed.jpg',
            'kitchen': 'images/kitchen.jpg'
        }.get(category, 'uploads/default.jpg')
        
        # Обрабатываем загрузку изображения
        image_path = handle_image_upload(request.files.get('image'), default_image)
        
        furniture = Furniture(
            name=name,
            description=description,
            price=price,
            category_id=category,
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
        old_category = furniture.category_id
        furniture.category_id = request.form['category']
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
        elif old_category != furniture.category_id:
            if furniture.category_id == 'living-room':
                furniture.image = 'images/sofa.jpg'
            elif furniture.category_id == 'bedroom':
                furniture.image = 'images/bed.jpg'
            elif furniture.category_id == 'kitchen':
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

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/products')
@admin_required
def admin_products():
    products = Furniture.query.all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    if request.method == 'POST':
        image = request.files['image']
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f'images/{filename}'
        else:
            image_path = 'images/default.jpg'

        new_product = Furniture(
            name=request.form['name'],
            description=request.form['description'],
            price=float(request.form['price']),
            category_id=request.form['category'],
            image=image_path,
            stock=int(request.form['stock'])
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Товар успешно добавлен', 'success')
        return redirect(url_for('admin_products'))
    return render_template('admin/add_product.html')

@app.route('/admin/product/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_product(id):
    product = Furniture.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash('Товар успешно удален', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/order/<int:id>')
@admin_required
def admin_order_detail(id):
    order = Order.query.get_or_404(id)
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/order/status/<int:id>', methods=['POST'])
@admin_required
def admin_update_order_status(id):
    order = Order.query.get_or_404(id)
    order.status = request.form['status']
    db.session.commit()
    flash('Статус заказа обновлен', 'success')
    return redirect(url_for('admin_order_detail', id=id))

@app.route('/admin/product/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(id):
    furniture = Furniture.query.get_or_404(id)
    
    if request.method == 'POST':
        furniture.name = request.form['name']
        furniture.description = request.form['description']
        furniture.price = float(request.form['price'])
        furniture.category_id = int(request.form['category_id'])
        furniture.stock = int(request.form['stock'])
        
        # Обработка загрузки нового изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # Генерируем безопасное имя файла
                filename = secure_filename(file.filename)
                # Добавляем временную метку к имени файла
                filename = f"{int(time.time())}_{filename}"
                # Сохраняем файл
                file.save(os.path.join(app.static_folder, 'images', filename))
                # Обновляем путь к изображению в базе данных
                furniture.image = f'images/{filename}'
        
        try:
            db.session.commit()
            flash('Товар успешно обновлен', 'success')
            return redirect(url_for('admin_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении товара: {str(e)}', 'danger')
    
    return render_template('admin/edit_product.html', furniture=furniture)

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
        'images/bathroom.jpg',
        'images/office.jpg',
        'images/children.jpg',
        'images/hallway.jpg',
        'images/outdoor.jpg',
        'images/soft-furniture.jpg',
        'images/default-category.jpg'
    ]
    
    # Создаем простые тестовые изображения, если файлы не существуют
    for img_path in default_images:
        full_path = os.path.join('static', img_path)
        if not os.path.exists(full_path):
            # Создаем директорию, если она не существует
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            try:
                # Создаем простое тестовое изображение
                # Создаем изображение 800x600 пикселей
                img = Image.new('RGB', (800, 600), color=(73, 109, 137))
                
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
                if item.category_id == 'living-room':
                    new_path = 'images/sofa.jpg'
                elif item.category_id == 'bedroom':
                    new_path = 'images/bed.jpg'
                elif item.category_id == 'kitchen':
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
        with app.app_context():
            try:
                # Создаем таблицы
                db.create_all()
                print("Таблицы созданы")

                # Создаем изображения по умолчанию
                create_default_images()
                print("Изображения по умолчанию созданы")

                # Создаем администратора
                if User.query.count() == 0:
                    create_admin()
                    print("Администратор создан")

                # Создаем категории
                if Category.query.count() == 0:
                    add_initial_categories()
                    print("Категории созданы")
                    # Делаем коммит, чтобы получить ID категорий
                    db.session.commit()

                # Добавляем мебель только после создания категорий
                if Furniture.query.count() == 0:
                    add_initial_furniture()
                    print("Начальные товары добавлены")

                print("Инициализация базы данных завершена успешно")
            except Exception as e:
                print(f"Ошибка при инициализации базы данных: {str(e)}")
                import traceback
                print(traceback.format_exc())
        _is_initialized = True

@app.route('/admin/categories')
@admin_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/category/add', methods=['POST'])
@admin_required
def admin_add_category():
    try:
        name = request.form['name']
        slug = request.form['slug']
        description = request.form['description']
        
        # Проверяем уникальность slug
        if Category.query.filter_by(slug=slug).first():
            flash('Категория с таким URL уже существует', 'danger')
            return redirect(url_for('admin_categories'))
        
        # Создаем категорию
        category = Category(name=name, slug=slug, description=description)
        db.session.add(category)
        
        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                try:
                    # Создаем директорию, если её нет
                    os.makedirs(os.path.join(app.static_folder, 'images'), exist_ok=True)
                    
                    # Сохраняем файл с именем slug категории
                    filename = f"{slug}.jpg"
                    file_path = os.path.join(app.static_folder, 'images', filename)
                    file.save(file_path)
                    
                    # Оптимизируем изображение
                    with Image.open(file_path) as img:
                        # Изменяем размер до 800x600, сохраняя пропорции
                        img.thumbnail((800, 600))
                        img.save(file_path, 'JPEG', quality=85)
                    
                except Exception as e:
                    flash(f'Ошибка при сохранении изображения: {str(e)}', 'danger')
                    db.session.rollback()
                    return redirect(url_for('admin_categories'))
        
        db.session.commit()
        flash('Категория успешно добавлена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении категории: {str(e)}', 'danger')
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/category/edit/<int:id>', methods=['POST'])
@admin_required
def admin_edit_category(id):
    category = Category.query.get_or_404(id)
    old_slug = category.slug
    
    # Проверяем уникальность slug
    new_slug = request.form['slug']
    if new_slug != category.slug and Category.query.filter_by(slug=new_slug).first():
        flash('Категория с таким URL уже существует', 'danger')
        return redirect(url_for('admin_categories'))
    
    category.name = request.form['name']
    category.slug = new_slug
    category.description = request.form['description']
    
    # Обработка загрузки нового изображения
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            try:
                # Создаем директорию, если её нет
                os.makedirs(os.path.join(app.static_folder, 'images'), exist_ok=True)
                
                # Если slug изменился, удаляем старое изображение
                if old_slug != new_slug:
                    old_image_path = os.path.join(app.static_folder, 'images', f"{old_slug}.jpg")
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # Сохраняем новое изображение
                filename = f"{new_slug}.jpg"
                file_path = os.path.join(app.static_folder, 'images', filename)
                file.save(file_path)
                
                # Оптимизируем изображение
                with Image.open(file_path) as img:
                    # Изменяем размер до 800x600, сохраняя пропорции
                    img.thumbnail((800, 600))
                    img.save(file_path, 'JPEG', quality=85)
                
            except Exception as e:
                flash(f'Ошибка при сохранении изображения: {str(e)}', 'danger')
    # Если slug изменился, но новое изображение не загружено, переименовываем старое
    elif old_slug != new_slug:
        old_image_path = os.path.join(app.static_folder, 'images', f"{old_slug}.jpg")
        new_image_path = os.path.join(app.static_folder, 'images', f"{new_slug}.jpg")
        if os.path.exists(old_image_path):
            try:
                os.rename(old_image_path, new_image_path)
            except Exception as e:
                flash(f'Ошибка при переименовании изображения: {str(e)}', 'danger')
    
    try:
        db.session.commit()
        flash('Категория успешно обновлена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении категории: {str(e)}', 'danger')
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/category/delete/<int:id>', methods=['POST'])
@admin_required
def admin_delete_category(id):
    category = Category.query.get_or_404(id)
    
    try:
        # Удаляем изображение категории
        image_path = os.path.join(app.static_folder, 'images', f"{category.slug}.jpg")
        if os.path.exists(image_path):
            os.remove(image_path)
        
        # Удаляем все товары в категории
        Furniture.query.filter_by(category_id=category.id).delete()
        # Удаляем саму категорию
        db.session.delete(category)
        db.session.commit()
        flash('Категория и все связанные товары успешно удалены', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении категории: {str(e)}', 'danger')
    
    return redirect(url_for('admin_categories'))

@app.route('/admin/change-admin', methods=['GET', 'POST'])
@admin_required
def change_admin():
    if request.method == 'POST':
        try:
            current_user = User.query.get(session['user_id'])
            current_password = request.form['current_password']
            new_username = request.form['username']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']

            # Проверяем текущий пароль
            if not current_user.check_password(current_password):
                flash('Неверный текущий пароль', 'danger')
                return redirect(url_for('change_admin'))

            # Проверяем уникальность нового имени пользователя
            if new_username != current_user.username:
                existing_user = User.query.filter_by(username=new_username).first()
                if existing_user:
                    flash('Пользователь с таким именем уже существует', 'danger')
                    return redirect(url_for('change_admin'))
                current_user.username = new_username

            # Если введен новый пароль, проверяем его и обновляем
            if new_password:
                if new_password != confirm_password:
                    flash('Новые пароли не совпадают', 'danger')
                    return redirect(url_for('change_admin'))
                current_user.set_password(new_password)

            db.session.commit()
            flash('Данные успешно обновлены', 'success')
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении данных: {str(e)}', 'danger')
            return redirect(url_for('change_admin'))

    return render_template('admin/change_admin.html', current_user=User.query.get(session['user_id']))

if __name__ == '__main__':
    # Локальная разработка
    with app.app_context():
        # Создаем таблицы
        db.create_all()
        print("Таблицы созданы")

        # Создаем изображения по умолчанию
        create_default_images()
        print("Изображения по умолчанию созданы")

        # Создаем администратора
        if User.query.count() == 0:
            create_admin()
            print("Администратор создан")

        # Создаем категории
        if Category.query.count() == 0:
            add_initial_categories()
            print("Категории созданы")
            # Делаем коммит, чтобы получить ID категорий
            db.session.commit()

        # Добавляем мебель только после создания категорий
        if Furniture.query.count() == 0:
            add_initial_furniture()
            print("Начальные товары добавлены")

        # Проверяем и исправляем пути к изображениям
        fix_image_paths()
        print("Пути к изображениям проверены и исправлены")
    
    # Определение порта для Railway или локального запуска
    port = int(os.environ.get('PORT', 5000))
    
    # Запуск приложения
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        # Production - режим для Railway
        app.run(host='0.0.0.0', port=port)
    else:
        # Режим разработки
        app.run(debug=True, port=port) 