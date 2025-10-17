# ベースイメージは任意（ここでは slim を推奨）
FROM python:3.11-slim

# 非対話的: minimal deps
ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# 必要なら OS レベルの依存をインストール（例: build-essential が必要なら追加）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# 依存ファイルをコピーしてインストール
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# アプリコードをコピー
COPY . /app

# ポート
EXPOSE 5000

# 本番向け Gunicorn コマンド（ワーカ数は適宜調整）
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "schedule_app.wsgi:app", "-w", "4", "--threads", "2"]