import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import os
import google.auth
from googleapiclient import discovery
import asyncio
from flask import Flask, request, abort
import threading
import datetime

# 設定ファイルの読み込み
try:
    import config
except ImportError:
    print("エラー: config.py が見つかりません。discord-bot/config.sample.py をコピーして config.py を作成し、必要な情報を設定してください。")
    exit()

# --- Flask App Setup ---
flask_app = Flask(__name__)

# --- グローバル変数・初期設定 ---
GCP_PROJECT_ID = config.GCP_PROJECT_ID
GCP_ZONE = config.GCP_ZONE
GCP_INSTANCE_NAME = config.GCP_INSTANCE_NAME
DISCORD_BOT_TOKEN = config.DISCORD_BOT_TOKEN
DISCORD_CHANNEL_ID = config.DISCORD_CHANNEL_ID

# GCP認証情報の設定
# 1. DISCORD_BOT_GCP_CREDENTIALS 環境変数を優先 (ローカル開発用)
# 2. 次に GOOGLE_APPLICATION_CREDENTIALS 環境変数 (ローカル開発用、または他のツールと共用)
# 3. 上記いずれもなければ、アプリケーションデフォルト認証情報 (ADC) を使用 (Cloud Run/FunctionsなどのGCP環境で推奨)

gcp_credentials_source = "アプリケーションデフォルト認証情報 (ADC)"
if os.getenv('DISCORD_BOT_GCP_CREDENTIALS'):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.environ['DISCORD_BOT_GCP_CREDENTIALS']
    gcp_credentials_source = f"DISCORD_BOT_GCP_CREDENTIALS 環境変数 ({os.environ['DISCORD_BOT_GCP_CREDENTIALS']})"
elif os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    gcp_credentials_source = f"GOOGLE_APPLICATION_CREDENTIALS 環境変数 ({os.environ['GOOGLE_APPLICATION_CREDENTIALS']})"

print(f"GCP認証: {gcp_credentials_source} を使用します。")

intents = discord.Intents.default()
intents.message_content = True # メッセージ内容の取得を有効にする場合 (スラッシュコマンドメインなら不要なことも)

bot = commands.Bot(command_prefix="!mc ", intents=intents) # スラッシュコマンドの場合は prefix はあまり意味をなさない

# GCP Compute Engine APIサービスクライアントを初期化
credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/compute'])
compute_service = discovery.build('compute', 'v1', credentials=credentials)

