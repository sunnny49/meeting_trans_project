FROM python:3.11-slim

# 安裝系統套件（gcc 用於某些 wheel，odbc 驅動）
RUN apt-get update \
 && apt-get install -y gcc curl gnupg unixodbc-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 環境變數
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    TZ=Asia/Taipei

# Gunicorn 啟動
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
