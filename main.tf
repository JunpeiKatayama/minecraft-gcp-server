// GCPプロバイダー設定
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

// VM用サービスアカウント
resource "google_service_account" "minecraft_sa" {
  account_id   = "minecraft-server-sa"
  display_name = "Minecraft Server Service Account"
}

// VMインスタンス
resource "google_compute_instance" "minecraft" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = var.disk_size_gb
    }
  }

  network_interface {
    network = "default"
    access_config {
      // 外部IP（動的）
    }
  }

  metadata_startup_script = file("${path.module}/startup.sh")

  service_account {
    email  = google_service_account.minecraft_sa.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }

  tags = ["minecraft-server"]
}

// ファイアウォール（25565ポート開放）
resource "google_compute_firewall" "minecraft" {
  name    = "allow-minecraft"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["25565"]
  }
  allow {
    protocol = "udp"
    ports    = ["25565"]
  }

  target_tags = ["minecraft-server"]
  source_ranges = ["0.0.0.0/0"]
}

// Cloud Function用サービスアカウント
resource "google_service_account" "function_sa" {
  account_id   = "minecraft-function-sa"
  display_name = "Minecraft Function Service Account"
}

// Cloud Functionに必要なIAMロール付与（GCE操作権限）
resource "google_project_iam_member" "function_compute_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

// Cloud Function SAにディスクスナップショット作成権限を付与
resource "google_project_iam_member" "function_compute_storage_admin" {
  project = var.project_id
  role    = "roles/compute.storageAdmin" # ディスクの読み書き、スナップショット作成権限など
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

// Cloud Functionデプロイ
resource "google_storage_bucket" "function_bucket" {
  name     = "${var.project_id}-function-bucket"
  location = var.region
  force_destroy = true
}

data "archive_file" "function_source_zip" {
  type        = "zip"
  source_dir  = "${path.module}/cloud-function/"
  output_path = "${path.module}/function-source-generated.zip"
}

resource "google_storage_bucket_object" "function_zip" {
  name   = "function-source-${data.archive_file.function_source_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name
  source = data.archive_file.function_source_zip.output_path
}

resource "google_cloudfunctions_function" "check_players" {
  name        = "check-players"
  description = "Minecraftサーバー人数チェック＆自動停止"
  runtime     = "python310"
  available_memory_mb = 256
  source_archive_bucket = google_storage_bucket.function_bucket.name
  source_archive_object = google_storage_bucket_object.function_zip.name
  entry_point = "main"
  trigger_http = true
  region = var.region
  service_account_email = google_service_account.function_sa.email
  environment_variables = {
    GCE_ZONE                 = var.zone
    GCE_INSTANCE_NAME        = var.instance_name
    GCP_PROJECT              = var.project_id
    DISCORD_BOT_WEBHOOK_URL  = "${google_cloud_run_v2_service.discord_bot_service.uri}/webhook/vm-stopped"
  }
  depends_on = [
    google_cloud_run_v2_service.discord_bot_service
  ]
}

// Cloud Schedulerジョブ（5分ごと）
resource "google_cloud_scheduler_job" "minecraft_check" {
  name             = "minecraft-check"
  description      = "5分ごとにCloud Functionを実行"
  schedule         = "*/5 * * * *"
  time_zone        = "Asia/Tokyo"
  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.check_players.https_trigger_url
  }
}

// 必要なAPIの有効化
resource "google_project_service" "compute" {
  project = var.project_id
  service = "compute.googleapis.com"
}

resource "google_project_service" "cloudfunctions" {
  project = var.project_id
  service = "cloudfunctions.googleapis.com"
}

resource "google_project_service" "cloudscheduler" {
  project = var.project_id
  service = "cloudscheduler.googleapis.com"
}

resource "google_project_service" "storage" {
  project = var.project_id
  service = "storage.googleapis.com"
}