# --- Discord UI (Buttons) ---
class ServerControlView(View):
    def __init__(self, *, timeout=180): # タイムアウトを適宜設定 (デフォルトは180秒)
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Minecraftサーバーを起動", style=discord.ButtonStyle.success, custom_id="start_minecraft_server_button")
    async def start_server_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer() # 応答に時間がかかる可能性があるため
        current_status = await get_instance_status()
        if current_status == "RUNNING":
            await interaction.followup.send("サーバーは既に起動しています。", ephemeral=True)
        elif current_status == "TERMINATED":
            await interaction.followup.send("サーバーを起動中です...完了まで数分かかることがあります。", ephemeral=True)
            success = await start_instance()
            if success:
                # 起動完了 & IP通知ロジック (後で実装)
                await asyncio.sleep(15) # 仮の待機時間
                ip_address = await get_instance_external_ip()
                if ip_address:
                    message = f"サーバーが起動しました！ IPアドレス:\n```{ip_address}```"
                else:
                    message = "サーバーの起動処理は開始されましたが、IPアドレスの取得に失敗しました。少し待ってから `/mc_status` で確認してください。"
                # ボタンを無効化するか、メッセージを更新する
                self.disable_all_items()
                await interaction.edit_original_response(content=message, view=self) # 元のメッセージを編集
            else:
                await interaction.followup.send("サーバーの起動に失敗しました。エラーログを確認してください。", ephemeral=True)
        else:
            await interaction.followup.send(f"サーバーは現在 `{current_status}` 状態です。起動できません。", ephemeral=True)

    # ボタンが押された後に無効化するヘルパー
    def disable_all_items(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

# --- ヘルパー関数 (GCP操作) ---
async def get_instance_status():
    """GCEインスタンスの現在のステータスを取得する"""
    try:
        request = compute_service.instances().get(project=GCP_PROJECT_ID, zone=GCP_ZONE, instance=GCP_INSTANCE_NAME)
        response = request.execute()
        return response.get('status') # 例: RUNNING, TERMINATED
    except Exception as e:
        print(f"インスタンスの状態取得中にエラー: {e}")
        return None

async def start_instance():
    """GCEインスタンスを起動する"""
    try:
        request = compute_service.instances().start(project=GCP_PROJECT_ID, zone=GCP_ZONE, instance=GCP_INSTANCE_NAME)
        response = request.execute()
        print(f"インスタンス起動APIレスポンス: {response}")
        # 起動完了まで待機するロジックをここに追加することも可能 (ポーリングなど)
        return True
    except Exception as e:
        print(f"インスタンス起動中にエラー: {e}")
        return False

async def stop_instance(): # 今回は自動停止がメインだが、手動停止用として
    """GCEインスタンスを停止する"""
    try:
        request = compute_service.instances().stop(project=GCP_PROJECT_ID, zone=GCP_ZONE, instance=GCP_INSTANCE_NAME)
        response = request.execute()
        print(f"インスタンス停止APIレスポンス: {response}")
        return True
    except Exception as e:
        print(f"インスタンス停止中にエラー: {e}")
        return False

async def get_instance_external_ip():
    """GCEインスタンスの外部IPアドレスを取得する"""
    try:
        request = compute_service.instances().get(project=GCP_PROJECT_ID, zone=GCP_ZONE, instance=GCP_INSTANCE_NAME)
        response = request.execute()
        interfaces = response.get('networkInterfaces', [])
        if interfaces:
            access_configs = interfaces[0].get('accessConfigs', [])
            if access_configs:
                return access_configs[0].get('natIP')
        return None
    except Exception as e:
        print(f"外部IPアドレスの取得中にエラー: {e}")
        return None

async def get_boot_disk_name():
    """GCEインスタンスのブートディスク名を取得する"""
    try:
        instance_details = compute_service.instances().get(project=GCP_PROJECT_ID, zone=GCP_ZONE, instance=GCP_INSTANCE_NAME).execute()
        disks = instance_details.get('disks', [])
        if disks:
            boot_disk_info = next((disk for disk in disks if disk.get('boot')), None)
            if boot_disk_info:
                # 'source' は 'projects/PROJECT_ID/zones/ZONE/disks/DISK_NAME' の形式
                source_disk_url = boot_disk_info.get('source')
                if source_disk_url:
                    return source_disk_url.split('/')[-1]
        print("ブートディスクが見つかりませんでした。")
        return None
    except Exception as e:
        print(f"ブートディスク名の取得中にエラー: {e}")
        return None

async def create_gce_snapshot(disk_name: str, snapshot_name_prefix: str):
    """GCEディスクのスナップショットを作成する"""
    try:
        # スナップショット名に日時を付加して一意にする
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        snapshot_name = f"{snapshot_name_prefix}-{timestamp}"
        
        snapshot_body = {
            "name": snapshot_name,
            "description": f"Snapshot of {disk_name} created by Discord Bot at {timestamp}"
            # 必要に応じてラベルなどを追加
            # "labels": {
            #     "created-by": "discord-bot"
            # }
        }
        
        print(f"スナップショット作成リクエスト: disk='{disk_name}', name='{snapshot_name}'")
        
        request = compute_service.disks().createSnapshot(
            project=GCP_PROJECT_ID,
            zone=GCP_ZONE, # ゾーンディスクを想定
            disk=disk_name,
            body=snapshot_body
        )
        operation = request.execute()
        print(f"スナップショット作成オペレーション開始: {operation}")
        
        # オペレーションの完了を待機 (同期的に待つ場合は下記のようなループが必要)
        # self_link = operation.get('selfLink')
        # while True:
        #     op_request = compute_service.zoneOperations().get(project=GCP_PROJECT_ID, zone=GCP_ZONE, operation=operation['name'])
        #     op_response = op_request.execute()
        #     if op_response['status'] == 'DONE':
        #         if 'error' in op_response:
        #             raise Exception(f"スナップショット作成オペレーションエラー: {op_response['error']}")
        #         print(f"スナップショット '{snapshot_name}' が正常に作成されました。")
        #         break
        #     await asyncio.sleep(5) # 5秒待機して再確認
            
        return True, snapshot_name, None # 成功、スナップショット名、エラーなし
    except Exception as e:
        error_message = f"スナップショット作成中にエラー: {e}"
        print(error_message)
        return False, None, str(e) # 失敗、スナップショット名なし、エラーメッセージ

# --- Helper function for Webhook ---
async def send_vm_stopped_notification():
    """VM停止通知をDiscordに送信する非同期ヘルパー関数"""
    target_channel_id = DISCORD_CHANNEL_ID
    channel = bot.get_channel(target_channel_id)
    if channel:
        print(f"{target_channel_id} チャンネルに通知を送信します (async helper)。")
        view = ServerControlView() # Botのイベントループ内でViewインスタンスを作成
        await channel.send(
            "Minecraftサーバーが停止しました。\n" +
            "再度プレイする場合は下のボタンからサーバーを起動してください。",
            view=view
        )
        print("Discordへの通知メッセージ送信成功 (async helper)")
        return True
    else:
        print(f"エラー: チャンネルID {target_channel_id} が見つかりません (async helper)。")
        return False

# --- Flask Webhook Endpoint ---
@flask_app.route("/webhook/vm-stopped", methods=['POST'])
def vm_stopped_webhook(): # asyncを外して同期関数にする
    # ここで何らかの認証を入れるのが望ましい (例: 固定トークン、リクエスト元のIP制限など)
    # ... (認証コメントはそのまま)

    print("VM停止のWebhookを受信しました。")
    
    # Discordへの通知処理 (Viewの作成も含む) をBotのイベントループで実行
    future = asyncio.run_coroutine_threadsafe(send_vm_stopped_notification(), bot.loop)
    
    try:
        success = future.result(timeout=10) # タイムアウトを設定 (例: 10秒)
        if success:
            print("Discord通知処理完了 (via run_coroutine_threadsafe)")
            return "Webhook processed and notification sent.", 200
        else:
            print("Discord通知処理で問題発生 (via run_coroutine_threadsafe)")
            return "Webhook processed, but notification failed.", 500 # エラーを示すステータスコード
    except Exception as e:
        print(f"Discord通知処理中に例外発生 (via run_coroutine_threadsafe): {e}")
        return f"Error during notification: {e}", 500

# --- Discord Bot イベントハンドラ ---
@bot.event
async def on_ready():
    print(f'{bot.user.name} としてログインしました')
    print(f"Bot ID: {bot.user.id}")
    print(f"監視対象チャンネルID: {DISCORD_CHANNEL_ID}")
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)}個のスラッシュコマンドを同期しました")
    except Exception as e:
        print(f"スラッシュコマンドの同期に失敗: {e}")
    # TODO: VM停止を監視するバックグラウンドタスクを開始する
    # Flaskアプリを別スレッドで起動
    # werkzeugのログを無効化するなど、本番環境では調整が必要な場合がある
    # threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False), daemon=True).start()
    # print("Flask Webhookサーバーを http://0.0.0.0:8080 で起動しました")
    pass # Cloud Runで動かす場合は、gunicornなどがFlaskアプリをサーブするので、Bot内での起動は不要になることが多い

