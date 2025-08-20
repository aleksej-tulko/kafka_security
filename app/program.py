import logging
import os
import sys
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
COMPRESSION_TYPE = os.getenv('COMPRESSION_TYPE', 'lz4')
GROUP_ID = os.getenv('GROUP_ID', 'ssl')
CERTS_FOLDER = '/opt/secrets'

conf = {
    'bootstrap.servers':
    'kafka-1:9093,kafka-2:9093,kafka-3:9093',
    'security.protocol': 'SASL_PLAINTEXT',
    'ssl.ca.location': f'{CERTS_FOLDER}/root-ca.pem',
    'ssl.certificate.location': f'{CERTS_FOLDER}/kafka-client.crt',
    'ssl.key.location': f'{CERTS_FOLDER}/kafka-client.key',
    'sasl.mechanism': 'PLAIN',
}

producer_conf = conf | {
    'acks': ACKS_LEVEL,
    'retries': RETRIES,
    'linger.ms': LINGER_MS,
    'compression.type': COMPRESSION_TYPE,
    'sasl.username': 'producer',
    'sasl.password': 'producer_password',
}

consumer_conf = conf | {
    'auto.offset.reset': AUTOOFF_RESET,
    'enable.auto.commit': ENABLE_AUTOCOMMIT,
    'session.timeout.ms': SESSION_TIME_MS,
    'group.id': GROUP_ID,
    'fetch.min.bytes': FETCH_MIN_BYTES,
    'fetch.wait.max.ms': FETCH_WAIT_MAX_MS,
    'sasl.username': 'consumer',
    'sasl.password': 'consumer_password',
}

producer = Producer(producer_conf)
consumer = Consumer(consumer_conf)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class LoggerMsg:
    """Сообщения для логгирования."""

    MSG_NOT_DELIVERED = 'Ошибка доставки {err}.'
    MSG_DELIVERED = 'Сообщение доставлено в топик {topic}.'
    MSG_RECEIVED = ('Получено сообщение. Ключ - {key}, '
                    'значение - {value}, офсет - {offset}. '
                    'Размер сообщения - {size} байтов.'
                    )
    PROGRAM_RUNNING = 'Выполняется программа.'


def delivery_report(err, msg) -> None:
    """Отчет о доставке."""
    if err is not None:
        logger.error(msg=LoggerMsg.MSG_NOT_DELIVERED.format(err=err))
    else:
        logger.info(msg=LoggerMsg.MSG_DELIVERED.format(topic=msg.topic()))


def create_message(producer: Producer) -> None:
    """Сериализация сообщения и отправка в брокер."""
    producer.produce(
        topic=TOPIC,
        key='SSL Message',
        value=f'val-{uuid.uuid4()}'.encode('utf-8'),
        on_delivery=delivery_report
    )


def producer_infinite_loop(producer: Producer):
    """Запуска цикла для генерации сообщения."""
    try:
        while True:
            create_message(producer=producer)
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

            logger.debug(msg=LoggerMsg.MSG_RECEIVED.format(
                key=msg.key().decode('utf-8'), value=value,
                offset=msg.offset(), size=len(msg.value())
            ))

    except KafkaException as KE:
        raise KafkaError(KE)
    finally:
        consumer.close()


if __name__ == "__main__":
    producer_thread = Thread(
        target=producer_infinite_loop,
        args=(producer,),
        daemon=True
    )
    consumer_thread = Thread(
        target=consume_infinite_loop,
        args=(consumer,),
        daemon=True
    )
    producer_thread.start()
    consumer_thread.start()
    while True:
        logger.debug(msg=LoggerMsg.PROGRAM_RUNNING)
        sleep(10)
