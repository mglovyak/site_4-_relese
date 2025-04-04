# Магазин мебели

Веб-приложение для продажи мебели, разработанное с использованием Python и Flask.

## Функциональность

- Просмотр каталога мебели по категориям
- Детальная информация о товарах
- Административная панель для управления товарами
- Адаптивный дизайн
- Загрузка изображений товаров

## Требования

- Python 3.8+
- Flask
- Flask-SQLAlchemy
- Pillow
- Flask-Login
- Flask-WTF
- email-validator
- python-dotenv

## Установка

1. Клонируйте репозиторий:
```bash
git clone <url-репозитория>
cd furniture-store
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
# Для Windows:
venv\Scripts\activate
# Для Linux/Mac:
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте необходимые директории:
```bash
mkdir static/uploads
mkdir static/images
```

5. Запустите приложение:
```bash
python app.py
```

## Структура проекта

```
furniture-store/
├── app.py
├── requirements.txt
├── static/
│   ├── css/
│   │   └── style.css
│   ├── images/
│   └── uploads/
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── category.html
│   ├── product.html
│   └── admin.html
└── README.md
```

## Использование

1. Откройте браузер и перейдите по адресу `http://localhost:5000`
2. Для доступа к админ-панели перейдите по адресу `http://localhost:5000/admin`

## Разработка

- Для добавления новых категорий мебели отредактируйте список категорий в `templates/admin.html`
- Изображения товаров сохраняются в директории `static/uploads`
- Стили можно настроить в файле `static/css/style.css`

## Лицензия

MIT 