import logging
from zmq_message import ZMQPublisher
import time


logging.basicConfig(level=logging.INFO)
MESSAGE_SENDING_PORT = 8880



def run_message_publisher():
    publishing_period_secs = 1 
    publisher = ZMQPublisher(f"tcp://*:{MESSAGE_SENDING_PORT}")
    while True:
        msg = "Hello World!"
        logging.info(f'[SEND] {msg}')
        publisher.send_msg(msg)
        time.sleep(publishing_period_secs)
        

if __name__ == "__main__":
    run_message_publisher()
    

    