# --- Discord スラッシュコマンド ---
@bot.tree.command(name="mc_status", description="Minecraftサーバーの現在の状態を表示します。")
async def mc_status_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) # 応答に時間がかかる場合があるため
    status = await get_instance_status()
    if status:
        await interaction.followup.send(f"Minecraftサーバー ({GCP_INSTANCE_NAME}) の現在の状態: `{status}`")
    else:
        await interaction.followup.send("サーバーの状態を取得できませんでした。エラーログを確認してください。")

@bot.tree.command(name="mc_start", description="Minecraftサーバーを起動します。")
async def mc_start_command(interaction: discord.Interaction):
    await interaction.response.defer() # 先にdefer
    current_status = await get_instance_status()
    if current_status == "RUNNING":
        ip_address = await get_instance_external_ip()
        await interaction.followup.send(f"サーバーは既に起動しています。IPアドレス: `{ip_address or '取得失敗'}`", ephemeral=True)
        return
    if current_status == "TERMINATED":
        await interaction.followup.send("サーバーを起動中です...完了まで数分かかることがあります。", ephemeral=True)
        success = await start_instance()
        if success:
            await asyncio.sleep(15) # VM起動とIP割り当てまでの猶予 (必要に応じて調整)
            ip_address = await get_instance_external_ip()
            if ip_address:
                message = f"サーバーが起動しました！ IPアドレス:\n```{ip_address}```"
            else:
                message = "サーバーの起動処理は開始されましたが、IPアドレスの取得に失敗しました。少し待ってから `/mc_status` や `/mc_start` で再度確認してください。"
            await interaction.edit_original_response(content=message) # 最初の応答を編集
        else:
            await interaction.edit_original_response(content="サーバーの起動に失敗しました。エラーログを確認してください。")
    else:
        await interaction.followup.send(f"サーバーは現在 `{current_status}` 状態です。起動できません。", ephemeral=True)

