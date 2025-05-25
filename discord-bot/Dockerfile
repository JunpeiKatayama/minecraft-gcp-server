# Pythonの公式イメージをベースとして使用 (適宜バージョンを指定)
FROM python:3.10-slim

# 環境変数
ENV PYTHONUNBUFFERED=1
ENV APP_HOME /app
WORKDIR $APP_HOME

# 必要なライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# Flaskが使用するポート (Cloud Runが自動でリッスンする環境変数PORTではない点に注意)
# Cloud Runはコンテナがリッスンする任意のポートを検出しようとしますが、明示しておくと確実です。
# bot.py内でFlaskを8080で起動しているので、それに合わせます。
EXPOSE 8080

# アプリケーションを実行
CMD ["python", "bot.py"] 