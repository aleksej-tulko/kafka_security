sudo docker compose up vault -d
sudo docker exec -it vault vault operator init -key-shares=1 -key-threshold=1 > init.txt
cat init.txt
####
vault secrets enable -path root-ca pki
vault secrets tune -max-lease-ttl=8760h root-ca
vault write -field certificate root-ca/root/generate/internal common_name="Acme Root CA" ttl=8760h > /vault/certs/root-ca.pem
vault write root-ca/config/urls issuing_certificates="$VAULT_ADDR/v1/root-ca/ca" crl_distribution_points="$VAULT_ADDR/v1/root-ca/crl"
vault secrets enable -path kafka-int-ca pki
vault secrets tune -max-lease-ttl=8760h kafka-int-ca
vault write -field=csr kafka-int-ca/intermediate/generate/internal common_name="Acme Kafka Intermediate CA" ttl=43800h > /vault/certs/kafka-int-ca.csr
vault write -field=certificate root-ca/root/sign-intermediate csr=@/vault/certs/kafka-int-ca.csr format=pem_bundle ttl=43800h > /vault/certs/kafka-int-ca.pem
vault write kafka-int-ca/intermediate/set-signed certificate=@/vault/certs/kafka-int-ca.pem
vault write kafka-int-ca/config/urls issuing_certificates="$VAULT_ADDR/v1/kafka-int-ca/ca" crl_distribution_points="$VAULT_ADDR/v1/kafka-int-ca/crl"
vault write kafka-int-ca/roles/kafka-client allowed_domains=clients.kafka.acme.com allow_subdomains=true max_ttl=72h
vault write kafka-int-ca/roles/kafka-server allowed_domains=servers.kafka.acme.com allow_subdomains=true max_ttl=72h
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


sudo docker run --rm -v kafka_security_certs:/certs openjdk:17 keytool -import -alias root-ca -trustcacerts -file /certs/root-ca.pem -keystore /certs/kafka-truststore.jks     -storepass changeit -noprompt

sudo docker run --rm -v kafka_security_certs:/certs openjdk:17 keytool -import -alias kafka-int-ca -trustcacerts -file /certs/kafka-int-ca.pem -keystore /certs/kafka-truststore.jks -storepass changeit -noprompt


sudo docker exec -it vault sh
####
vault token create -role kafka-server
####
vault write -field certificate kafka-int-ca/issue/kafka-server common_name=kafka.servers.kafka.acme.com alt_names=localhost format=pem_bundle > /vault/certs/kafka.pem
apk add openssl
openssl pkcs12 -inkey /vault/certs/kafka.pem -in /vault/certs/kafka.pem -name kafka -export -out /vault/certs/kafka.p12 -passout pass:changeit
sudo docker run --rm -v kafka_security_certs:/certs openjdk:17 keytool -alias kafka -importkeystore -deststorepass changeit -destkeystore /certs/kafka-keystore.jks -srckeystore /certs/kafka.p12 -srckeypass changeit -srcstorepass changeit -srcstoretype PKCS12 -noprompt