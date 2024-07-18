import logging
from zmq_message import ZMQSubscriber



logging.basicConfig(level=logging.INFO)

INCOMING_MESSAGE_PORT = 8880
IP_TO_LISTEN_TO = '127.0.0.1'
INCOMING_MESSAGE_CHANNEL = f"tcp://{IP_TO_LISTEN_TO}:{INCOMING_MESSAGE_PORT}"


def log_serialized_message():
    """
    Action any messages coming out of zmq
    """
    receiver_subscriber = ZMQSubscriber(
        address=INCOMING_MESSAGE_CHANNEL, timeout_ms=-1, linger_period_ms=0
    )
    logging.info("Waiting for messages")
    for msg in receiver_subscriber.get_messages(-1):
        logging.info(f'Coming message is {msg}') 

if __name__ == '__main__':
    log_serialized_message()