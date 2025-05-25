# Minecraft Server Management Discord Bot

この Bot は、GCP 上に構築された Minecraft サーバーの状態を Discord から管理するためのものです。

## 機能

- Minecraft サーバーの起動
- Minecraft サーバーの停止通知と手動起動トリガー
- Minecraft サーバーの状態確認

## 必要なもの

- Discord Bot Token
- GCP プロジェクト ID
- GCP サービスアカウントキー (JSON 形式)
- Python 3.x
- Discord.py ライブラリ
- Google Cloud Client Libraries for Python

## セットアップ手順

1.  **Discord Bot の作成とトークンの取得:**

    - Discord Developer Portal ([https://discord.com/developers/applications](https://discord.com/developers/applications)) にアクセスします。
    - 新しいアプリケーションを作成します。
    - 作成したアプリケーションの「Bot」タブから「Add Bot」をクリックし、Bot ユーザーを作成します。
    - Bot のトークンをコピーして控えておきます。このトークンは後で設定ファイルに使用します。
    - Bot に必要な権限（メッセージの送信、メッセージ履歴の閲覧など）を設定します。
    - Bot を自分の Discord サーバーに招待します。「OAuth2」タブの「URL Generator」で `bot` と `applications.commands` スコープを選択し、必要な権限を選んで生成された URL にアクセスします。

2.  **GCP サービスアカウントキーの準備:**

    - GCP コンソールで、この Bot が使用するサービスアカウントを作成または選択します。
    - 必要なロール（例: Compute Instance Admin (v1), Cloud Functions Invoker など）をサービスアカウントに付与します。
    - サービスアカウントの JSON キーをダウンロードし、安全な場所に配置します (例: `discord-bot/gcp-key.json` やユーザーのホームディレクトリなど)。
    - **重要:** このキーファイルのパスを環境変数 `DISCORD_BOT_GCP_CREDENTIALS` に設定します。
      例 (Git Bash):
      ```bash
      export DISCORD_BOT_GCP_CREDENTIALS="/path/to/your/discord-bot-gcp-key.json"
      ```
      恒久的に設定する場合は、`~/.bashrc` や `~/.bash_profile` に上記の行を追記してください。
    - Bot は、まず `DISCORD_BOT_GCP_CREDENTIALS` を参照し、次に `GOOGLE_APPLICATION_CREDENTIALS` (Terraform 用などと共用の場合) を参照します。
    - `.gitignore` に実際のキーファイル名を追加し、リポジトリにコミットされないように注意してください (例: `gcp-key.json` を gitignore に追加)。

3.  **設定ファイルの作成:**

    - `discord-bot` ディレクトリにある `config.sample.py` をコピーして `config.py` という名前のファイルを作成します。
    - `config.py` を開き、以下の情報を実際の値に編集します。
      ```python
      # config.py の例 (編集後)
      DISCORD_BOT_TOKEN = "YOUR_DISCORD_BOT_TOKEN"
      GCP_PROJECT_ID = "YOUR_GCP_PROJECT_ID"
      GCP_ZONE = "asia-northeast1-b"  # Minecraftサーバーのゾーンに合わせて変更
      GCP_INSTANCE_NAME = "minecraft-server" # Minecraftサーバーのインスタンス名
      # GOOGLE_APPLICATION_CREDENTIALS = "path/to/your/gcp-key.json" # 環境変数で設定する場合は不要
      DISCORD_CHANNEL_ID = YOUR_DISCORD_CHANNEL_ID # 通知や操作を受け付けるチャンネルID (整数)
      ```

4.  **必要な Python ライブラリのインストール:**

    ```bash
    pip install discord.py google-api-python-client google-auth
    ```

    (もしくは `requirements.txt` を作成して `pip install -r requirements.txt`)

5.  **Bot の実行:**
    ```bash
    python bot.py
    ```

## 使い方 (予定)

- `/mc_start`: Minecraft サーバーを起動します。
- `/mc_status`: Minecraft サーバーの状態を確認します。
- VM 停止時には、指定されたチャンネルに自動で通知が送られ、「サーバー起動」ボタンが表示されます。

## 注意事項

- Bot トークンや GCP の認証情報は厳重に管理してください。
- Bot を実行する環境から GCP への API アクセス（特に Compute Engine API）が可能である必要があります。
