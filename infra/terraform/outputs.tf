output "server_ip" {
  description = "Public IP of the Shopflow server"
  value       = hcloud_server.web.ipv4_address
}
