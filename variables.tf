variable "project_id" {
  description = "GCPのプロジェクトID"
  type        = string
}

variable "region" {
  description = "GCPリージョン"
  type        = string
  default     = "asia-northeast1"
}

variable "zone" {
  description = "GCPゾーン"
  type        = string
  default     = "asia-northeast1-b"
}

variable "instance_name" {
  description = "Minecraftサーバーのインスタンス名"
  type        = string
  default     = "minecraft-server"
}

variable "machine_type" {
  description = "GCEインスタンスタイプ"
  type        = string
  default     = "e2-small"
}

variable "disk_size_gb" {
  description = "ブートディスクサイズ(GB)"
  type        = number
  default     = 20
}

// Discord Bot 用の変数
variable "discord_bot_token" {
  description = "Discord Botのトークン"
  type        = string
  sensitive   = true # 機密情報として扱う
}

variable "discord_channel_id" {
  description = "Discord Botが通知やコマンドをやり取りするチャンネルのID"
  type        = string # 数値だが、環境変数としては文字列で渡すことが多い
}

variable "discord_bot_image_name" {
  description = "Discord BotのDockerイメージ名"
  type        = string
  default     = "discord-bot"
}

variable "artifact_registry_repository_id" {
  description = "Artifact RegistryのリポジトリID"
  type        = string
  default     = "minecraft-server-bots"
}

variable "cloud_build_region" {
  description = "Cloud Build と Artifact Registry を使用するGCPリージョン"
  type        = string
  default     = "us-central1" # 例としてus-central1を指定
} 