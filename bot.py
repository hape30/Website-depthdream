import os
import logging
from dotenv import load_dotenv
import telebot
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, BigInteger, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import numpy as np
from encode import TextEncoder
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = os.getenv("MY_KEY")
database_url_bot = os.getenv("DATABASE_URL")  # URL для базы данных сообщений бота
database_url_tarologist = os.getenv("DATABASE_URL_TAROLOGIST")  # URL для базы данных сообщений таролога
TAROLOGIST_CHAT_ID = int(os.getenv("TAROLOGIST_CHAT_ID"))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем объект бота
bot = telebot.TeleBot(my_token)

# Настройка базы данных для сообщений бота
BaseBot = declarative_base()
engine_bot = create_engine(database_url_bot, client_encoding='utf8')
SessionBot = sessionmaker(bind=engine_bot)
session_bot = SessionBot()

# Настройка базы данных для сообщений таролога
BaseTarologist = declarative_base()
engine_tarologist = create_engine(database_url_tarologist, client_encoding='utf8')
SessionTarologist = sessionmaker(bind=engine_tarologist)
session_tarologist = SessionTarologist()

# Определение таблицы для хранения сообщений бота
class EncodedMessage(BaseBot):
    __tablename__ = 'encoded_messages'
    id = Column(Integer, primary_key=True)
    original_text = Column(String, nullable=False)
    encoded_vector = Column(LargeBinary, nullable=False)

# Определение таблиц для хранения сообщений таролога и переписки
class User(BaseTarologist):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True)
    username = Column(String, nullable=True)
    conversations = relationship("Conversation", back_populates="user")

class Conversation(BaseTarologist):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")

class Message(BaseTarologist):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    sender_id = Column(BigInteger, nullable=False)
    message_text = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    conversation = relationship("Conversation", back_populates="messages")

# Создание таблиц в базе данных
BaseBot.metadata.create_all(engine_bot)
BaseTarologist.metadata.create_all(engine_tarologist)

# Создаем объект для кодирования текста
text_encoder = TextEncoder()

# Словарь для отслеживания активных сеансов общения
active_sessions = {}

# Функция для записи информации о сеансе общения в базу данных
def start_conversation(user_id, username=None):
    logger.info(f"Starting conversation with user_id: {user_id}, username: {username}")
    user = session_tarologist.get(User, user_id)
    if not user:
        user = User(id=user_id, username=username)
        session_tarologist.add(user)
    else:
        # Деактивируем все предыдущие сеансы общения для этого пользователя
        session_tarologist.query(Conversation).filter_by(user_id=user_id, active=True).update({Conversation.active: False})
    
    conversation = Conversation(user_id=user_id, active=True)
    session_tarologist.add(conversation)
    session_tarologist.commit()
    active_sessions[user_id] = True
    logger.info(f"Conversation started for user_id: {user_id}")

def is_conversation_active(user_id):
    logger.info(f"Checking if conversation is active for user_id: {user_id} - {active_sessions.get(user_id, False)}")
    return active_sessions.get(user_id, False)

def get_active_user_id_for_tarologist():
    conversation = session_tarologist.query(Conversation).filter_by(active=True).first()
    active_user_id = conversation.user_id if conversation else None
    logger.info(f"Getting active user id for tarologist: {active_user_id}")
    return active_user_id

def save_message(user_id, sender_id, message_text):
    conversation = session_tarologist.query(Conversation).filter_by(user_id=user_id, active=True).first()
    if conversation:
        message = Message(
            conversation_id=conversation.id,
            sender_id=sender_id,
            message_text=message_text
        )
        session_tarologist.add(message)
        session_tarologist.commit()
        logger.info(f"Saving message from sender_id: {sender_id} to user_id: {user_id} - {message_text}")
        logger.info("Message saved")

def save_bot_message(message_text):
    encoded_vector = text_encoder.encode(message_text)
    encoded_message = EncodedMessage(
        original_text=message_text,
        encoded_vector=np.array(encoded_vector).tobytes()
    )
    session_bot.add(encoded_message)
    session_bot.commit()
    logger.info(f"Bot message saved: {message_text}")

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    contact_tarologist_button = InlineKeyboardButton("Contact the tarologist", callback_data="contact_tarologist")
    markup.add(contact_tarologist_button)
    bot.reply_to(message, "Hi! I am a bot created to process your dreams using AI, and you can also contact the tarologist by clicking the button below.", reply_markup=markup)
    logger.info(f"Received /start command from user_id: {message.chat.id}")

# Обработчик команды для таролога
@bot.message_handler(commands=['select_user'])
def handle_select_user(message):
    if message.chat.id == TAROLOGIST_CHAT_ID:
        try:
            user_id = int(message.text.split()[1])
            start_conversation(user_id)
            bot.reply_to(message, f"Communication with the user {user_id} fixed.")
        except (IndexError, ValueError):
            bot.reply_to(message, "Using: /select_user <user_id>")
    else:
        bot.reply_to(message, "This command can only be used by a tarologist.")
    logger.info(f"Received /select_user command from user_id: {message.chat.id}")

# Обработчик нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "contact_tarologist":
        user_id = call.message.chat.id
        username = call.message.chat.username
        start_conversation(user_id, username)
        bot.answer_callback_query(call.id, "The connection with the tarologist has been established. Please send your message.")
        bot.send_message(TAROLOGIST_CHAT_ID, f"User {user_id} ({username}) wants to contact you.")
    logger.info(f"Received callback query from user_id: {call.message.chat.id} with data: {call.data}")

# Обработчик всех сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id

    if user_id == TAROLOGIST_CHAT_ID:
        target_user_id = get_active_user_id_for_tarologist()
        if target_user_id:
            bot.send_message(target_user_id, f"A message from the tarologist: {message.text}")
            save_message(target_user_id, TAROLOGIST_CHAT_ID, message.text)
        else:
            bot.reply_to(message, "There are no active users to communicate with.")
    else:
        if is_conversation_active(user_id):
            bot.send_message(TAROLOGIST_CHAT_ID, f"A message from the user {user_id}: {message.text}")
            save_message(user_id, user_id, message.text)
        else:
            bot.reply_to(message, "I got your message. It was saved.")
            save_bot_message(message.text)
    logger.info(f"Received message from user_id: {message.chat.id} - {message.text}")

# Основная функция для запуска бота
def main():
    logger.info("Starting bot polling")
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
