## 📦 プロジェクト概要

このプロジェクトは、Google Cloud Platform (GCP) 上に **1〜3 人向けの Minecraft Java Edition サーバー** を構築し、Discord Bot を通じて管理するための Terraform 構成です。
主な機能は以下の通りです。

- Minecraft サーバーの自動構築 (Debian 12, Java 21, 指定バージョン Minecraft Server)
- サーバー無接続時の GCE インスタンス自動停止によるコスト最適化
- VM 停止時におけるサーバーセーブデータの自動バックアップ (ディスクスナップショット作成)
- 定期的なバックアップのローテーション (古いスナップショットの自動削除)
- Discord Bot (Python, Cloud Run) による以下の操作:
  - サーバー停止時の Discord 通知（「サーバー起動」ボタン付き）
  - Discord からの VM 起動と IP アドレス通知
  - Discord からの VM 状態確認

---

## 💰 予想コスト (現時点での試算)

この構成で発生する可能性のある主なコストは以下の通りです。これらの多くは GCP の無料枠の範囲に収まるか、非常に低コストで運用できる可能性があります。
**実際のコストは、リージョン、VM の稼働時間、選択するマシンタイプ、ストレージ使用量、ネットワークトラフィックなどによって変動します。**

- **Google Compute Engine (GCE):**

  - **VM インスタンス:** サーバー起動中のみ課金されます。自動停止機能により、実際のプレイ時間に応じた料金になります。選択するマシンタイプによってコストが大きく変わります。以下は東京リージョン (`asia-northeast1`) におけるオンデマンド料金の目安です (2024 年 1 月時点、ブートディスクやネットワーク費用は含まず)。

    | インスタンスタイプ | vCPU        | メモリ (GB) | 月額 (常時稼働の場合の概算) | 1 時間あたり (概算) |
    | :----------------- | :---------- | :---------- | :-------------------------- | :------------------ |
    | `e2-micro`         | 0.25 (共有) | 1           | 約 $7 - $10                 | 約 $0.010 - $0.014  |
    | `e2-small`         | 0.5 (共有)  | 2           | 約 $15 - $20                | 約 $0.020 - $0.027  |
    | `e2-medium`        | 1 (共有)    | 4           | 約 $30 - $40                | 約 $0.040 - $0.054  |
    | `e2-standard-2`    | 2           | 8           | 約 $60 - $80                | 約 $0.080 - $0.108  |

    _注意:_
    _ 上記の月額料金は、1 ヶ月を 730 時間として計算した概算です。
    _ 持続利用割引 (SUD) や確約利用割引 (CUD) を適用することで、さらにコストを削減できる場合があります。 \* 最新の正確な料金は、必ず [Google Cloud Platform Console](https://console.cloud.google.com/billing) または [Google Cloud Pricing Calculator](https://cloud.google.com/products/calculator) でご確認ください。
    \_ **実際に試したところ、`e2-standard-2` 未満のスペックでは Minecraft サーバーが安定して動作しないことが確認されています。快適なプレイのためには `e2-standard-2` 以上のスペックを推奨します。**

  - **ブートディスク** (20GB デフォルト): 低容量であれば無料枠の範囲または月額数ドル未満。
  - **ディスクスナップショット:** Minecraft サーバー停止時に自動作成されます。差分保存のため効率的ですが、保持数やデータ量に応じてストレージコスト (アジア太平洋リージョンで約$0.026/GB/月) が発生します。古いスナップショットは自動的に削除されます。
  - **外部 IP アドレス:** VM 起動中のみエフェメラル IP アドレスを使用するため、通常は追加料金なし。静的 IP アドレスを予約すると別途料金が発生します。

- **Cloud Functions:**
  - `check-players` (プレイヤー数監視・VM 停止・スナップショット作成): 無料枠が比較的大きく、このプロジェクトの用途であれば通常無料枠内に収まる見込みです。
  - `delete-old-snapshots` (スナップショット削除): こちらも軽量な処理のため、無料枠内に収まる見込みです。
- **Cloud Scheduler:**
  - `check-players` 用と `delete-old-snapshots` 用の 2 つのジョブが無料枠 (月間 3 ジョブまで無料) の範囲内で動作します。
- **Cloud Storage:**
  - Cloud Function のソースコード (zip ファイル) の保存に使用します。容量は非常に小さいため、コストはほぼ発生しません。
- **Artifact Registry:**
  - Docker イメージの保存に使用します。小規模なプロジェクトであれば無料枠 (最初の 0.5GiB/月まで無料など) の範囲に収まるか、月額数ドル未満の見込みです。
- **Cloud Build:**
  - 無料枠 (1 日あたり 120 ビルド分無料など) があります。Bot のコード更新頻度が低ければ無料枠内に収まる可能性があります。
- **Cloud Run:**
  - Discord Bot のホスティングに使用します。**応答性向上のため最小インスタンス数が `1` に設定されています。** これにより、無料枠を超える可能性があり、月額数ドル程度のコストが発生する場合があります。 (マシンタイプやリージョンによる)
- **ネットワークトラフィック:**
  - 主に Minecraft サーバーのプレイによる下りトラフィックが課金対象となりますが、小規模サーバーであれば大きな金額にはなりにくいです。

**コスト削減のポイント:**

- VM の自動停止機能が最も効果的です。
- スナップショットの保持数 (`snapshot_retention_count` 変数) を調整する。
- 不要なリソース (古いスナップショットを手動で更に削除するなど、未使用の静的 IP など) を定期的に確認・削除する。
- GCP の料金計算ツールや請求ダッシュボードでコストを監視する。

**あくまで現時点での一般的な試算であり、詳細な見積もりは GCP の料金計算ツールをご利用ください。**

---

## 📁 フォルダ構成

```
minecraft-gcp-server/
├── main.tf                 # TerraformによるGCPリソース定義
├── variables.tf            # Terraform変数定義
├── terraform.tfvars        # プロジェクトIDなどユーザー設定
├── startup.sh              # VM起動時にMinecraftを自動インストール・起動
├── cloud-function/         # 接続人数チェック・VM停止・スナップショット作成用Cloud Function
│   ├── main.py             # Cloud Function本体
│   └── requirements.txt    # Cloud Function用Python依存
├── cloud-function-delete-snapshots/ # 古いスナップショット削除用Cloud Function
│   ├── main.py             # Cloud Function本体
│   └── requirements.txt    # Cloud Function用Python依存
├── discord-bot/            # Discord Bot (サーバー管理用)
│   ├── bot.py              # Discord Bot本体 (Flask Webhook含む)
│   ├── requirements.txt    # Discord Bot用Python依存
│   ├── Dockerfile          # Discord Botコンテナ化用
│   └── config.sample.py    # ローカル実行時の設定ファイルテンプレート
└── README.md               # このガイド
```

---

## 🔧 使用技術

- **GCP:**
  - Google Compute Engine (GCE): Minecraft サーバー実行用 VM
  - Cloud Functions:
    - プレイヤー数監視、VM 自動停止、スナップショット作成
    - 古いスナップショットの定期的な削除
  - Cloud Scheduler: Cloud Function の定期実行
  - Cloud Storage: Cloud Function のソースコード保存 (任意: バックアップ保存用)
  - Artifact Registry: Discord Bot の Docker イメージ格納
  - Cloud Build: Docker イメージのビルドとプッシュ
  - Cloud Run: Discord Bot のホスティング (最小インスタンス 1 で稼働)
  - IAM (Identity and Access Management): 各サービスへの権限付与
- **Minecraft:**
  - Minecraft Java Edition Server
- **Discord Bot:**
  - Python
  - discord.py: Discord API ラッパー
  - Flask: Webhook 受信用マイクロフレームワーク
  - google-api-python-client: GCP API 操作
- **Infrastructure as Code:**
  - Terraform: GCP リソース全体のプロビジョニングと管理

---

## 必要なもの

- GCP プロジェクト
- 課金が有効になっている GCP アカウント
- [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) がインストール・認証済みであること
- [Terraform](https://developer.hashicorp.com/terraform/install) (推奨: 1.0 以上)
- Git
- Discord アカウントと、Bot を作成・招待する権限のあるサーバー
- Discord Bot トークン
- Discord 通知用チャンネル ID

---

## 1. GCP API の有効化

Terraform がリソースを作成するために、以下の GCP API が有効になっている必要があります。
Terraform の `google_project_service` リソースにより、`apply` 時に自動で有効化が試みられますが、事前に手動で有効化しておくと確実です。

下記リンクから各 API のページを開き、右上の「プロジェクト選択」でご自身のプロジェクトを選択し、「有効にする」ボタンを押してください。

- [Compute Engine API](https://console.developers.google.com/apis/api/compute.googleapis.com/overview)
- [Cloud Functions API](https://console.developers.google.com/apis/api/cloudfunctions.googleapis.com/overview)
- [Cloud Scheduler API](https://console.developers.google.com/apis/api/cloudscheduler.googleapis.com/overview)
- [Cloud Storage API](https://console.developers.google.com/apis/api/storage.googleapis.com/overview)
- [Artifact Registry API](https://console.developers.google.com/apis/api/artifactregistry.googleapis.com/overview)
- [Cloud Build API](https://console.developers.google.com/apis/api/cloudbuild.googleapis.com/overview)
- [Cloud Run API](https://console.developers.google.com/apis/api/run.googleapis.com/overview)
- [Identity and Access Management (IAM) API](https://console.developers.google.com/apis/api/iam.googleapis.com/overview)
- [Cloud Resource Manager API](https://console.developers.google.com/apis/api/cloudresourcemanager.googleapis.com/overview) (通常デフォルトで有効)

---

## 2. サービスアカウントキーの準備 (ローカル実行時、任意)

Terraform をローカルマシンから実行する場合、GCP への認証が必要です。
推奨は `gcloud auth application-default login` コマンドを使用する方法ですが、サービスアカウントキーを使用することも可能です。

サービスアカウントキーを使用する場合:
GCP コンソールでサービスアカウントを作成し、JSON キーをダウンロードします。
例: `C:\\Users\\your_user\\gcp-key.json` (Windows) または `/home/your_user/gcp-key.json` (Linux/macOS)

---

## 3. Discord Bot の準備

1.  **Discord Developer Portal で Bot を作成**

    - [Discord Developer Portal](https://discord.com/developers/applications) にアクセスし、新しい Application を作成します。
    - 作成した Application の「Bot」タブで「Add Bot」をクリックして Bot ユーザーを作成します。
    - 「TOKEN」セクションで「Reset Token」または「Copy」をクリックし、Bot トークンを控えておきます。**このトークンは絶対に公開しないでください。**
    - 「Privileged Gateway Intents」の項目で、「SERVER MEMBERS INTENT」と「MESSAGE CONTENT INTENT」を有効にしてください（Bot の機能に応じて必要であれば）。現状の Bot では必須ではありませんが、将来的な拡張のために有効にしておいても良いでしょう。

2.  **Bot を Discord サーバーに招待**

    - Application の「OAuth2」→「URL Generator」タブを開きます。
    - 「SCOPES」で `bot` と `applications.commands` を選択します。
    - 「BOT PERMISSIONS」で、Bot に必要な権限（例: `Send Messages`, `Read Message History`, `Use Slash Commands` など）を選択します。
    - 生成された URL にアクセスし、Bot を追加したいサーバーを選択して認証します。

3.  **通知用チャンネル ID の取得**
    - Discord のユーザー設定で「詳細設定」を開き、「開発者モード」をオンにします。
    - Bot に通知させたいチャンネルを右クリックし、「ID をコピー」を選択してチャンネル ID を控えます。

---

## 4. 変数ファイルの編集

プロジェクトルートに `terraform.tfvars` というファイルを作成（または既存のファイルを編集）し、以下の情報を記述します。

```hcl
# terraform.tfvars

project_id          = "your-gcp-project-id"  # あなたのGCPプロジェクトID
region              = "asia-northeast1"      # 例: 東京リージョン
zone                = "asia-northeast1-b"    # 例: 東京リージョンbゾーン

# Discord Bot 設定 (重要: これらの値は機密情報として扱ってください)
discord_bot_token   = "YOUR_DISCORD_BOT_TOKEN" # 手順3で取得したDiscord Botトークン
discord_channel_id  = "YOUR_DISCORD_CHANNEL_ID" # 手順3で取得した通知用チャンネルID (数値ではなく文字列で囲む)

# (任意) Cloud Build と Artifact Registry を使用するリージョン
# デフォルトは "us-central1" です。特定のリージョンでクォータ制限がある場合に指定します。
# cloud_build_region  = "us-central1"

# (任意) スナップショット保持数
# Minecraftサーバー停止時に作成されるディスクスナップショットの最大保持数です。
# これを超える古いスナップショットは自動的に削除されます。
# snapshot_retention_count = 7 # デフォルトは7
```

**注意:** `terraform.tfvars` ファイルは `.gitignore` に記載されているため、Git リポジトリにはコミットされません。これにより、機密情報が誤って公開されるのを防ぎます。

---

## 5. Terraform の実行

1.  **GCP 認証**

    - **推奨:** `gcloud auth application-default login` を実行し、ブラウザ経由で認証します。
      ```bash
      gcloud auth application-default login
      ```
    - サービスアカウントキーを使用する場合 (非推奨): 環境変数 `GOOGLE_APPLICATION_CREDENTIALS` にキーファイルのパスを設定します。
      ```bash
      # Linux / macOS
      export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/gcp-key.json"
      # Windows (Git Bashなど)
      export GOOGLE_APPLICATION_CREDENTIALS="/c/Users/your_user/gcp-key.json"
      ```

2.  **Terraform 初期化**
    プロジェクトルートディレクトリで以下のコマンドを実行します。

    ```bash
    terraform init
    ```

3.  **(任意) プラン作成**
    どのようなリソースが作成・変更されるかを確認します。

    ```bash
    terraform plan
    ```

4.  **適用**
    リソースを実際に GCP 上に作成します。途中で確認を求められるので `yes` と入力します。
    ```bash
    terraform apply
    ```
    `terraform apply` が完了すると、Cloud Function や Cloud Run サービスがデプロイされ、Discord Bot が起動可能な状態になります。

---

## 6. 主な機能と動作の確認

`terraform apply` が成功すると、以下の主要な自動化機能が動作を開始します。

- **Minecraft サーバー自動停止とバックアップ:**
  - Cloud Function (`check-players`) が 5 分ごとに Minecraft サーバーのプレイヤー数を確認します。
  - プレイヤーが 0 人になると、Cloud Function はまずサーバーのディスクスナップショットを作成し、その後 VM を停止します。
  - VM 停止後、Discord Bot の Webhook URL を呼び出します。
- **Discord Bot 通知:**
  - Webhook を受信した Discord Bot は、指定されたチャンネルに「サーバーが停止しました」というメッセージと「サーバーを起動」ボタンを送信します。
- **スナップショット自動ローテーション:**
  - 別の Cloud Function (`delete-old-snapshots`) が毎日定刻 (デフォルト午前 3 時 JST) に実行されます。
  - この Function は、`check-players` によって作成されたスナップショットのうち、設定された保持数 (`snapshot_retention_count`) を超える古いものを自動的に削除します。

**利用可能な Discord スラッシュコマンド:**

- `/mc_status`: Minecraft サーバーの現在の状態（RUNNING, TERMINATED など）を表示します。
- `/mc_start`: Minecraft サーバーを起動します。成功すると IP アドレスを通知します。

これらの動作やコマンドを Discord の指定チャンネルで実行して、システム全体が正しく機能することを確認してください。

---

## 7. 結果の確認 (Terraform Output)

Terraform によって作成されたリソースの情報（Minecraft サーバーの IP アドレス、Cloud Function の URL など）は、`terraform apply` の最後に出力されます。
再度確認したい場合は、以下のコマンドで出力値を確認できます。

```bash
terraform output
```

---

## 8. 注意事項

- **API の有効化:** GCP API の有効化は、Terraform が試みるものの、反映に数分かかる場合や、手動での確認が必要な場合があります。エラーが発生した場合は、API が正しく有効になっているか確認してください。
- **Cloud Function のソースコード:** `cloud-function/` および `cloud-function-delete-snapshots/` ディレクトリの内容は `terraform apply` 時に自動的に zip 化され、Cloud Storage にアップロードされます。
- **Discord Bot のイメージ:** `discord-bot/` ディレクトリの内容 (Dockerfile 含む) は `terraform apply` 時に Cloud Build によって Docker イメージとしてビルドされ、Artifact Registry にプッシュされた後、Cloud Run サービスにデプロイされます。
- **機密情報:** `terraform.tfvars` やサービスアカウントキー (`*.json`) は `.gitignore` によって Git の管理対象外となっています。これらのファイルは絶対にリポジトリにコミットしないでください。
- **コスト:**
  - この構成では、VM が無操作時に自動停止し、スナップショットもローテーションされるためコスト最適化が図られていますが、Cloud Run (最小インスタンス 1)、スナップショットストレージ、その他のサービスにも利用状況に応じたコストが発生します。
  - 詳細は「💰 予想コスト」セクションを参照し、GCP の無料枠や料金体系を確認してください。
  - Cloud Build は一定の無料枠がありますが、頻繁にビルドすると料金が発生します。

---

## 9. Minecraft サーバー関連

### ⚙️ 初期設定手順 (旧 README より参考、Terraform で自動化済み箇所も含む)

以前の README に記載されていた手動での Cloud Function デプロイや Cloud Scheduler 登録の手順は、現在 Terraform によって自動化されています。
`startup.sh` が VM 起動時に Minecraft サーバーをセットアップします。

### 🧩 カスタマイズポイント

- **Minecraft のバージョン固定:** `startup.sh`内の `MINECRAFT_VERSION` 変数を変更。
- **VM のメモリ割り当て:** `startup.sh` 内の Java 起動コマンドの `-Xmx` `-Xms` パラメータや、`variables.tf` の `machine_type` を適宜調整。
- **Cloud Function のロジック変更:** `cloud-function/main.py` や `cloud-function-delete-snapshots/main.py` を改修。
- **Discord Bot の機能拡張:** `discord-bot/bot.py` を改修。
- **スナップショット保持数の変更:** `terraform.tfvars` で `snapshot_retention_count` の値を変更するか、`variables.tf` のデフォルト値を変更します。

---

## 🛠️ VM への接続とサーバー状態確認・トラブルシュート

### 1. VM への SSH 接続方法

#### A. GCP コンソールから接続

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 左メニュー「Compute Engine」→「VM インスタンス」
3. 対象 VM (`minecraft-server` など) の「SSH」ボタンをクリック

#### B. ローカル PC から gcloud コマンドで接続

- 事前に [gcloud CLI](https://cloud.google.com/sdk/docs/install) をインストールし、認証しておく
- コマンド例 (プロジェクト ID やゾーンは適宜置き換えてください):
  ```bash
  gcloud compute ssh YOUR_INSTANCE_NAME --zone=YOUR_ZONE --project=YOUR_PROJECT_ID
  # 例: gcloud compute ssh minecraft-server --zone=asia-northeast1-b --project=minecfaft-gcp-server
  ```

---

### 2. Minecraft サーバーの状態確認 (VM 接続後)

#### A. サーバープロセスの確認

```bash
ps aux | grep java
```

- `java -jar server.jar` (または `minecraft_server.jar`) のプロセスが表示されていればサーバーは起動中

#### B. サーバーファイルの確認

```bash
ls -l /opt/minecraft/
```

- `server.jar` (または `minecraft_server.X.X.X.jar`)、`eula.txt`、`server.properties` などが存在するか確認

#### C. EULA・設定ファイルの内容確認

```bash
cat /opt/minecraft/eula.txt
cat /opt/minecraft/server.properties
```

- `eula=true` (`startup.sh`で自動同意)、`enable-query=true` (`server.properties`で設定推奨) などが正しく設定されているか

#### D. サーバーログの確認（起動エラー時など）

- サーバーログは `/opt/minecraft/logs/latest.log` にあります。
- 例：
  ```bash
  cat /opt/minecraft/logs/latest.log
  # tail -f /opt/minecraft/logs/latest.log (リアルタイム表示)
  ```

---

### 3. サーバーの手動起動・再起動 (VM 接続後、通常は不要)

`startup.sh` により、VM 起動時に Minecraft サーバーは自動的に `screen` セッション内で起動されます。
手動での操作が必要な場合は以下を参考にしてください。

#### A. screen セッションへのアタッチ

```bash
sudo screen -r minecraft
```

- `Ctrl+A` を押してから `D` を押すとデタッチできます。

#### B. 手動で起動 (screen を使わない場合、フォアグラウンド実行)

```bash
cd /opt/minecraft
sudo java -Xmx1536M -Xms1536M -jar server.jar nogui # メモリ等はstartup.shに合わせる
```

---

### 4. よくあるトラブルと対処

- **Discord Bot が反応しない:**
  - Cloud Run のログを確認 (GCP コンソール > Cloud Run > `minecraft-discord-bot` > ログ)。
  - `terraform.tfvars` の `discord_bot_token` や `discord_channel_id` が正しいか確認。
  - Bot が Discord サーバーに正しく招待され、必要な権限を持っているか確認。
  - Discord Developer Portal で Bot のインテント設定を確認。
- **VM が起動しない/Minecraft サーバーが起動しない:**
  - GCP コンソールの VM インスタンスのシリアルポートログを確認。
  - `startup.sh` の実行エラーがないか確認 (上記シリアルポートログ内)。
  - VM に SSH 接続し、Minecraft サーバーのログ (`/opt/minecraft/logs/latest.log`) を確認。
  - Java のバージョン、メモリ不足、JAR ファイルの破損などを疑う。
- **Cloud Function (`check-players`) が動作しない/エラーになる:**
  - GCP コンソールの Cloud Functions のログ (`check-players`) を確認。
  - 環境変数 (`GCE_ZONE`, `GCE_INSTANCE_NAME`, `DISCORD_BOT_WEBHOOK_URL` など) が正しく設定されているか確認。
  - Cloud Function のサービスアカウントに必要な権限 (Compute Instance Admin, Compute Storage Admin など) が付与されているか確認。
- **Cloud Function (`delete-old-snapshots`) が動作しない/エラーになる:**
  - GCP コンソールの Cloud Functions のログ (`delete-old-snapshots`) を確認。
  - 環境変数 (`GCP_PROJECT`, `SNAPSHOT_PREFIX`, `SNAPSHOT_RETENTION_COUNT`) が正しく設定されているか確認。
  - Cloud Function のサービスアカウントに必要な権限 (Compute Storage Admin など。スナップショットのリスト取得・削除) が付与されているか確認。
- **Query 失敗 (Cloud Function `check-players` ログ):**
  - Minecraft サーバーの `server.properties` で `enable-query=true` และ `query.port=25565` (デフォルト) が設定されているか確認。
  - GCP ファイアウォールで UDP ポート `25565` が開放されているか確認 (Terraform で設定済みのはず)。
  - サーバー起動直後は Query に応答するまで少し時間がかかる場合があります。
- **スナップショットが作成されない/削除されない:**
  - Cloud Function (`check-players` または `delete-old-snapshots`) のログでスナップショット関連の API 呼び出しが成功しているか、エラーが出ていないか確認。
  - Cloud Function のサービスアカウントに適切な IAM 権限が付与されているか確認。
  - スナップショットの命名規則やプレフィックスが Cloud Function の期待通りか確認。

---

### 5. 参考コマンドまとめ (VM 接続後)

```bash
# サーバープロセス確認
ps aux | grep java

# screenセッション確認・アタッチ
sudo screen -ls
sudo screen -r minecraft

# サーバーファイル確認
ls -l /opt/minecraft/

# EULA・設定確認
cat /opt/minecraft/eula.txt
cat /opt/minecraft/server.properties

# サーバーログ確認
cat /opt/minecraft/logs/latest.log
tail -f /opt/minecraft/logs/latest.log

# (参考) 手動起動 (通常はstartup.shによる自動起動)
# cd /opt/minecraft
# sudo java -XmxYOUR_MEM -XmsYOUR_MEM -jar server.jar nogui
```

---

何か問題が発生した場合は、各サービスのログ（Cloud Run, Cloud Functions, VM シリアルポート, Minecraft サーバーログ）を確認し、エラー内容をもとに対処してください。
それでも解決しない場合は、エラーメッセージを添えて Issue 等でご相談ください。

---