resource "google_cloudfunctions_function_iam_member" "public_invoker" {
  project        = google_cloudfunctions_function.check_players.project
  region         = google_cloudfunctions_function.check_players.region
  cloud_function = google_cloudfunctions_function.check_players.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

output "minecraft_server_ip" {
  value = google_compute_instance.minecraft.network_interface[0].access_config[0].nat_ip
}

output "cloud_function_url" {
  value = google_cloudfunctions_function.check_players.https_trigger_url
}

// --- Discord Bot on Cloud Run ---

// Artifact Registry APIの有効化 (Cloud Buildがイメージをプッシュするために必要)
resource "google_project_service" "artifactregistry" {
  project = var.project_id
  service = "artifactregistry.googleapis.com"
}

// Cloud Build APIの有効化 (イメージビルドに必要)
resource "google_project_service" "cloudbuild" {
  project = var.project_id
  service = "cloudbuild.googleapis.com"
}

// Cloud Run APIの有効化
resource "google_project_service" "run" {
  project = var.project_id
  service = "run.googleapis.com"
}

// Dockerイメージを格納するArtifact Registryリポジトリ
resource "google_artifact_registry_repository" "discord_bot_repo" {
  project       = var.project_id
  location      = var.cloud_build_region # Cloud Runと同じリージョンが望ましい -> Cloud Buildが利用可能なリージョンに変更
  repository_id = var.artifact_registry_repository_id
  description   = "Repository for Minecraft server Discord bot images"
  format        = "DOCKER"
  depends_on = [
    google_project_service.artifactregistry
  ]
}

// Discord Bot用サービスアカウント (Cloud Run実行用)
resource "google_service_account" "discord_bot_sa" {
  account_id   = "mc-discord-bot-sa"
  display_name = "Minecraft Discord Bot Service Account"
}

// Discord Bot SAにGCEインスタンス操作権限を付与
resource "google_project_iam_member" "discord_bot_sa_compute_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.discord_bot_sa.email}"
}

// Discord Bot SAにArtifact Registryリポジトリへの書き込み権限を付与 (Cloud BuildがSAを使用する場合に必要になることがある)
// Cloud Buildが自身のデフォルトSAを使う場合はこれは不要な場合も多いが、念のため。
// resource "google_artifact_registry_repository_iam_member" "discord_bot_repo_writer" {
//   project    = google_artifact_registry_repository.discord_bot_repo.project
//   location   = google_artifact_registry_repository.discord_bot_repo.location
//   repository = google_artifact_registry_repository.discord_bot_repo.name
//   role       = "roles/artifactregistry.writer"
//   member     = "serviceAccount:${google_service_account.discord_bot_sa.email}"
// }

// null_resourceを使用してDockerイメージをビルド・プッシュする
// このリソースは、discord-botディレクトリの内容が変更された場合に再実行されるようにトリガーを設定
// (実際のファイル内容のハッシュをトリガーにするのがより堅牢)
locals {
  # discord-bot ディレクトリ内のファイル群のハッシュを計算
  # これにより、コード変更時にイメージビルドが再トリガーされる
  discord_bot_src_dir_hash = filesha256("${path.module}/discord-bot/bot.py") # 主要なファイルのみ or glob
  # 他にも requirements.txt, Dockerfile などを含めるべきだが、例として bot.py のみ
}

resource "null_resource" "build_and_push_discord_bot_image" {
  triggers = {
    # bot.pyの内容が変更されたら再ビルド (より多くのファイルを監視することが望ましい)
    bot_code_hash = local.discord_bot_src_dir_hash
    # Artifact Registryリポジトリが作成された後に実行
    repo_url = google_artifact_registry_repository.discord_bot_repo.name 
  }

  provisioner "local-exec" {
    command = <<EOT
      gcloud builds submit ${path.module}/discord-bot --region=${var.cloud_build_region} --tag ${var.cloud_build_region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.discord_bot_repo.repository_id}/${var.discord_bot_image_name}:latest --quiet
    EOT
    working_dir = path.module
    # 環境変数は親プロセスから引き継がれる想定
    # ここでGCP認証が必要。gcloud CLIが認証済みであること。
  }
  depends_on = [
    google_artifact_registry_repository.discord_bot_repo,
    google_project_service.cloudbuild # Cloud Build APIが有効になってから実行
  ]
}

// Cloud Runサービス
resource "google_cloud_run_v2_service" "discord_bot_service" {
  project  = var.project_id
  name     = "minecraft-discord-bot"
  location = var.region

  template {
    scaling {
      min_instance_count = 0 # アイドル時に0にスケールダウン (コスト削減)
      max_instance_count = 1 # Botは通常1インスタンスで十分
    }
    containers {
      image = "${var.cloud_build_region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.discord_bot_repo.repository_id}/${var.discord_bot_image_name}:latest"
      ports {
        container_port = 8080 # DockerfileでEXPOSEしたポート
      }
      env {
        name  = "DISCORD_BOT_TOKEN"
        value = var.discord_bot_token
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_ZONE"
        value = var.zone
      }
      env {
        name  = "GCP_INSTANCE_NAME"
        value = var.instance_name
      }
      env {
        name  = "DISCORD_CHANNEL_ID"
        value = var.discord_channel_id
      }
      # DISCORD_BOT_GCP_CREDENTIALS はCloud RunのSAを使うため、ここでは設定不要
    }
    service_account = google_service_account.discord_bot_sa.email
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    null_resource.build_and_push_discord_bot_image, // イメージがプッシュされた後にサービスを作成・更新
    google_project_iam_member.discord_bot_sa_compute_admin // SAの権限設定後
  ]
}

