resource "hcloud_server" "web" {
  name        = "shopflow"
  image       = "ubuntu-24.04"
  server_type = "cpx22"
  location    = "hel1"
  ssh_keys    = [hcloud_ssh_key.default.id]
}

resource "hcloud_ssh_key" "default" {
  name       = "shopflow-key"
  public_key = file(pathexpand("~/.ssh/id_ed25519.pub"))
}
