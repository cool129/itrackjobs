terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

variable "subscription_id" {
  description = "Your Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region (close to Neon's AWS US East 2)"
  type        = string
  default     = "eastus2"
}

variable "image" {
  description = "Docker image to run"
  type        = string
  default     = "ghcr.io/cool129/itrackjobs:latest"
}

variable "api_key" {
  description = "iTrackJobs API key"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Neon Postgres connection string (postgresql+psycopg://...)"
  type        = string
  sensitive   = true
}

resource "azurerm_resource_group" "main" {
  name     = "rg-itrackjobs"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-itrackjobs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.1
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-itrackjobs"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

resource "azurerm_container_app" "api" {
  name                         = "ca-itrackjobs"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  secret {
    name  = "api-key"
    value = var.api_key
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "api"
      image  = var.image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "ITJ_API_KEY"
        secret_name = "api-key"
      }

      env {
        name        = "ITJ_DATABASE_URL"
        secret_name = "database-url"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

output "app_url" {
  value = "https://${azurerm_container_app.api.ingress[0].fqdn}"

}