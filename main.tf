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
    GCE_ZONE = var.zone
    GCE_INSTANCE_NAME = var.instance_name
    GCP_PROJECT = var.project_id
  }
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