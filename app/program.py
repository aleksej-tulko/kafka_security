import os
import uuid
from threading import Thread
from time import sleep

from confluent_kafka import (
    Consumer, KafkaError, KafkaException, Producer
)
from dotenv import load_dotenv

load_dotenv()


ACKS_LEVEL = os.getenv('ACKS_LEVEL', 'all')
AUTOOFF_RESET = os.getenv('AUTOCOMMIT_RESET', 'earliest')
ENABLE_AUTOCOMMIT = os.getenv('ENABLE_AUTOCOMMIT', False)
FETCH_MIN_BYTES = os.getenv('FETCH_MIN_BYTES', 1)
FETCH_WAIT_MAX_MS = os.getenv('FETCH_WAIT_MAX_MS', 100)
RETRIES = os.getenv('RETRIES', '3')
SESSION_TIME_MS = os.getenv('SESSION_TIME_MS', 1_000)
LINGER_MS = os.getenv('LINGER_MS', 0)
TOPIC = os.getenv('TOPIC', 'ssl-topic')

print(TOPIC)

conf = {
    "bootstrap.servers":
    "kafka-1:9093,kafka-2:9093,kafka-3:9093",
    "security.protocol": "SSL",
    "ssl.ca.location": "/opt/certs/root-ca.pem",
    "ssl.certificate.location": "/opt/certs/kafka-client.crt",
    "ssl.key.location": "/opt/certs/kafka-client.key",
}

producer_conf = conf | {
    "acks": ACKS_LEVEL,
    "retries": RETRIES,
    "linger.ms": LINGER_MS,
    "compression.type": "lz4"
}

consumer_conf = conf | {
    "auto.offset.reset": AUTOOFF_RESET,
    "enable.auto.commit": ENABLE_AUTOCOMMIT,
    "session.timeout.ms": SESSION_TIME_MS,
    "group.id": "ssl_client",
    "fetch.min.bytes": FETCH_MIN_BYTES,
    "fetch.wait.max.ms": FETCH_WAIT_MAX_MS
}

producer = Producer(producer_conf)
consumer = Consumer(consumer_conf)


def delivery_report(err, msg) -> None:
    """Отчет о доставке."""
    if err is not None:
        print(f'Сообщение не отправлено: {err}')
    else:
        print(f'Сообщение доставлено в {msg.topic()} [{msg.partition()}]')


def create_message() -> None:
    """Сериализация сообщения и отправка в брокер."""
    producer.produce(
        topic=TOPIC,
        key="SSL Message",
        value=f"val-{uuid.uuid4()}".encode('utf-8'),
        on_delivery=delivery_report
    )


def producer_infinite_loop():
    """Запуска цикла для генерации сообщения."""
    try:
        while True:
            create_message()
            producer.flush()
    except (KafkaException, Exception) as e:
        raise KafkaError(e)
    finally:
        producer.flush()

def consume_infinite_loop(consumer: Consumer) -> None:
    """Получение сообщений из брокера по одному."""
    consumer.subscribe([TOPIC])
    try:
        while True:
            msg = consumer.poll(0.1)

            if msg is None or msg.error():
                continue

            value = msg.value().decode('utf-8')
            consumer.commit(asynchronous=False)

            print(
                f'Получено сообщение: {msg.key().decode('utf-8')}, '
                f'{value}, offset={msg.offset()}. '
                f'Размер сообщения - {len(msg.value())} байтов.'
            )

    except KafkaException as KE:
        raise KafkaError(KE)
    finally:
        consumer.close()


if __name__ == "__main__":
    producer_thread = Thread(
        target=producer_infinite_loop,
        args=(),
        daemon=True
    )
    consumer_thread = Thread(
        target=consume_infinite_loop,
        args=(consumer_conf,),
        daemon=True
    )
    producer_thread.start()
    consumer_thread.start()
    while True:
        print('Выполняется программа')
        sleep(10)
