ui = true
disable_mlock = "true"

storage "file" {
  path    = "/vault/storage"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = "true"
}

api_addr = "https://0.0.0.0:8200"
