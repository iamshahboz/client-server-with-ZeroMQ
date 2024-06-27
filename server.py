import logging
from pydantic import BaseModel
from zmq_message import ZMQSubscriber
import time

logging.basicConfig(level=logging.INFO)

MESSAGE_SENDING_PORT = 8880
MESSAGE_SENDING_CHANNEL = f'tcp://0.0.0.0:{MESSAGE_SENDING_PORT}'

def log_incoming_messages():
    subscriber = ZMQSubscriber(
        address= MESSAGE_SENDING_CHANNEL, timeout_ms=-1, linger_period_ms=0
    )
    logging.info('Waiting for messages')
    for msg in subscriber.get_message(-1):
        logging.info(f'Coming message is {msg}')
        
if __name__ == '__main__':
    log_incoming_messages()