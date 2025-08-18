{{ with secret "kafka-int-ca/issue/kafka-client" "common_name=ui" "alt_names=ui,localhost" "ip_sans=127.0.0.1" }}
{{ .Data.private_key }}{{ end }}