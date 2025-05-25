# discord-bot/config.sample.py
# このファイルは、Discord Botをローカル環境で動作させる際に必要な設定のテンプレートです。
# 実際にローカルでBotを動かす場合は、このファイルを `config.py` という名前でコピーし、
# 各設定値をご自身のものに書き換えてください。
# Cloud Run での実行時、このファイルは読み込まれず、terraform.tfvars で設定した値が使用されます。

# Discord Bot Token
DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE" # 自身のDiscord Botのトークンに置き換えてください

# GCP Configuration
GCP_PROJECT_ID = "YOUR_GCP_PROJECT_ID_HERE"  # GCPプロジェクトID (例: "minecfaft-gcp-server")
GCP_ZONE = "asia-northeast1-b"  # GCEインスタンスのゾーン
GCP_INSTANCE_NAME = "minecraft-server" # GCEインスタンス名

# Discord Channel ID for notifications and commands
# 開発者モードを有効にして、チャンネルを右クリック -> IDをコピー で取得できます
DISCORD_CHANNEL_ID = 0 # 通知やコマンドを受け付けるチャンネルのID (整数)

# GCPサービスアカウントキーのパスについて:
# このBotは、まず環境変数 `DISCORD_BOT_GCP_CREDENTIALS` を参照します。
# 次に環境変数 `GOOGLE_APPLICATION_CREDENTIALS` を参照します。
# これらの環境変数にサービスアカウントキー(JSON)のフルパスを設定することを推奨します。
# (例: export DISCORD_BOT_GCP_CREDENTIALS="/path/to/your/discord-bot-gcp-key.json") 