import zmq

context = zmq.Context()

print("Connecting to hello world server...")
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5555")

# do 10 requests waiting each time for response 

for request in range(10):
    print("Sending request %s..." % request)
    socket.send(b'Hello')

    message = socket.recv()
    print("Recieved reply %s [ %s ]" % (request, message))
    