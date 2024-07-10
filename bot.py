import os
import logging
from dotenv import load_dotenv
import telebot
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
import numpy as np
from encode import TextEncoder

# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = os.getenv("MY_KEY")
database_url = os.getenv("DATABASE_URL")

# Настройка логирования
logging.basicConfig(level=logging.INFO)  # Устанавливаем уровень логирования INFO

# Создаем объект бота
bot = telebot.TeleBot(my_token)

# Настройка базы данных
Base = declarative_base()
engine = create_engine(database_url, client_encoding='utf8')
Session = sessionmaker(bind=engine)
session = Session()

# Определение таблицы для хранения сообщений
class EncodedMessage(Base):
    __tablename__ = 'encoded_messages'
    id = Column(Integer, primary_key=True)
    original_text = Column(String, nullable=False)
    encoded_vector = Column(LargeBinary, nullable=False)

# Создание таблицы в базе данных
Base.metadata.create_all(engine)

# Создаем объект для кодирования текста
text_encoder = TextEncoder()

# Глобальная переменная для хранения последнего сообщения
last_message = ""

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    global last_message
    last_message = message.text  # Сохраняем текст сообщения в глобальную переменную
    bot.reply_to(message, "Привет! Я бот, созданный с помощью telebot. Отправь мне любое сообщение, и я сохраню его текст в переменной.")
    logging.info(f"Сохранено в last_message: {last_message}")  # Логируем сообщение

# Обработчик всех сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global last_message
    last_message = message.text  # Сохраняем текст сообщения в глобальную переменную
    bot.reply_to(message, "Я получил ваше сообщение. Оно было сохранено.")
    logging.info(f"Сохранено в last_message: {last_message}")  # Логируем сообщение

    # Кодируем сообщение и сохраняем в базу данных
    encoded_vector = text_encoder.encode(message.text)
    encoded_message = EncodedMessage(
        original_text=message.text,
        encoded_vector=np.array(encoded_vector).tobytes()
    )
    session.add(encoded_message)
    session.commit()
    logging.info("Сообщение закодировано и сохранено в базу данных")

# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
