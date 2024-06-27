import zmq
import logging
import time
from typing import Any, List, Tuple

class ZMQTimeout(RuntimeError):
    pass



class ZMQPublisher:
    """
    Publisher for ZMQ messages. Use send/receive pyobj to handle objects
    """

    def __init__(self, address: str = "tcp://*:5555", linger_period_ms: int = 1000):
        """
        lingering is the period AFTER close() has been called where we still
        wait around to send or receive messages. Set it to 0 to close immediately, -1
        to stick around forever (but why would you want that?)
        """
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.bind(address)

        socket.setsockopt(zmq.LINGER, linger_period_ms)
        socket.SNDTIMEO = 1000  # from original code
        # ZMQ loses first message see  https://github.com/zeromq/libzmq/issues/2267
        # so send something junk at the beginning to flush
        socket.send_string("STARTUP")
        self.socket = socket
        time.sleep(STARTUP_FLUSH_PAUSE)
        logging.info("ZMQ Client Ready")

    def send_msg(self, msg: Any):
        """
        Send a single python object as a message
        """
        self.socket.send_pyobj(msg)
        
class ZMQSubscriber:
    def __init__(
        self,
        address: str = "tcp://localhost:5555",
        topic_name: str = "",  # listen to global messages
        linger_period_ms: int = 0,
        timeout_ms: int = 1000,
    ) -> None:
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        self.default_timeout_ms = timeout_ms
        self.set_timeout()
        self.socket.setsockopt(zmq.LINGER, linger_period_ms)
        self.socket.connect(address)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, topic_name)

    def set_timeout(self, timeout_ms: int = None):
        """
        Set the timeout. If none provided, use default
        """
        if not timeout_ms:
            timeout_ms = self.default_timeout_ms
        self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)

    def get_messages(self, num_messages=1, timeout_override_ms: int = None):
        """
        Provide a generator for the messages coming in
        on the channel. If timeout_override_ms is set,
        use that, else use the default
        Usage:

        for msg in sub.get_messages(-1):
            print("Received: ", msg)
        """
        received_msgs = 0
        try:
            self.set_timeout(timeout_override_ms)
            while True:
                try:
                    data = self.socket.recv_pyobj()
                    yield data
                    if num_messages > 0:
                        received_msgs += 1
                        if received_msgs >= num_messages:
                            break
                except zmq.error.Again:
                    raise ZMQTimeout("Timeout waiting for message")
        finally:
            self.set_timeout()  # reset

    def get_message(self, timeout_override_ms: int = None):
        """Get a single message. If timeout_override_ms is set,
        use that, else use the default
        """
        return list(
            self.get_messages(num_messages=1, timeout_override_ms=timeout_override_ms)
        )[0]


STARTUP_FLUSH_PAUSE = 0.1
