import os
import socket
import struct
from googleapiclient import discovery
import google.auth
import requests
import datetime

gce_zone = os.environ["GCE_ZONE"]
gce_instance_name = os.environ["GCE_INSTANCE_NAME"]
project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
DISCORD_BOT_WEBHOOK_URL = os.environ.get("DISCORD_BOT_WEBHOOK_URL")

def get_instance_external_ip(project, zone, instance_name):
    print(f"get_instance_external_ip: project={project}, zone={zone}, instance_name={instance_name}", flush=True)
    credentials, _ = google.auth.default()
    service = discovery.build('compute', 'v1', credentials=credentials)
    try:
        instance = service.instances().get(
            project=project,
            zone=zone,
            instance=instance_name
        ).execute()
        interfaces = instance.get('networkInterfaces', [])
        if interfaces:
            access_configs = interfaces[0].get('accessConfigs', [])
            if access_configs:
                ip = access_configs[0].get('natIP')
                print(f"取得した外部IP: {ip}", flush=True)
                return ip
    except Exception as e:
        print(f"get_instance_external_ipでAPIエラー: {e}", flush=True)
    print("外部IPが取得できませんでした", flush=True)
    return None

# Minecraft Queryプロトコルで人数取得
def get_player_count(ip, port=25565, timeout=5): # タイムアウトを少し延長 (例: 5秒)
    print(f"Query開始: ip={ip}, port={port}, timeout={timeout}", flush=True)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        # handshake
        print("handshake送信試行", flush=True)
        # セッションIDは固定でOK (例: 0x01020304)
        # Pythonのint.to_bytes()を使う場合、バイトオーダーと符号に注意
        # ここではシンプルに固定バイト列を使用
        session_id_bytes = b"\x01\x02\x03\x04"
        handshake_payload = b"\xfe\xfd\x09" + session_id_bytes
        s.sendto(handshake_payload, (ip, port))
        print(f"handshake送信済み: {handshake_payload.hex()}", flush=True)
        data_handshake, addr_handshake = s.recvfrom(2048)
        print(f"handshake応答受信 from {addr_handshake}: {data_handshake}", flush=True)

        # チャレンジトークンを抽出
        # 応答の最初の1バイトはタイプ (0x09)
        # 次の4バイトがセッションID (エコーバック)
        # その後がNULL終端のチャレンジトークン文字列
        if data_handshake[0] != 0x09 or data_handshake[1:5] != session_id_bytes:
            print(f"handshake応答のタイプまたはセッションIDが不正です。type={data_handshake[0]}, session_id={data_handshake[1:5].hex()}", flush=True)
            return -1
        
        challenge_token_str = data_handshake[5:data_handshake.find(b'\x00', 5)].decode('ascii')
        challenge_token_int = int(challenge_token_str)
        # チャレンジトークンはネットワークバイトオーダー (ビッグエンディアン) の符号付き32ビット整数として送信
        challenge_token_bytes = struct.pack('>i', challenge_token_int)
        print(f"抽出したチャレンジトークン: str='{challenge_token_str}', int={challenge_token_int}, bytes={challenge_token_bytes.hex()}", flush=True)

        # stat
        print("stat送信試行", flush=True)
        # 基本statリクエスト: タイプ0x00, セッションID, チャレンジトークン
        # Full statリクエストにするには、チャレンジトークンの後にペイロード (4バイトのNULLなど) を追加
        stat_payload = b"\xfe\xfd\x00" + session_id_bytes + challenge_token_bytes + b"\x00\x00\x00\x00" # Full stat
        s.sendto(stat_payload, (ip, port))
        print(f"stat送信済み (トークン使用): {stat_payload.hex()}", flush=True)
        data_stat, addr_stat = s.recvfrom(4096) # 応答データが大きくなる可能性があるのでバッファを増やす
        print(f"stat応答受信 from {addr_stat}: {data_stat}", flush=True)
        
        if b'numplayers' in data_stat:
            parts = data_stat.split(b'\x00')
            try:
                idx = parts.index(b'numplayers')
                player_count = int(parts[idx+1])
                print(f"プレイヤー数抽出成功: {player_count}", flush=True)
                return player_count
            except (ValueError, IndexError) as e:
                print(f"プレイヤー数抽出失敗: {e}, parts: {parts}", flush=True)
        else:
            print("stat応答にnumplayersが含まれていません", flush=True)
            
    except socket.timeout:
        print(f"Query失敗: socket.timeout ({timeout}秒)", flush=True)
    except Exception as e:
        print(f"Query失敗: {type(e).__name__} - {e}", flush=True)
    return -1

