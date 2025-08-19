{{- with secret "kafka-int-ca/issue/kafka-client" "common_name=ui" "alt_names=ui,localhost" "ip_sans=127.0.0.1" -}}
{
  "private_key": <<EOF
{{ .Data.private_key }}
EOF,
  "certificate": <<EOF
{{ .Data.certificate }}
EOF,
  "ca_chain": [
  {{- range $i, $v := .Data.ca_chain -}}
    {{- if $i }},{{ end }}
    <<EOF
{{ $v }}
EOF
  {{- end }}
  ]
}
{{- end -}}