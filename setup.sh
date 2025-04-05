#!/bin/bash

# Обновляем pip
python -m pip install --upgrade pip

# Устанавливаем зависимости
pip install -r requirements.txt

# Создаем необходимые директории
mkdir -p static/uploads

# Проверяем установку Flask-Mail
python -c "from flask_mail import Mail" 