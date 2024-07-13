import os
import logging
from dotenv import load_dotenv
import telebot
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, BigInteger, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import numpy as np
from encode import TextEncoder
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = os.getenv("MY_KEY")
database_url = os.getenv("DATABASE_URL")
TAROLOGIST_CHAT_ID = int(os.getenv("TAROLOGIST_CHAT_ID"))

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

# Определение таблицы для хранения активных сеансов общения
class ActiveConversation(Base):
    __tablename__ = 'active_conversations'
    user_id = Column(BigInteger, primary_key=True)
    active = Column(Boolean, nullable=False, default=True)

# Создание таблиц в базе данных
Base.metadata.create_all(engine)

# Создаем объект для кодирования текста
text_encoder = TextEncoder()

# Функция для записи информации о сеансе общения в базу данных
def start_conversation(user_id):
    conversation = ActiveConversation(user_id=user_id, active=True)
    session.merge(conversation)
    session.commit()

# Функция для завершения сеанса общения
def end_conversation(user_id):
    conversation = session.query(ActiveConversation).filter_by(user_id=user_id, active=True).first()
    if conversation:
        conversation.active = False
        session.commit()

# Функция для проверки активного сеанса общения
def is_conversation_active(user_id):
    conversation = session.query(ActiveConversation).filter_by(user_id=user_id, active=True).first()
    return conversation is not None

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    contact_tarologist_button = InlineKeyboardButton("Связаться с тарологом", callback_data="contact_tarologist")
    markup.add(contact_tarologist_button)
    bot.reply_to(message, "Привет! Я бот, созданный с помощью telebot. Вы можете связаться с тарологом, нажав кнопку ниже.", reply_markup=markup)

# Обработчик команды для таролога
@bot.message_handler(commands=['select_user'])
def handle_select_user(message):
    if message.chat.id == TAROLOGIST_CHAT_ID:
        try:
            user_id = int(message.text.split()[1])
            start_conversation(user_id)
            bot.reply_to(message, f"Связь с пользователем {user_id} установлена.")
        except (IndexError, ValueError):
            bot.reply_to(message, "Использование: /select_user <user_id>")
    else:
        bot.reply_to(message, "Эту команду может использовать только таролог.")

# Обработчик нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "contact_tarologist":
        bot.answer_callback_query(call.id, "Связь с тарологом установлена. Пожалуйста, отправьте ваше сообщение.")
        start_conversation(call.message.chat.id)

# Обработчик всех сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id

    # Проверяем, находится ли пользователь в сеансе общения с тарологом
    if is_conversation_active(user_id):
        bot.send_message(TAROLOGIST_CHAT_ID, f"Сообщение от пользователя {user_id}: {message.text}")
    elif message.chat.id == TAROLOGIST_CHAT_ID:
        # Получаем идентификатор пользователя, с которым общается таролог
        target_user_id = get_active_user_id_for_tarologist()
        if target_user_id:
            bot.send_message(target_user_id, f"Сообщение от таролога: {message.text}")
        else:
            bot.reply_to(message, "Нет активных пользователей для общения.")
    else:
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

def get_active_user_id_for_tarologist():
    conversation = session.query(ActiveConversation).filter_by(active=True).first()
    return conversation.user_id if conversation else None

# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
