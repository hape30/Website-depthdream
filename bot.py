import os
import logging
from dotenv import load_dotenv
import telebot

# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = os.getenv("MY_KEY")

# Настройка логирования
logging.basicConfig(level=logging.INFO)  # Устанавливаем уровень логирования INFO

# Создаем объект бота
bot = telebot.TeleBot(my_token)

# Глобальная переменная для хранения последнего сообщения
last_message = ""

# Файл для записи сообщений
messages_file = "messages.txt"

# Функция для записи сообщений в файл
def write_to_file(message):
    with open(messages_file, "a", encoding="utf-8") as file:
        file.write(message + "\n")

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
    write_to_file(message.text)  # Записываем сообщение в файл

# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
