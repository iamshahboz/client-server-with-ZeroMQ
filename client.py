import logging
from pydantic import BaseModel
from zmq_message import ZMQPublisher
import time

logging.basicConfig(level=logging.INFO)

MESSAGE_SENDING_PORT = 8880
MESSAGE_SENDING_CHANNEL = f'tcp://0.0.0.0:{MESSAGE_SENDING_PORT}'

class Student(BaseModel):
    name: str
    age: int
    email: str


def run_message_publisher():
    publishing_period_secs = 1 
    publisher = ZMQPublisher(f"tcp://*:{MESSAGE_SENDING_PORT}")
    while True:
        msg = Student(
            name = 'Jack',
            age = 22,
            email= 'jacksmith@gmail.com'
        )
        logging.info(f'[SEND] {msg}')
        publisher.send_msg(msg)
        time.sleep(1)
        
if __name__ == '__main__':
    run_message_publisher()
    