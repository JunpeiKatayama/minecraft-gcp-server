import os
import socket
import struct
from googleapiclient import discovery
import google.auth

gce_zone = os.environ["GCE_ZONE"]
gce_instance_name = os.environ["GCE_INSTANCE_NAME"]
project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")

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
        
    ip = get_instance_external_ip(project_id, gce_zone, gce_instance_name)
    if not ip:
        # get_instance_external_ip内でエラーログは出力済み
        return "No external IP found or API error\n", 500 
        
    count = get_player_count(ip)
    print(f"最終的なプレイヤー数: {count}", flush=True)
    
    if count == 0:
        print("プレイヤー数0のため、インスタンス停止処理を開始します。", flush=True)
        try:
            credentials, _ = google.auth.default()
            service = discovery.build('compute', 'v1', credentials=credentials)
            resp = service.instances().stop(
                project=project_id,
                zone=gce_zone,
                instance=gce_instance_name
            ).execute()
            print(f"インスタンス停止API呼び出し成功: {resp}", flush=True)
        except Exception as e:
            print(f"インスタンス停止API呼び出し失敗: {e}", flush=True)
            return f"Player count: {count}, but failed to stop instance.\n", 500
            
    elif count == -1:
        print("プレイヤー数取得失敗のため、インスタンスは停止しません。", flush=True)
        # 失敗時は500エラーではなく、エラーを示すメッセージを返しつつもCloud Schedulerがリトライしないように2xxを返すことも検討
        # ここではシンプルにプレイヤー数-1を返す
        return f"Player count: {count} (Query failed)\n", 200 # もしくはエラーを示すために500

    print("main関数終了", flush=True)
    return f"Player count: {count}\n", 200 