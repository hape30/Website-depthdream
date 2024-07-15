import os
from dotenv import load_dotenv

load_dotenv()

# Печать всех переменных окружения для отладки
for key, value in os.environ.items():
    print(f"{key}: {value}")

# Загружаем необходимые переменные
my_token = os.getenv("MY_KEY")
database_url_bot = os.getenv("DATABASE_URL_BOT")
database_url_tarologist = os.getenv("DATABASE_URL_TAROLOGIST")
TAROLOGIST_CHAT_ID = os.getenv("TAROLOGIST_CHAT_ID")

# Проверка на None
if not my_token:
    raise ValueError("MY_KEY is not set in the environment variables")
if not database_url_bot:
    raise ValueError("DATABASE_URL_BOT is not set in the environment variables")
if not database_url_tarologist:
    raise ValueError("DATABASE_URL_TAROLOGIST is not set in the environment variables")
if not TAROLOGIST_CHAT_ID:
    raise ValueError("TAROLOGIST_CHAT_ID is not set in the environment variables")

TAROLOGIST_CHAT_ID = int(TAROLOGIST_CHAT_ID)
