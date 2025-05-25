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