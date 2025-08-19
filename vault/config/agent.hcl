exit_after_auth = false
pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/vault/secrets/role_id"
      secret_id_file_path = "/vault/secrets/secret_id"
    }
  }
}

template {
  source      = "/vault/config/kafka-client.tpl"
  destination = "/vault/certs/kafka-client.json"
  command = "sh /vault/config/make-p12.sh"
}
