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

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Функция для авторизации Google Calendar API
def get_google_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    return service

# Функция для создания события в Google Calendar
def create_google_calendar_event(user_id, scheduled_time):
    service = get_google_calendar_service()

    event = {
        'summary': 'Tarologist Session',
        'description': f'Session with user {user_id}.',
        'start': {
            'dateTime': scheduled_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (scheduled_time + timedelta(hours=1)).isoformat(),
            'timeZone': 'UTC',
        },
        'attendees': [
            {'email': 'tarologist_email@gmail.com'},  # Email таролога
            {'email': 'user_email@gmail.com'},  # Email пользователя (замените на реальный email пользователя)
        ],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 30},
                {'method': 'popup', 'minutes': 30},
            ],
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    logger.info(f"Event created: {event.get('htmlLink')}")

# Функция для записи информации о сеансе общения в базу данных
def start_conversation(user_id, username=None):
    logger.info(f"Начало разговора с помощью user_id: {user_id}, username: {username}")
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
    logger.info(f"Разговор начался сr user_id: {user_id}")
    logger.info(f"Активные сеансы: {active_sessions}")

def end_conversation(user_id):
    logger.info(f"Завершение разговора с помощью user_id: {user_id}")
    conversation = session_tarologist.query(Conversation).filter_by(user_id=user_id, active=True).first()
    if conversation:
        conversation.active = False
        session_tarologist.commit()
        active_sessions.pop(user_id, None)
        logger.info(f"Диалог завершен для user_id: {user_id}")
        logger.info(f"Активные сеансы: {active_sessions}")
    else:
        logger.warning(f"Не найдено активного диалога для user_id: {user_id}")

def is_conversation_active(user_id):
    active = active_sessions.get(user_id, False)
    logger.info(f"Проверка, активен ли диалог для user_id: {user_id} - {active}")
    return active

def get_active_user_id_for_tarologist():
    conversation = session_tarologist.query(Conversation).filter_by(active=True).order_by(Conversation.id.desc()).first()
    active_user_id = conversation.user_id if conversation else None
    if active_user_id == TAROLOGIST_CHAT_ID:
        active_user_id = None
    logger.info(f"Получение активного идентификатора пользователя для таролога:{active_user_id}")
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
        logger.info(f"Сохранение сообщения из идентификатора отправителя: {sender_id} to user_id: {user_id} - {message_text}")
        logger.info("Message saved")
    else:
        logger.warning(f"Не найдено активного диалога для user_id: {user_id}")

def save_bot_message(message_text):
    encoded_vector = text_encoder.encode(message_text)
    encoded_message = EncodedMessage(
        original_text=message_text,
        encoded_vector=np.array(encoded_vector).tobytes()
    )
    session_bot.add(encoded_message)
    session_bot.commit()
    logger.info(f"Сообщение бота сохранено: {message_text}")

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
    logger.info(f"Сеанс, запланированный для user_id: {user_id} at {scheduled_time}")
    
    # Создаем событие в Google Calendar
    create_google_calendar_event(user_id, scheduled_time)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    contact_tarologist_button = InlineKeyboardButton("Обратитесь к тарологу", callback_data="contact_tarologist")
    schedule_session_button = InlineKeyboardButton("Schedule a session", callback_data="schedule_session")
    markup.add(contact_tarologist_button, schedule_session_button)
    bot.reply_to(message, "Привет! Я - бот, созданный для обработки ваших снов с помощью искусственного интеллекта, и вы также можете связаться с тарологом, нажав на кнопку ниже.", reply_markup=markup)
    logger.info(f"Received /start command from user_id: {message.chat.id}")

# Обработчик обратных вызовов от Inline кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    if call.data == "contact_tarologist":
        start_conversation(user_id, call.message.chat.username)
        bot.send_message(user_id, "Пожалуйста, напишите свое сообщение тарологу.")
    elif call.data == "schedule_session":
        schedule_session(user_id, datetime.utcnow() + timedelta(days=1))  # Пример записи на сеанс через 1 день

# Обработчик текстовых сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.chat.id
    if is_conversation_active(user_id):
        save_message(user_id, user_id, message.text)
        save_bot_message("Ваше сообщение отправлено тарологу.")
        bot.send_message(TAROLOGIST_CHAT_ID, f"User {message.chat.username}: {message.text}")
    elif user_id == TAROLOGIST_CHAT_ID:
        active_user_id = get_active_user_id_for_tarologist()
        if active_user_id:
            save_message(active_user_id, user_id, message.text)
            bot.send_message(active_user_id, f"Tarologist: {message.text}")
        else:
            bot.send_message(user_id, "Активных разговоров нет")
    else:
        bot.send_message(user_id, "Пожалуйста, нажмите на 'Связаться с тарологом', чтобы начать разговор.")

# Основная функция для запуска бота
def main():
    logger.info("Starting bot polling")
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
