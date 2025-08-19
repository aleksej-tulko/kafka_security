{{ with secret "pki_int/issue/kafka-client" }}
{
  "private_key": {{ .Data.private_key | toJSON }},
  "certificate": {{ .Data.certificate | toJSON }},
  "ca_chain": {{ .Data.ca_chain | toJSON }}
}
{{ end }}