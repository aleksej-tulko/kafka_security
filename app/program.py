import uuid

from confluent_kafka import Producer

if __name__ == "__main__":
    producer_conf = {
        "bootstrap.servers": "localhost:9095",
        "security.protocol": "SSL",
        "ssl.ca.location": "/opt/certs/root-ca.pem",
        "ssl.certificate.location": "/opt/certs/kafka-client.crt",
        "ssl.key.location": "/opt/certs/kafka-client.key",
    }
    producer = Producer(producer_conf)
    key = f"key-{uuid.uuid4()}"
    value = "SSL message"
    producer.produce(
        "ssl-topic",
        key=key,
        value=value,
    )
    producer.flush()
    print(f"Отправлено сообщение: {key=}, {value=}")