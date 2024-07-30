from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.web_app_info import WebAppInfo
from aiogram.dispatcher.filters.builtin import CommandStart
import json
# Инициализация бота и диспетчера
bot = Bot('6653550966:AAGaqSR2kwaV9ZcsEUVtREysZn0Iz7fiD4M')
dp = Dispatcher(bot)

# Обработчик команды '/start'
@dp.message_handler(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup()
    markup.add(types.KeyboardButton('Contact technical support', web_app=WebAppInfo(url='https://hape30.github.io/Femida-last-release')))
    await message.answer('Hello, please describe your problem', reply_markup=markup)

@dp.message_handler(content_types=['web_app_data'])
async def web_app(message: types.Message):
    res = json.loads(message.web_app_data.data)
    await message.answer(f'Name: {res["name"]}. Email: {res["email"]}. Message: {res["message"]}')
# Запуск бота
executor.start_polling(dp)
