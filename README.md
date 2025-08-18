sudo docker compose up vault -d
sudo docker exec -it vault vault operator init -key-shares=1 -key-threshold=1 > init.txt
cat init.txt
sudo docker exec -it vault sh
export VAULT_TOKEN=hvs.Hc8WsAM8QGnE38qJTcYS7c4T

#####
vault secrets enable -path=root-ca pki || true
vault secrets tune -max-lease-ttl=87600h root-ca
vault write -field=certificate root-ca/root/generate/internal \
  common_name="Acme Root CA" ttl=87600h > /vault/certs/root-ca.pem
vault write root-ca/config/urls \
  issuing_certificates="$VAULT_ADDR/v1/root-ca/ca" \
  crl_distribution_points="$VAULT_ADDR/v1/root-ca/crl"

#####
vault secrets enable -path=kafka-int-ca pki || true
vault secrets tune -max-lease-ttl=43800h kafka-int-ca

vault write -field=csr kafka-int-ca/intermediate/generate/internal \
  common_name="Acme Kafka Intermediate CA" ttl=43800h > /vault/certs/kafka-int-ca.csr

vault write -field=certificate root-ca/root/sign-intermediate \
  csr=@/vault/certs/kafka-int-ca.csr format=pem_bundle ttl=43800h > /vault/certs/kafka-int-ca.pem

vault write kafka-int-ca/intermediate/set-signed \
  certificate=@/vault/certs/kafka-int-ca.pem

vault write kafka-int-ca/config/urls \
  issuing_certificates="$VAULT_ADDR/v1/kafka-int-ca/ca" \
  crl_distribution_points="$VAULT_ADDR/v1/kafka-int-ca/crl"

#####
vault write kafka-int-ca/roles/kafka-server \
  allowed_domains="localhost,kafka,kafka-1,kafka-2,kafka-3" \
  allow_subdomains=true allow_bare_domains=true \
  allow_ip_sans=true allow_localhost=true \
  enforce_hostnames=false \
  server_flag=true client_flag=false \
  key_type="rsa" key_bits=2048 ttl="720h" max_ttl="720h" \
  key_usage="DigitalSignature,KeyEncipherment" \
  ext_key_usage="ServerAuth"

vault write kafka-int-ca/roles/kafka-client \
  allowed_domains="kafka,localhost,kafka-1,kafka-2,kafka-3" \
  allow_subdomains=true allow_bare_domains=true \
  allow_ip_sans=true allow_localhost=true \
  enforce_hostnames=false \
  server_flag=true client_flag=false \
  key_type="rsa" key_bits=2048 ttl="720h" max_ttl="720h" \
  key_usage="DigitalSignature,KeyEncipherment" \
  ext_key_usage="ClientAuth"

vault write kafka-int-ca/roles/zookeeper-server \
  allowed_domains="localhost,zookeeper" \
  allow_subdomains=true allow_bare_domains=true \
  allow_ip_sans=true allow_localhost=true \
  enforce_hostnames=false \
  server_flag=true client_flag=false \
  key_type="rsa" key_bits=2048 ttl="720h" max_ttl="720h" \
  key_usage="DigitalSignature,KeyEncipherment" \
  ext_key_usage="ServerAuth"

#####
cat > kafka-client.hcl <<EOF
path "kafka-int-ca/issue/kafka-client" {
  capabilities = ["update"]
}
EOF
vault policy write kafka-client kafka-client.hcl
vault write auth/token/roles/kafka-client allowed_policies=kafka-client period=24h

cat > kafka-server.hcl <<EOF
path "kafka-int-ca/issue/kafka-server" {
  capabilities = ["update"]
}
EOF
vault policy write kafka-server kafka-server.hcl
vault write auth/token/roles/kafka-server allowed_policies=kafka-server period=24h

cat > zookeeper-server.hcl <<EOF
path "kafka-int-ca/issue/zookeeper-server" {
  capabilities = ["update"]
}
EOF
vault policy write zookeeper-server zookeeper-server.hcl
vault write auth/token/roles/zookeeper-server allowed_policies=kafka-server period=24h

#####
apk add --no-cache openssl jq >/dev/null

vault write -format=json kafka-int-ca/issue/kafka-server \
  common_name="localhost" \
  alt_names="kafka,localhost,kafka-1,kafka-2,kafka-3" \
  ip_sans="127.0.0.1" \
  > /vault/certs/kafka.json

vault write -format=json kafka-int-ca/issue/zookeeper-server \
  common_name="localhost" \
  alt_names="localhost,zookeeper" \
  ip_sans="127.0.0.1" \
  > /vault/certs/zookeeper.json

jq -r ".data.private_key"  /vault/certs/kafka.json > /vault/certs/kafka.key
jq -r ".data.certificate"  /vault/certs/kafka.json > /vault/certs/kafka.crt
jq -r ".data.ca_chain[]"   /vault/certs/kafka.json > /vault/certs/ca-chain.crt
chmod 600 /vault/certs/kafka.key

jq -r ".data.private_key"  /vault/certs/zookeeper.json > /vault/certs/zookeeper.key
jq -r ".data.certificate"  /vault/certs/zookeeper.json > /vault/certs/zookeeper.crt
chmod 600 /vault/certs/zookeeper.key

openssl pkcs12 -export \
  -inkey    /vault/certs/kafka.key \
  -in       /vault/certs/kafka.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name kafka \
  -out /vault/certs/kafka.p12 \
  -passout pass:changeit


openssl pkcs12 -export \
  -inkey    /vault/certs/zookeeper.key \
  -in       /vault/certs/zookeeper.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name zookeeper \
  -out /vault/certs/zookeeper.p12 \
  -passout pass:changeit


#####

keytool -import -alias root-ca -trustcacerts \
  -file root-ca.pem \
  -keystore kafka-truststore.jks \
  -storepass changeit -noprompt

keytool -import -alias kafka-int-ca -trustcacerts \
  -file kafka-int-ca.pem \
  -keystore kafka-truststore.jks \
  -storepass changeit -noprompt



