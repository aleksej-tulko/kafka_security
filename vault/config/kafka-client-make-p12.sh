#!/bin/sh
set -e

jq -r '.private_key'   /vault/certs/kafka-client.json > /vault/certs/kafka-client.key
jq -r '.certificate'   /vault/certs/kafka-client.json > /vault/certs/kafka-client.crt
jq -r '.ca_chain[]'    /vault/certs/kafka-client.json > /vault/certs/ca-chain.crt

openssl pkcs12 -export \
  -inkey    /vault/certs/kafka-client.key \
  -in       /vault/certs/kafka-client.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name ui \
  -out /vault/certs/kafka-client.p12 \
  -passout pass:changeit

echo "[make-p12.sh] Updated kafka-client.p12"