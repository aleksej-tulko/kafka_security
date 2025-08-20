# Описание

kafka_security состоит из одного Zookeeper, хранящего метаданные кластера Apache Kafka из трех брокеров, а так же Kafka UI и программы для генерации и чтения сообщений.

### Безопасность
#### SSL
Вся информация между компонентами зашифрована протоколом SSL.

- Zookeeper при обращении к нему предъяляет сертификат сервера. При проверке сервис отдает:

```yaml
KeyUsage:
  Extended:
    - TLS Web Server Authentication
```

- Брокеры Apache Kafka выступают и как сервера для программы, и как клиенты для Zookeeper. При проверке каждый брокер отдает:

```yaml
KeyUsage:
  Extended:
    - TLS Web Server Authentication
    - TLS Web Client Authentication
```

- Клиенты Kafka UI и программа на Python предъявляют сертификат клиента:

```yaml
KeyUsage:
  Extended:
    - TLS Web Client Authentication
```

#### Аутентификация
Для аутентификации используется SASL/PLAIN.

#### Авторизация

Авторизация работает на стороне брокеров Apache Kafka:

- Kafka UI аутентифицируется как **User:ui** и имеет права на описание конфигов кластера, чтение всех топиков и описание конфигов группы.

- Producer аутентифицируется как **User:producer** и имеет права только на запись в топики topic-1 и topic-2.

- Consumer аутентифицируется как **User:consumer** и имеет права только на чтение из топика topic-1.

- Суперпользователь **kafka-server-admin** используется самими брокерами и обладает всеми привилегями. Используется для создания топиков и политик ACL.

#### Выпуск сертификатов 

Выпуск корневого, промежуточного и конечного сертификатов для компонентов осуществляется с помощью **Hashicorp Vault**.

### Работа программы по генерации и чтению сообщений

Сервис **app** является одновременно продюсером и консумером. Он пишет рандомные сообщения в топики topic-1 и topic-2, но читает только из topic-2. После запуска сервиса в стандартный вывод летят логи, что сообщение записалось в оба топика, но все сообщения были прочитаны только из одного.

### Требования

- **OS**: Linux Ubuntu 24.04 aarm
- **Python**: Python 3.12.3
- **Docker**: 28.2.2 - https://docs.docker.com/engine/install/ubuntu/


# Инструкция по запуску

1. Склонировать проект и создать папку для хранения секретов:

```bash
cd ~
git clone https://github.com/aleksej-tulko/kafka_security.git
sudo mkdir /opt/secrets/
cd kafka_security
```

2. Поднять Vault и подоготовить к работе:

```bash
sudo docker compose up vault -d
sudo docker exec -it vault vault operator init -key-shares=1 -key-threshold=1 > init.txt
sudo docker exec -it vault sh
vault operator unseal # Запросит ввести Unseal Key 1 из файла init.txt
export VAULT_TOKEN=XXXX # Подставить Initial Root Token из файла init.txt

# ПУНКТЫ 3-12 ВЫПОЛНЯТЬ В ШЕЛЛЕ VAULT!!!!
```

3. Настроить Vault для создания корневого сертификата:

```bash
vault secrets enable -path=root-ca pki || true
vault secrets tune -max-lease-ttl=87600h root-ca
vault write -field=certificate root-ca/root/generate/internal \
  common_name="Acme Root CA" ttl=87600h > /vault/certs/root-ca.pem
vault write root-ca/config/urls \
  issuing_certificates="$VAULT_ADDR/v1/root-ca/ca" \
  crl_distribution_points="$VAULT_ADDR/v1/root-ca/crl"
```

4. Настроить Vault для создания промежуточного сертификата:

```bash
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
```

5. Создать роли для выпуска конечных сертификатов:

