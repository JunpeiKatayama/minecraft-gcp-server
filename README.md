# Minecraft GCP Server 構築手順

このリポジトリは、Terraform を使って Google Cloud Platform (GCP) 上に Minecraft サーバーを構築・自動管理するためのものです。

---

## 必要なもの

- GCP プロジェクト
- サービスアカウントキー（JSON）
- Terraform（推奨: 1.0 以上）
- Git Bash などのターミナル

---

## 1. GCP API の有効化

下記リンクから各 API のページを開き、右上の「プロジェクト選択」でご自身のプロジェクトを選択し、「有効にする」ボタンを押してください。

- [Identity and Access Management (IAM) API](https://console.developers.google.com/apis/api/iam.googleapis.com/overview)
- [Compute Engine API](https://console.developers.google.com/apis/api/compute.googleapis.com/overview)
- [Cloud Resource Manager API](https://console.developers.google.com/apis/api/cloudresourcemanager.googleapis.com/overview)
- [Cloud Functions API](https://console.developers.google.com/apis/api/cloudfunctions.googleapis.com/overview)
- [Cloud Scheduler API](https://console.developers.google.com/apis/api/cloudscheduler.googleapis.com/overview)
- [Cloud Storage API](https://console.developers.google.com/apis/api/storage.googleapis.com/overview)
- [Artifact Registry API](https://console.developers.google.com/apis/api/artifactregistry.googleapis.com/overview)
- [Cloud Build API](https://console.developers.google.com/apis/api/cloudbuild.googleapis.com/overview)

---

## 2. サービスアカウントキーの準備

GCP コンソールでサービスアカウントを作成し、JSON キーをダウンロードします。
例: `C:\Users\jupei\gcp-key.json`

---

## 3. Cloud Function の準備

`cloud-function/` ディレクトリ内に、Cloud Function の本体である `main.py` と、Python の依存パッケージを記述した `requirements.txt` を用意します。

Terraform が自動的にこのディレクトリの内容を zip 化し、デプロイします。

- `main.py` … Cloud Function 本体（例：下記参照）
- `requirements.txt` … 依存パッケージ（例：下記参照）

```python
# cloud-function/main.py の例
import os
# ... (関数の中身)

def main(request):
    # ...
    return "OK"
```

```text
# cloud-function/requirements.txt の例
google-api-python-client
google-auth
```

---

## 4. 変数ファイルの編集

`terraform.tfvars` に GCP プロジェクト ID を記載します。
例:

```
project_id = "your-gcp-project-id"
```

---

## 5. Terraform の実行

1. サービスアカウントキーのパスを環境変数に設定

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/c/Users/jupei/gcp-key.json"
   ```

2. Terraform 初期化

   ```bash
   terraform init
   ```

3. プラン作成

   ```bash
   terraform plan
   ```

4. 適用
   ```bash
   terraform apply
   ```
   （`yes` と入力して適用）

---

## 6. 結果の確認

- 適用後、サーバーの外部 IP や Cloud Function の URL が表示されます。
- 再度確認したい場合は
  ```bash
  terraform output
  ```
  で出力値を確認できます。

---

## 7. 注意事項

- API 有効化後は反映まで数分かかる場合があります。
- `cloud-function.zip` がないとエラーになります。
- `.gitignore` で `*.tfvars` や `*.json` など機密情報は git 管理から除外されています。

---

## 8. 参考

- GCP 公式: [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- Minecraft 公式: [サーバーダウンロード](https://www.minecraft.net/ja-jp/download/server)

---

何か問題が発生した場合は、エラーメッセージをよく読み、API の有効化やファイルの配置を再確認してください。

---

## 📦 プロジェクト概要

このプロジェクトは、Google Cloud Platform (GCP) 上に **1〜3 人向けの Minecraft Java Edition サーバー** を構築するための Terraform 構成です。
無接続時にインスタンスを自動停止し、コストを最小限に抑える仕組みを含みます。

---

## 📁 フォルダ構成

```
minecraft-gcp-server/
├── main.tf                 # TerraformによるGCPリソース定義
├── variables.tf            # Terraform変数定義
├── terraform.tfvars        # プロジェクトIDなどユーザー設定
├── startup.sh              # VM起動時にMinecraftを自動インストール・起動
├── cloud-function/         # 接続人数チェック用Cloud Function
│   ├── main.py             # Cloud Function本体
│   └── requirements.txt    # Cloud Function用Python依存
└── README.md               # このガイド
```

---

## 🖥️ 推奨インスタンスサイズ

| プレイヤー数 | インスタンスサイズ | 月額目安（常時稼働）  | 備考                       |
| ------------ | ------------------ | --------------------- | -------------------------- |
| 1〜3 人      | `e2-small`         | 約 1,600 円〜2,000 円 | CPU×2、RAM 2GB。安価で安定 |
| 無料枠活用   | `e2-micro`         | 0 円（条件付き）      | 米リージョン限定、東京不可 |

- 無接続時に**自動でインスタンスを停止**することで、実際の稼働コストを 1/3 以下にできます。

---

## 🔧 使用技術

- Google Compute Engine（VM）
- Terraform（インフラ管理）
- Cloud Function（接続人数チェック）
- Cloud Scheduler（自動トリガー）
- Cloud Storage（任意：バックアップ保存用）

---

## ⚙️ 初期設定手順

1. **terraform.tfvars を編集**

   ```hcl
   project_id = "your-gcp-project-id"
   ```

2. **Terraform 適用**

   ```bash
   terraform init
   terraform apply
   ```

3. **Cloud Function のデプロイ**

   ```bash
   cd cloud-function
   gcloud functions deploy check_players \
     --runtime python310 \
     --trigger-http \
     --entry-point main \
     --set-env-vars MC_SERVER_IP=XXX.XXX.XXX.XXX,GCE_ZONE=asia-northeast1-b,GCE_INSTANCE_NAME=minecraft-server
   ```

4. **Cloud Scheduler 登録（例：5 分おき）**
   ```bash
   gcloud scheduler jobs create http minecraft-check \
     --schedule "*/5 * * * *" \
     --uri https://REGION-PROJECT.cloudfunctions.net/check_players \
     --http-method GET
   ```

---

## 💰 コスト最適化のヒント

- 無接続時に VM 自動停止
- 静的 IP を使わず、動的 IP で起動時のみ払い出し
- ディスクは 20GB 程度で十分、スナップショットバックアップ推奨
- Cloud Scheduler, Cloud Function は無料枠内で動作可能

---

## 🧩 カスタマイズポイント

- Minecraft のバージョン固定：`startup.sh`内の jar ダウンロードリンクを変更
- メモリ割り当て：`-Xmx1024M` などを適宜調整
- RCON による人数取得を別手段に変更したい場合は `main.py` を改修

---

## 🛠️ VM への接続とサーバー状態確認・トラブルシュート

### 1. VM への SSH 接続方法

#### A. GCP コンソールから接続

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 左メニュー「Compute Engine」→「VM インスタンス」
3. 対象 VM の「SSH」ボタンをクリック

#### B. ローカル PC から gcloud コマンドで接続

- 事前に [gcloud CLI](https://cloud.google.com/sdk/docs/install) をインストールし、認証しておく
- コマンド例：
  ```bash
  gcloud compute ssh minecraft-server --zone=asia-northeast1-b --project=minecfaft-gcp-server
  ```

---

### 2. Minecraft サーバーの状態確認

#### A. サーバープロセスの確認

```bash
ps aux | grep java
```

- `java -jar server.jar` のプロセスが表示されていればサーバーは起動中

#### B. サーバーファイルの確認

```bash
ls -l /opt/minecraft/
```

- `server.jar`、`eula.txt`、`server.properties` などが存在するか確認

#### C. EULA・設定ファイルの内容確認

```bash
cat /opt/minecraft/eula.txt
cat /opt/minecraft/server.properties
```

- `eula=true`、`enable-query=true` などが正しく設定されているか

#### D. サーバーログの確認（起動エラー時）

- サーバー起動時にエラーが出る場合、`/opt/minecraft/` 内に `logs/` ディレクトリや `latest.log` があれば内容を確認
- 例：
  ```bash
  cat /opt/minecraft/logs/latest.log
  ```

---

### 3. サーバーの手動起動・再起動

#### A. 手動で起動

```bash
cd /opt/minecraft
sudo java -Xmx1536M -Xms1536M -jar server.jar nogui
```

- エラーが出る場合はその内容を確認

#### B. screen でバックグラウンド起動

```bash
cd /opt/minecraft
sudo screen -dmS minecraft java -Xmx1536M -Xms1536M -jar server.jar nogui
```

- `screen -ls` でセッション確認、`screen -r minecraft` でアタッチ

---

### 4. よくあるトラブルと対処

- **プロセスがいない/すぐ落ちる**：Java バージョンやメモリ不足、JAR 破損を疑う
- **ファイルが 0 バイト**：ダウンロード URL ミスやネットワークエラー
- **EULA 未同意**：`eula.txt` の内容を確認
- **ポートが開いていない**：ファイアウォール設定を再確認
- **Query 失敗**：`enable-query=true`、UDP 25565 開放、サーバー起動直後は数分待つ

---

### 5. 参考コマンドまとめ

```bash
# サーバープロセス確認
ps aux | grep java

# サーバーファイル確認
ls -l /opt/minecraft/

# EULA・設定確認
cat /opt/minecraft/eula.txt
cat /opt/minecraft/server.properties

# サーバーログ確認
cat /opt/minecraft/logs/latest.log

# 手動起動
cd /opt/minecraft
sudo java -Xmx1536M -Xms1536M -jar server.jar nogui

# screenでバックグラウンド起動
sudo screen -dmS minecraft java -Xmx1536M -Xms1536M -jar server.jar nogui
screen -ls
screen -r minecraft
```

---

何か問題が発生した場合は、上記のコマンドやログを確認し、エラー内容をもとに対処してください。
分からない場合は、エラー内容を添えてご相談ください！

---
