## Hello world in Python
## Binds REP Socket to tcp://*:5555

# Expects b"Hello" from client, replies with b"world"

import time
import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

while True:
    # wait for the next request from the client
    message = socket.recv()
    print("Recieved request: %s" % message)

    # do some work
    time.sleep(1)

    socket.send(b'World')
    