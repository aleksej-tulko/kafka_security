exit_after_auth = false
pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    mount_path = "auth/approle"
    config = {
      role_id_file_path   = "/vault/secrets/kafka-client-role_id"
      secret_id_file_path = "/vault/secrets/kafka-client-secret_id"
      remove_secret_id_file_after_reading = false
    }
  }
}

template {
  source      = "/vault/config/kafka-client.tpl"
  destination = "/vault/certs/kafka-client.json"
  perms = "0640"
  command = "sh /vault/config/make-p12.sh"
}
