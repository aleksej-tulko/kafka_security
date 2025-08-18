exit_after_auth = false
pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/vault/config/role_id"
      secret_id_file_path = "/vault/config/secret_id"
    }
  }

  sink "file" {
    config = {
      path = "/vault/certs/vault-token"
    }
  }
}

template {
  source      = "/vault/config/kafka-client.tpl"
  destination = "/vault/certs/kafka-client.json"
}