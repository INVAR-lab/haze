terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {}

resource "digitalocean_ssh_key" "key" {
  name       = var.name
  public_key = var.pub_key
}

resource "digitalocean_droplet" "node" {
  name     = var.name
  image    = var.image
  size     = var.size
  region   = var.region
  ssh_keys = [digitalocean_ssh_key.key.id]
}

variable "name"    { default = "haze-node" }
variable "image"   { default = "ubuntu-22-04-x64" }
variable "size"    { default = "s-1vcpu-1gb" }
variable "region"  { default = "nyc1" }
variable "pub_key" {}

output "ip" { value = digitalocean_droplet.node.ipv4_address }
