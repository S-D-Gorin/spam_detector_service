FROM python:3.11-slim

LABEL org.opencontainers.image.version="0.2.0"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# зависимости
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && \
    apt-get update && apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# код приложения
COPY src ./src

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