// Cloud Runサービスを誰でも呼び出せるようにする (Webhook用)
// 注意: これはBotのWebhookエンドポイントを公開します。必要に応じて認証を追加してください。
resource "google_cloud_run_v2_service_iam_member" "discord_bot_service_invoker" {
  project  = google_cloud_run_v2_service.discord_bot_service.project
  location = google_cloud_run_v2_service.discord_bot_service.location
  name     = google_cloud_run_v2_service.discord_bot_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "discord_bot_cloud_run_service_url" {
  description = "Discord Bot (Cloud Run) Service URL"
  value       = google_cloud_run_v2_service.discord_bot_service.uri
}

// --- Snapshot Rotation Function ---

data "archive_file" "delete_snapshots_function_source_zip" {
  type        = "zip"
  source_dir  = "${path.module}/cloud-function-delete-snapshots/"
  output_path = "${path.module}/delete-snapshots-function-source-generated.zip"
}

resource "google_storage_bucket_object" "delete_snapshots_function_zip" {
  name   = "delete-snapshots-function-source-${data.archive_file.delete_snapshots_function_source_zip.output_md5}.zip"
  bucket = google_storage_bucket.function_bucket.name # 既存のバケットを共用
  source = data.archive_file.delete_snapshots_function_source_zip.output_path
}

resource "google_cloudfunctions_function" "delete_old_snapshots" {
  name        = "delete-old-snapshots"
  description = "古いMinecraftサーバーのスナップショットを自動削除する"
  runtime     = "python310" # check-players と同じランタイムを使用
  available_memory_mb = 128 # 軽量な処理なのでメモリは最小限
  timeout     = 300 # タイムアウトは長めに設定 (多数のスナップショット処理を考慮)
  source_archive_bucket = google_storage_bucket.function_bucket.name
  source_archive_object = google_storage_bucket_object.delete_snapshots_function_zip.name
  entry_point = "delete_old_snapshots_http" # Pythonファイル内の関数名
  trigger_http = true # Schedulerから呼び出すためHTTPトリガー
  region = var.region
  service_account_email = google_service_account.function_sa.email # 既存のSAを共用
  environment_variables = {
    GCP_PROJECT              = var.project_id
    SNAPSHOT_PREFIX          = "${var.instance_name}-snapshot-" # check-players Functionが作成するスナップショットのプレフィックスに合わせる
    SNAPSHOT_RETENTION_COUNT = var.snapshot_retention_count
  }
}

// delete-old-snapshots Cloud Functionを誰でも呼び出せるようにする (Schedulerからの呼び出しのため)
// SchedulerがSA経由で呼び出す場合はallUsersは不要になるが、HTTPトリガーのデフォルトとして設定
// よりセキュアにするには、SchedulerのSAに明示的に起動権限を付与する
resource "google_cloudfunctions_function_iam_member" "delete_snapshots_invoker" {
  project        = google_cloudfunctions_function.delete_old_snapshots.project
  region         = google_cloudfunctions_function.delete_old_snapshots.region
  cloud_function = google_cloudfunctions_function.delete_old_snapshots.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers" # SchedulerがSAを使う場合は特定のSAに変更可能
}

// Cloud Schedulerジョブ (毎日午前3時に古いスナップショット削除を実行)
resource "google_cloud_scheduler_job" "delete_old_snapshots_job" {
  name             = "delete-old-minecraft-snapshots"
  description      = "毎日古いMinecraftサーバーのスナップショットを削除"
  schedule         = "0 3 * * *" # 毎日午前3時 (JSTを想定する場合、time_zoneもAsia/Tokyoに)
  time_zone        = "Asia/Tokyo"
  attempt_deadline = "320s"

  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.delete_old_snapshots.https_trigger_url
    // Schedulerが使用するサービスアカウントを指定し、OIDCトークンで認証するのが推奨
    // ここでは簡単のため指定しないが、本番環境では設定を推奨
    // oidc_token {
    //   service_account_email = google_service_account.cloud_scheduler_sa.email # Scheduler用のSAを別途作成・指定
    // }
  }

  depends_on = [
    google_cloudfunctions_function_iam_member.delete_snapshots_invoker
  ]
} 