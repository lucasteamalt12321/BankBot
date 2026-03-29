FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# По умолчанию запускает BankBot; переопределяется в docker-compose через CMD
CMD ["python", "run_bot.py", "bank"]
