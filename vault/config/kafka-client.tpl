{{- with secret "kafka-int-ca/issue/kafka-client" "common_name=ui" "alt_names=ui,localhost" "ip_sans=127.0.0.1" -}}
{{ pkcs12 "changeit" .Data.private_key .Data.certificate .Data.ca_chain }}
{{- end }}