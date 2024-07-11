import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker

# Загружаем переменные окружения из .env файла
load_dotenv()
database_url = os.getenv("DATABASE_URL")

# Настройка базы данных
Base = declarative_base()
engine = create_engine(database_url)
Session = sessionmaker(bind=engine)
session = Session()

# Определение таблицы для хранения сообщений
class EncodedMessage(Base):
    __tablename__ = 'encoded_messages'
    id = Column(Integer, primary_key=True)
    original_text = Column(String, nullable=False)
    encoded_vector = Column(LargeBinary, nullable=False)

# Получение данных из базы данных
messages = session.query(EncodedMessage).all()

# Вывод данных на экран
for message in messages:
    print(f"ID: {message.id}, Original Text: {message.original_text}, Encoded Vector: {message.encoded_vector}")
