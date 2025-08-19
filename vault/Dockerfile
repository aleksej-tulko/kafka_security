FROM hashicorp/vault

RUN apk add jq openssl

RUN mkdir /vault/certs

RUN mkdir /vault/secrets

COPY ./config/ /vault/config/

RUN chown 100:1000 /vault -R

RUN chmod +x /vault/config/kafka-client-make-p12.sh