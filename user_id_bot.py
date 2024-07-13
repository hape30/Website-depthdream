import os
import telebot
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()
my_token = '7050647320:AAFBO2kg-cyrysGLLXA49Zj0ZyiIPcsCiOk'

# Создаем объект бота
bot = telebot.TeleBot(my_token)

# Обработчик всех сообщений
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    bot.reply_to(message, f"Your user_id is: {message.chat.id}")

# Основная функция для запуска бота
def main():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    main()