```bash
vault write kafka-int-ca/roles/kafka-broker \
  allowed_domains="localhost,kafka-1,kafka-2,kafka-3" \
  allow_subdomains=true allow_bare_domains=true \
  allow_ip_sans=true allow_localhost=true \
  enforce_hostnames=false \
  server_flag=true client_flag=false \
  key_type="rsa" key_bits=2048 ttl="720h" max_ttl="720h" \
  key_usage="DigitalSignature,KeyEncipherment" \
  ext_key_usage="ServerAuth,ClientAuth"

vault write kafka-int-ca/roles/kafka-client \
  allowed_domains="localhost,client" \
  allow_subdomains=true allow_bare_domains=true \
  allow_ip_sans=true allow_localhost=true \
  enforce_hostnames=false \
  server_flag=false client_flag=true \
  key_type="rsa" key_bits=2048 ttl="720h" max_ttl="720h" \
  key_usage="DigitalSignature,KeyEncipherment" \
  ext_key_usage="ClientAuth"

vault write kafka-int-ca/roles/zookeeper \
  allowed_domains="localhost,zookeeper" \
  allow_subdomains=true allow_bare_domains=true \
  allow_ip_sans=true allow_localhost=true \
  enforce_hostnames=false \
  server_flag=true client_flag=false \
  key_type="rsa" key_bits=2048 ttl="720h" max_ttl="720h" \
  key_usage="DigitalSignature,KeyEncipherment" \
  ext_key_usage="ServerAuth"
```

6. Создание политик для обновления конечных сертификатов:

```bash
cd /vault # Это важно, чтобы не было проблем с правами в следующих шагах

cat > kafka-client.hcl <<EOF
path "kafka-int-ca/issue/kafka-client" {
  capabilities = ["update"]
}
EOF
vault policy write kafka-client kafka-client.hcl
vault write auth/token/roles/kafka-client allowed_policies=kafka-client period=24h

cat > kafka-broker.hcl <<EOF
path "kafka-int-ca/issue/kafka-broker" {
  capabilities = ["update"]
}
EOF
vault policy write kafka-broker kafka-broker.hcl
vault write auth/token/roles/kafka-broker allowed_policies=kafka-broker period=24h

cat > zookeeper.hcl <<EOF
path "kafka-int-ca/issue/zookeeper" {
  capabilities = ["update"]
}
EOF
vault policy write zookeeper zookeeper.hcl
vault write auth/token/roles/zookeeper allowed_policies=zookeeper period=24h
```

7. Подключить движок AppRole и настроить роли для аутентификации по токенам в файлах

```bash
vault auth enable approle

vault write auth/approle/role/kafka-client \
    secret_id_ttl=0 secret_id_num_uses=0 \
    token_ttl=1h token_max_ttl=4h \
    token_policies="kafka-client"

vault read -field=role_id auth/approle/role/kafka-client/role-id > /vault/secrets/kafka-client-role_id
vault write -field=secret_id -f auth/approle/role/kafka-client/secret-id > /vault/secrets/kafka-client-secret_id


vault write auth/approle/role/kafka-broker \
    secret_id_ttl=0 secret_id_num_uses=0 \
    token_ttl=1h token_max_ttl=4h \
    token_policies="kafka-broker"

vault read -field=role_id auth/approle/role/kafka-broker/role-id > /vault/secrets/kafka-broker-role_id
vault write -field=secret_id -f auth/approle/role/kafka-broker/secret-id > /vault/secrets/kafka-broker-secret_id

vault write auth/approle/role/zookeeper \
    secret_id_ttl=0 secret_id_num_uses=0 \
    token_ttl=1h token_max_ttl=4h \
    token_policies="zookeeper"

vault read -field=role_id auth/approle/role/zookeeper/role-id > /vault/secrets/zookeeper-role_id
vault write -field=secret_id -f auth/approle/role/zookeeper/secret-id > /vault/secrets/zookeeper-secret_id
```

8. Сгенерировать сертификат, ключ и кейстор для Zookeeper

```bash
vault write -format=json kafka-int-ca/issue/zookeeper \
  common_name="zookeeper" \
  alt_names="zookeeper,localhost" \
  ip_sans="127.0.0.1" \
  > /vault/certs/zookeeper.json

jq -r ".data.private_key"  /vault/certs/zookeeper.json > /vault/certs/zookeeper.key
jq -r ".data.certificate"  /vault/certs/zookeeper.json > /vault/certs/zookeeper.crt
jq -r ".data.ca_chain[]"   /vault/certs/zookeeper.json > /vault/certs/ca-chain.crt
chmod 600 /vault/certs/zookeeper.key

openssl pkcs12 -export \
  -inkey    /vault/certs/zookeeper.key \
  -in       /vault/certs/zookeeper.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name zookeeper \
  -out /vault/certs/zookeeper.p12 \
  -passout pass:changeit
```

