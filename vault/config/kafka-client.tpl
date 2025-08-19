{{ with secret "kafka-int-ca/issue/kafka-client" "common_name=ui" "alt_names=ui,localhost" "ip_sans=127.0.0.1" }}
{
  "private_key": "{{ .Data.private_key }}",
  "certificate": "{{ .Data.certificate }}",
  "ca_chain": {{ toJSON .Data.ca_chain }}
}
{{ end }}