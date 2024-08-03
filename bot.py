import os
import logging
import os.path
from dotenv import load_dotenv
import telebot
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, BigInteger, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import numpy as np
from encode import TextEncoder
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import datetime
# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = os.getenv("MY_KEY")
database_url_bot = os.getenv("DATABASE_URL")  # URL для базы данных сообщений бота
database_url_tarologist = os.getenv("DATABASE_URL_TAROLOGIST")  # URL для базы данных сообщений таролога
TAROLOGIST_CHAT_ID = int(os.getenv("TAROLOGIST_CHAT_ID"))
CONNECT_GOOGLE_API_KEY = os.getenv("CONNECT_GOOGLE")
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

class Session(BaseTarologist):
    __tablename__ = 'sessions'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    confirmed = Column(Boolean, default=False)
    user = relationship("User")

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
    logger.info(f"Active sessions: {active_sessions}")

def end_conversation(user_id):
    logger.info(f"Ending conversation with user_id: {user_id}")
    conversation = session_tarologist.query(Conversation).filter_by(user_id=user_id, active=True).first()
    if conversation:
        conversation.active = False
        session_tarologist.commit()
        active_sessions.pop(user_id, None)
        logger.info(f"Conversation ended for user_id: {user_id}")
        logger.info(f"Active sessions: {active_sessions}")
    else:
        logger.warning(f"No active conversation found for user_id: {user_id}")

def is_conversation_active(user_id):
    active = active_sessions.get(user_id, False)
    logger.info(f"Checking if conversation is active for user_id: {user_id} - {active}")
    return active

def get_active_user_id_for_tarologist():
    conversation = session_tarologist.query(Conversation).filter_by(active=True).order_by(Conversation.id.desc()).first()
    active_user_id = conversation.user_id if conversation else None
    if active_user_id == TAROLOGIST_CHAT_ID:
        active_user_id = None
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
    else:
        logger.warning(f"No active conversation found for user_id: {user_id}")

def save_bot_message(message_text):
    encoded_vector = text_encoder.encode(message_text)
    encoded_message = EncodedMessage(
        original_text=message_text,
        encoded_vector=np.array(encoded_vector).tobytes()
    )
    session_bot.add(encoded_message)
    session_bot.commit()
    logger.info(f"Bot message saved: {message_text}")

# Функция для записи на сеанс
def schedule_session(user_id, scheduled_time):
    user = session_tarologist.get(User, user_id)
    if not user:
        user = User(id=user_id)
        session_tarologist.add(user)
        session_tarologist.commit()

    session = Session(user_id=user_id, scheduled_time=scheduled_time)
    session_tarologist.add(session)
    session_tarologist.commit()
    logger.info(f"Session scheduled for user_id: {user_id} at {scheduled_time}")

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    contact_tarologist_button = InlineKeyboardButton("Contact the tarologist", callback_data="contact_tarologist")
    schedule_session_button = InlineKeyboardButton("Schedule a session", callback_data="schedule_session")
    markup.add(contact_tarologist_button, schedule_session_button)
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

# Обработчик команды для завершения сеанса
@bot.message_handler(commands=['end_conversation'])
def handle_end_conversation(message):
    if message.chat.id == TAROLOGIST_CHAT_ID:
        active_user_id = get_active_user_id_for_tarologist()
        if active_user_id:
            end_conversation(active_user_id)
            bot.reply_to(message, f"Conversation with user {active_user_id} ended.")
        else:
            bot.reply_to(message, "There are no active users to end the conversation with.")
    else:
        bot.reply_to(message, "This command can only be used by a tarologist.")
    logger.info(f"Received /end_conversation command from user_id: {message.chat.id}")

# Обработчик нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "contact_tarologist":
        user_id = call.message.chat.id
        username = call.message.chat.username
        start_conversation(user_id, username)
        bot.answer_callback_query(call.id, "The connection with the tarologist has been established. Please send your message.")
        bot.send_message(TAROLOGIST_CHAT_ID, f"User {user_id} ({username}) wants to contact you.")
    elif call.data == "schedule_session":
        bot.answer_callback_query(call.id, "Please send the date and time for the session (YYYY-MM-DD HH:MM).")
        bot.register_next_step_handler(call.message, process_session_schedule)
    logger.info(f"Received callback query from user_id: {call.message.chat.id} with data: {call.data}")

def process_session_schedule(message):
    try:
        scheduled_time = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        schedule_session(message.chat.id, scheduled_time)
        bot.reply_to(message, f"Session scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}.")
        # Отправить уведомление тарологу
        bot.send_message(TAROLOGIST_CHAT_ID, f"New session scheduled by user {message.chat.id} at {scheduled_time}.")
    except ValueError:
        bot.reply_to(message, "Invalid date format. Please use YYYY-MM-DD HH:MM.")

# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text_message(message):
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

# Обработчик фото
@bot.message_handler(content_types=['photo'])
def handle_photo_message(message):
    user_id = message.chat.id
    file_id = message.photo[-1].file_id

    if user_id == TAROLOGIST_CHAT_ID:
        target_user_id = get_active_user_id_for_tarologist()
        if target_user_id:
            bot.send_photo(target_user_id, file_id, caption="A photo from the tarologist")
            save_message(target_user_id, TAROLOGIST_CHAT_ID, f"Photo: {file_id}")
        else:
            bot.reply_to(message, "There are no active users to communicate with.")
    else:
        if is_conversation_active(user_id):
            bot.send_photo(TAROLOGIST_CHAT_ID, file_id, caption=f"A photo from the user {user_id}")
            save_message(user_id, user_id, f"Photo: {file_id}")
        else:
            bot.reply_to(message, "I got your photo. It was saved.")
            save_bot_message(f"Photo: {file_id}")
    logger.info(f"Received photo from user_id: {message.chat.id} - file_id: {file_id}")

# Обработчик видео
@bot.message_handler(content_types=['video'])
def handle_video_message(message):
    user_id = message.chat.id
    file_id = message.video.file_id

    if user_id == TAROLOGIST_CHAT_ID:
        target_user_id = get_active_user_id_for_tarologist()
        if target_user_id:
            bot.send_video(target_user_id, file_id, caption="A video from the tarologist")
            save_message(target_user_id, TAROLOGIST_CHAT_ID, f"Video: {file_id}")
        else:
            bot.reply_to(message, "There are no active users to communicate with.")
    else:
        if is_conversation_active(user_id):
            bot.send_video(TAROLOGIST_CHAT_ID, file_id, caption=f"A video from the user {user_id}")
            save_message(user_id, user_id, f"Video: {file_id}")
        else:
            bot.reply_to(message, "I got your video. It was saved.")
            save_bot_message(f"Video: {file_id}")
    logger.info(f"Received video from user_id: {message.chat.id} - file_id: {file_id}")

# Функция отправки напоминания о предстоящем сеансе
def send_session_reminder():
    now = datetime.utcnow()
    reminder_time = now + timedelta(minutes=30)  # Отправлять напоминание за 30 минут до сеанса
    sessions = session_tarologist.query(Session).filter(Session.scheduled_time.between(now, reminder_time), Session.confirmed == False).all()
    for session in sessions:
        bot.send_message(session.user_id, f"Reminder: Your session is scheduled at {session.scheduled_time.strftime('%Y-%m-%d %H:%M')} (UTC). Please confirm your attendance.")
        session.confirmed = True
        session_tarologist.commit()

# Основная функция для запуска бота
def main():
    logger.info("Starting bot polling")
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