9. Сгенерировать сертификат, ключ и кейстор для kafka-1

```bash
vault write -format=json kafka-int-ca/issue/kafka-broker \
  common_name="kafka-1" \
  alt_names="localhost" \
  ip_sans="127.0.0.1" \
  > /vault/certs/kafka-1.json

jq -r ".data.private_key"  /vault/certs/kafka-1.json > /vault/certs/kafka-1.key
jq -r ".data.certificate"  /vault/certs/kafka-1.json > /vault/certs/kafka-1.crt
chmod 600 /vault/certs/kafka-1.key

openssl pkcs12 -export \
  -inkey    /vault/certs/kafka-1.key \
  -in       /vault/certs/kafka-1.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name kafka-1 \
  -out /vault/certs/kafka-1.p12 \
  -passout pass:changeit
```

10. Сгенерировать сертификат, ключ и кейстор для kafka-2

```bash
vault write -format=json kafka-int-ca/issue/kafka-broker \
  common_name="kafka-2" \
  alt_names="localhost" \
  ip_sans="127.0.0.1" \
  > /vault/certs/kafka-2.json

jq -r ".data.private_key"  /vault/certs/kafka-2.json > /vault/certs/kafka-2.key
jq -r ".data.certificate"  /vault/certs/kafka-2.json > /vault/certs/kafka-2.crt
chmod 600 /vault/certs/kafka-2.key

openssl pkcs12 -export \
  -inkey    /vault/certs/kafka-2.key \
  -in       /vault/certs/kafka-2.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name kafka-2 \
  -out /vault/certs/kafka-2.p12 \
  -passout pass:changeit
```

11. Сгенерировать сертификат, ключ и кейстор для kafka-3

```bash
vault write -format=json kafka-int-ca/issue/kafka-broker \
  common_name="kafka-3" \
  alt_names="localhost" \
  ip_sans="127.0.0.1" \
  > /vault/certs/kafka-3.json

jq -r ".data.private_key"  /vault/certs/kafka-3.json > /vault/certs/kafka-3.key
jq -r ".data.certificate"  /vault/certs/kafka-3.json > /vault/certs/kafka-3.crt
chmod 600 /vault/certs/kafka-3.key

openssl pkcs12 -export \
  -inkey    /vault/certs/kafka-3.key \
  -in       /vault/certs/kafka-3.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name kafka-3 \
  -out /vault/certs/kafka-3.p12 \
  -passout pass:changeit
```

12. Сгенерировать сертификат, ключ и кейстор для клиентов

```bash
vault write -format=json kafka-int-ca/issue/kafka-client \
  common_name="client" \
  alt_names="localhost" \
  ip_sans="127.0.0.1" \
  > /vault/certs/kafka-client.json

jq -r ".data.private_key"   /vault/certs/kafka-client.json > /vault/certs/kafka-client.key
jq -r ".data.certificate"   /vault/certs/kafka-client.json > /vault/certs/kafka-client.crt
chmod 600 /vault/certs/kafka-client.key

openssl pkcs12 -export \
  -inkey /vault/certs/kafka-client.key \
  -in /vault/certs/kafka-client.crt \
  -certfile /vault/certs/ca-chain.crt \
  -name client \
  -passout pass:changeit \
  -out /vault/certs/kafka-client.p12
```

13. Выйти из Vault и скопировать сгенерированные сертификаты, ключи и кейсторы на хост:

```bash
sudo docker cp vault:/vault/certs/. /opt/secrets/
```

14. Собрать trustores:

```bash
cd /opt/secrets

sudo keytool -import -alias root-ca -trustcacerts \
  -file root-ca.pem \
  -keystore kafka-truststore.jks \
  -storepass changeit -noprompt

sudo keytool -import -alias kafka-int-ca -trustcacerts \
  -file kafka-int-ca.pem \
  -keystore kafka-truststore.jks \
  -storepass changeit -noprompt
```

