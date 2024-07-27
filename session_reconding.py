import os
import logging
from dotenv import load_dotenv
import telebot
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = os.getenv("MY_KEY")
database_url = os.getenv("DATABASE_URL")
TAROLOGIST_CHAT_ID = int(os.getenv("TAROLOGIST_CHAT_ID"))

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем объект бота
bot = telebot.TeleBot(my_token)

# Настройка базы данных
Base = declarative_base()
engine = create_engine(database_url, client_encoding='utf8')
Session = sessionmaker(bind=engine)
session = Session()

# Определение таблицы для хранения записей на сеанс
class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String, nullable=True)
    booking_time = Column(DateTime, nullable=False)

Base.metadata.create_all(engine)

# Функция для отправки оповещения тарологу
def notify_tarologist(user_id, username, booking_time):
    message = f"New booking from user {username} (ID: {user_id}) for {booking_time}."
    bot.send_message(TAROLOGIST_CHAT_ID, message)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    book_session_button = InlineKeyboardButton("Book a session", callback_data="book_session")
    markup.add(book_session_button)
    bot.reply_to(message, "Hi! Click the button below to book a session with the tarologist.", reply_markup=markup)
    logger.info(f"Received /start command from user_id: {message.chat.id}")

# Обработчик нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith("book_session"))
def handle_callback_query(call):
    if call.data == "book_session":
        user_id = call.message.chat.id
        username = call.message.chat.username

        # Создаем кнопки для выбора даты и времени
        markup = InlineKeyboardMarkup()
        for i in range(5):
            booking_time = datetime.now() + timedelta(days=i)
            button_text = booking_time.strftime("%Y-%m-%d %H:%M")
            callback_data = f"confirm_booking_{booking_time.timestamp()}"
            markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))
        bot.send_message(user_id, "Choose a date and time for your session:", reply_markup=markup)

    elif call.data.startswith("confirm_booking_"):
        timestamp = float(call.data.split("_")[2])
        booking_time = datetime.fromtimestamp(timestamp)
        user_id = call.message.chat.id
        username = call.message.chat.username

        # Сохраняем запись в базе данных
        booking = Booking(user_id=user_id, username=username, booking_time=booking_time)
        session.add(booking)
        session.commit()

        # Оповещаем таролога о новой записи
        notify_tarologist(user_id, username, booking_time)

        bot.answer_callback_query(call.id, "Your booking is confirmed!")
        bot.send_message(user_id, f"Your session is booked for {booking_time}.")

# Основная функция для запуска бота
def main():
    logger.info("Starting bot polling")
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
