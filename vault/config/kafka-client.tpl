{{ with secret "kafka-int-ca/issue/kafka-client" "common_name=ui" "alt_names=ui,localhost" "ip_sans=127.0.0.1" }}
{
  "private_key": {{ .Data.private_key | toJSON }},
  "certificate": {{ .Data.certificate | toJSON }},
  "ca_chain": {{ .Data.ca_chain | toJSON }}
}
{{ end }}