15. Добавить файл с паролем *changeit*:

```bash
sudo vim /opt/secrets/kafka_creds
```

16. Скопировать файлы конфигурации в папку с секретами:

```bash
sudo cp ~/kafka_security/adminclient-configs.conf /opt/secrets/

sudo cp ~/kafka_security/kafka_server_jaas.conf /opt/secrets/

sudo cp ~/kafka_security/zookeeper.sasl.jaas.conf /opt/secrets/
```

17. Выставить права на всю директорию с секретами:

```bash
sudo chown 1000:1000 /opt/secrets/ -R
```

18. Вернуться в папку с проектом и создать файл с env-переменными.

```bash
cd ~/kafka_security

cat > .env <<'EOF'
ACKS_LEVEL='all'
AUTOOFF_RESET='earliest'
ENABLE_AUTOCOMMIT=False
FETCH_MIN_BYTES=400
FETCH_WAIT_MAX_MS=100
RETRIES=3
SESSION_TIME_MS=6000
TOPICS='topic-1,topic-2'
COMPRESSION_TYPE='lz4'
GROUP_ID='ssl'
EOF
```

19. Поднять Zookeeper и проверить сертификат:

```bash
sudo docker compose up zookeeper -d

openssl s_client -connect localhost:2281 -servername zookeeper -showcerts </dev/null
```

20. Полнять брокеры и проверить сертификат любого из них:

```bash
sudo docker compose up kafka-1 kafka-2 kafka-3 -d

openssl s_client -connect localhost:9095 -servername kafka-2 -showcerts </dev/null
```

21. Настроить ACLs и создать топики

```bash
sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:producer \
  --operation Write --topic topic-1 \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:producer \
  --operation Write --topic topic-2 \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:consumer \
  --operation Read --topic topic-1 \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:consumer \
  --operation Read --group ssl \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:consumer \
  --operation Describe --group ssl \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:ui \
  --operation Read --topic '*' \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:ui \
  --operation Describe --group '*' \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:ui \
  --operation Describe --cluster \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-acls \
  --bootstrap-server kafka-1:9093 \
  --add --allow-principal User:ui \
  --operation DescribeConfigs --cluster \
  --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-topics \
  --create --topic topic-1 --partitions 1 \
  --replication-factor 2   --bootstrap-server \
  kafka-1:9093 --command-config /etc/kafka/secrets/adminclient-configs.conf

sudo docker compose exec -it kafka-1 kafka-topics \
  --create --topic topic-2 --partitions 1 \
  --replication-factor 2   --bootstrap-server \
  kafka-1:9093 --command-config /etc/kafka/secrets/adminclient-configs.conf
```

22. Поднять Kafka UI:

```bash
sudo docker compose up ui -d
```

23. Запустить приложение **app**

```bash
sudo docker compose up app
```

24. Обновить клиентский сертификат

Есть роли и политики для обновления любого серта, но для теста хватит обновления клиентского сертификата.

```bash
sudo docker compose down ui # Остановка Kafka UI, который отправляет клиентский сертификат брокерам

sudo docker compose up kafka-client-vault-agent # Агент выполнит скрипт, который пересоздаст сертификат. Надо дождаться вывода сообщения 'Updated kafka-client.p12'.По завершении можно просто удалить это сервис

sudo docker cp vault:/vault/certs/kafka-client.p12 ./ # Извлечь обновленный серт на хост

sudo openssl pkcs12 -in kafka-client.p12 -clcerts -nokeys -nodes > check_cert && cat check_cert | openssl x509 -noout -dates -subject -issuer # Проверка, что срок действия сертификата изменился. Запроси пароль, который 'changeit'

sudo chown 1000:1000 kafka-client.p12

sudo mv kafka-client.p12 /opt/secrets/

sudo docker compose up ui -d # Kafka UI уже запустится и подключится к брокерам с новым сертфиикатом
```

## Автор
[Aliaksei Tulko](https://github.com/aleksej-tulko)