FROM hashicorp/vault

RUN apk add jq openssl

COPY ./config/ /vault/config/

RUN chmod +x /vault/config/make-p12.sh