@bot.tree.command(name="mc_backup", description="Minecraftサーバーのバックアップ(スナップショット)を作成します。")
async def mc_backup_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True) # 応答に時間がかかるため、ephemeralで

    current_status = await get_instance_status()
    if not current_status:
        await interaction.followup.send("サーバーの状態を取得できませんでした。バックアップは作成できません。", ephemeral=True)
        return

    # サーバーが起動中でもスナップショットは作成可能だが、整合性のためには停止中が望ましい場合がある
    # ここでは起動中でも許可する
    if current_status not in ["RUNNING", "TERMINATED"]:
         await interaction.followup.send(f"サーバーは現在 `{current_status}` 状態です。この状態ではバックアップを作成できません。", ephemeral=True)
         return

    await interaction.followup.send("サーバーのブートディスク名を取得しています...", ephemeral=True)
    boot_disk_name = await get_boot_disk_name()

    if not boot_disk_name:
        await interaction.edit_original_response(content="サーバーのブートディスク名の取得に失敗しました。バックアップは作成できません。")
        return

    snapshot_prefix = f"{GCP_INSTANCE_NAME}-backup" # スナップショット名のプレフィックス
    
    await interaction.edit_original_response(content=f"`{boot_disk_name}` のスナップショット作成を開始します...")

    success, snapshot_name, error = await create_gce_snapshot(boot_disk_name, snapshot_prefix)

    if success:
        message = f"""スナップショットの作成処理を開始しました。
スナップショット名: `{snapshot_name}`
作成完了まで数分かかることがあります。GCPコンソールで進捗を確認してください。"""
        await interaction.edit_original_response(content=message)
    else:
        message = f"""スナップショットの作成に失敗しました。
エラー: `{error}`"""
        await interaction.edit_original_response(content=message)

@bot.tree.command(name="help", description="利用可能なコマンドの一覧を表示します。")
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="コマンドヘルプ",
        description="利用可能なスラッシュコマンドは以下の通りです。",
        color=discord.Color.blue()
    )

    commands_list = []
    # bot.tree.get_commands() は ApplicationCommand オブジェクトのリストを返す
    # discord.app_commands.Command
    for command in bot.tree.get_commands():
        commands_list.append(f"**/{command.name}**: {command.description}")

    if commands_list:
        embed.add_field(name="コマンド", value="\n".join(commands_list), inline=False)
    else:
        embed.add_field(name="コマンド", value="利用可能なコマンドはありません。", inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)

# --- Botの起動 & Flaskアプリの起動 ---
async def main():
    # Flaskアプリを起動 (本番環境ではgunicornなどを使用することを想定)
    # ローカルテスト用にthreadingで起動する場合
    flask_thread = threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()
    print("Flask Webhookサーバーを http://0.0.0.0:8080 で起動しました (ローカルテスト用)")

    await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN or GCP_PROJECT_ID == "" or DISCORD_CHANNEL_ID == 0:
        print("エラー: config.pyに必要な設定がされていません。")
        # (個別のエラーチェックは省略)
    else:
        asyncio.run(main()) 