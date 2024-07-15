import os
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()
database_url = os.getenv("DATABASE_URL_TAROLOGIST")

# Подключаемся к базе данных
engine = create_engine(database_url)

# Запрос для извлечения данных из таблицы messages
query = """
SELECT
    sent_at AS time,
    COUNT(*) AS message_count
FROM
    messages
GROUP BY
    sent_at
ORDER BY
    sent_at;
"""

# Чтение данных из базы данных в DataFrame
df = pd.read_sql(query, engine)

# Построение графика
plt.figure(figsize=(10, 5))
plt.plot(df['time'], df['message_count'], marker='o')
plt.title('Message Count Over Time')
plt.xlabel('Time')
plt.ylabel('Message Count')
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
