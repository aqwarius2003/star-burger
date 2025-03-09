#!/bin/bash
set -e  # Прерывать выполнение при ошибках

# Функция для обработки ошибок
handle_error() {
    echo "Ошибка в скрипте на строке $1. Прерывание выполнения."
    exit 1
}

# Перехватываем ошибки и вызываем handle_error
trap 'handle_error $LINENO' ERR

# Переходим в директорию проекта
cd /opt/star-burger

# Обновляем код из репозитория
echo "Обновление кода из репозитория..."
git pull origin master

# Собираем фронтенд с помощью Parcel (продакшн-сборка)
echo "Сборка фронтенда..."
./node_modules/.bin/parcel build bundles-src/index.js --dist-dir bundles --public-url="./"

# Устанавливаем Node.js-зависимости
echo "Установка Node.js-зависимостей..."
npm ci --dev

# Активируем виртуальное окружение
echo "Активация виртуального окружения..."
source /opt/star-burger/venv/bin/activate

# Устанавливаем Python-зависимости
echo "Установка Python-зависимостей..."
pip install -r requirements.txt


# Собираем статические файлы Django
echo "Сборка статических файлов..."
python manage.py collectstatic --noinput

# Применяем миграции базы данных
echo "Применение миграций..."
python manage.py migrate --noinput

# Перезагружаем Nginx
echo "Перезагрузка Nginx..."
systemctl reload nginx

# Отправляем уведомление в Rollbar о успешном деплое
echo "Отправка уведомления в Rollbar..."
curl -H "X-Rollbar-Access-Token: $ROLLBAR_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -X POST 'https://api.rollbar.com/api/1/deploy' \
     -d '{
           "environment": "production",
           "revision": "'"$(git rev-parse HEAD)"'",
           "rollbar_name": "star_burger",
           "local_username": "00victorr",
           "status": "succeeded"
         }'

echo "Деплой завершен успешно!"

# Деактивируем виртуальное окружение
echo "Деактивация виртуального окружения..."
deactivate