def main(request):
    print("main関数開始", flush=True)
    if not project_id:
        print("エラー: 環境変数 GCP_PROJECT が設定されていません。", flush=True)
        return "Configuration error: GCP_PROJECT not set\n", 500

    if not DISCORD_BOT_WEBHOOK_URL:
        print("警告: 環境変数 DISCORD_BOT_WEBHOOK_URL が設定されていません。VM停止通知は送信されません。", flush=True)

    ip = get_instance_external_ip(project_id, gce_zone, gce_instance_name)
    if not ip:
        return "No external IP found or API error\n", 500

    count = get_player_count(ip)
    print(f"最終的なプレイヤー数: {count}", flush=True)

    if count == 0:
        print("プレイヤー数0のため、インスタンス停止処理を開始します。", flush=True)
        try:
            credentials, _ = google.auth.default()
            service = discovery.build('compute', 'v1', credentials=credentials)

            # --- スナップショット作成処理 --- 
            snapshot_name = f"{gce_instance_name}-snapshot-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
            print(f"VM停止前にスナップショットを作成します: {snapshot_name}", flush=True)
            try:
                snapshot_body = {
                    'name': snapshot_name,
                    'description': f'Automatic snapshot for {gce_instance_name} before shutdown on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                }
                # VMインスタンスの最初のディスク (通常はブートディスク) を対象とする
                # より堅牢にするには、インスタンス情報からディスク名を正確に取得する
                # ここではインスタンス名と同じ名前のディスクを想定 (一般的なTerraform構成)
                snapshot_op = service.disks().createSnapshot(
                    project=project_id,
                    zone=gce_zone, # スナップショットはゾーンディスクから作成
                    disk=gce_instance_name, # インスタンス名と同じディスク名と仮定
                    body=snapshot_body
                ).execute()
                print(f"スナップショット作成API呼び出し成功: {snapshot_op}", flush=True)
                # スナップショット完了を待つ場合はここでポーリング処理が必要だが、今回は呼び出しのみ
            except Exception as e_snap:
                print(f"スナップショット作成中にエラー: {e_snap}", flush=True)
            # --- スナップショット作成処理ここまで ---

            stop_op = service.instances().stop(
                project=project_id,
                zone=gce_zone,
                instance=gce_instance_name
            ).execute()
            print(f"インスタンス停止API呼び出し成功: {stop_op}", flush=True)

            if DISCORD_BOT_WEBHOOK_URL:
                print(f"Discord Bot Webhook ({DISCORD_BOT_WEBHOOK_URL}) に通知を試みます。", flush=True)
                try:
                    response = requests.post(DISCORD_BOT_WEBHOOK_URL, timeout=10)
                    response.raise_for_status()
                    print(f"Discord Bot Webhookへの通知成功。ステータス: {response.status_code}", flush=True)
                except requests.exceptions.RequestException as e:
                    print(f"Discord Bot Webhookへの通知失敗: {e}", flush=True)
            else:
                print("DISCORD_BOT_WEBHOOK_URLが未設定のため、通知はスキップされました。", flush=True)

        except Exception as e:
            print(f"インスタンス停止処理またはWebhook通知中にエラー: {e}", flush=True)
            return f"Player count: {count}, but failed during stop process or notification.\n", 500

    elif count == -1:
        print("プレイヤー数取得失敗のため、インスタンスは停止しません。", flush=True)
        return f"Player count: {count} (Query failed)\n", 200

    print("main関数終了", flush=True)
    return f"Player count: {count}\n", 200 