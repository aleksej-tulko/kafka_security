exit_after_auth = false
pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/vault/approle/kafka-client/role_id"
      secret_id_file_path = "/vault/approle/kafka-client/secret_id"
    }
  }
  sink "file" { config = { path = "/vault/token/kafka-client.token" } }
}

template {
  source      = "/vault/config/kafka-client.tpl"
  destination = "/vault/certs/kafka-client.json"
}