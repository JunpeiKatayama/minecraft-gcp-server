import os
import google.auth
from googleapiclient import discovery
from datetime import datetime, timezone

# 環境変数から設定を取得
PROJECT_ID = os.environ.get("GCP_PROJECT")
SNAPSHOT_PREFIX = os.environ.get("SNAPSHOT_PREFIX", "minecraft-server-snapshot-") # デフォルトのプレフィックス
SNAPSHOT_RETENTION_COUNT = int(os.environ.get("SNAPSHOT_RETENTION_COUNT", 7)) # デフォルトの保持数 (例: 最新7個)

def delete_old_snapshots_http(request): # HTTPトリガー用のエントリポイント
    print(f"delete_old_snapshots_http関数開始。プロジェクト: {PROJECT_ID}, プレフィックス: {SNAPSHOT_PREFIX}, 保持数: {SNAPSHOT_RETENTION_COUNT}", flush=True)
    
    if not PROJECT_ID:
        print("エラー: 環境変数 GCP_PROJECT が設定されていません。", flush=True)
        return "Configuration error: GCP_PROJECT not set", 500

    try:
        credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/compute'])
        service = discovery.build('compute', 'v1', credentials=credentials)

        result = service.snapshots().list(project=PROJECT_ID).execute()
        snapshots = result.get('items', [])

        relevant_snapshots = []
        for snapshot in snapshots:
            if snapshot['name'].startswith(SNAPSHOT_PREFIX):
                try:
                    # creationTimestamp は RFC3339 UTC 形式 (例: '2024-01-15T10:00:00.000-08:00')
                    # Python 3.7+ の datetime.fromisoformat でパース可能
                    creation_time = datetime.fromisoformat(snapshot['creationTimestamp'])
                    relevant_snapshots.append({'name': snapshot['name'], 'creationTimestamp': creation_time, 'id': snapshot['id']})
                except Exception as e_parse:
                    print(f"スナップショット {snapshot['name']} の作成日時パースエラー: {e_parse}", flush=True)
        
        # 作成日時の降順（新しいものが先頭）でソート
        relevant_snapshots.sort(key=lambda s: s['creationTimestamp'], reverse=True)
        
        print(f"見つかった関連スナップショット ({len(relevant_snapshots)}個):", flush=True)
        for snap_idx, snap in enumerate(relevant_snapshots):
            print(f"  [{snap_idx+1}] {snap['name']} (作成日時: {snap['creationTimestamp']})", flush=True)

        if len(relevant_snapshots) > SNAPSHOT_RETENTION_COUNT:
            snapshots_to_delete = relevant_snapshots[SNAPSHOT_RETENTION_COUNT:]
            print(f"保持数({SNAPSHOT_RETENTION_COUNT})を超えるため、以下のスナップショットを削除します ({len(snapshots_to_delete)}個):", flush=True)
            for snap_to_delete in snapshots_to_delete:
                try:
                    print(f"  - {snap_to_delete['name']} を削除中...", flush=True)
                    delete_op = service.snapshots().delete(
                        project=PROJECT_ID,
                        snapshot=snap_to_delete['name']
                    ).execute()
                    print(f"    スナップショット削除API呼び出し成功: {snap_to_delete['name']}, operation: {delete_op.get('name')}", flush=True)
                except Exception as e_del:
                    print(f"    スナップショット {snap_to_delete['name']} の削除中にエラー: {e_del}", flush=True)
        else:
            print(f"関連スナップショット数({len(relevant_snapshots)})が保持数({SNAPSHOT_RETENTION_COUNT})以下のため、削除は行いません。", flush=True)
            
        return "Snapshot cleanup process completed successfully.", 200

    except Exception as e:
        print(f"スナップショットクリーンアップ処理中に予期せぬエラー: {e}", flush=True)
        return f"Error during snapshot cleanup: {e}", 500
