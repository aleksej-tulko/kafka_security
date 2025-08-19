{{- with pkiCert "kafka-int-ca/issue/kafka-client" 
      "common_name=ui" 
      "alt_names=ui,localhost" 
      "ip_sans=127.0.0.1" -}}
{
  "private_key": {{ .PrivateKey | toJSON }},
  "certificate": {{ .Certificate | toJSON }},
  "ca_chain": {{ .CAChain | toJSON }}
}
{{- end }}