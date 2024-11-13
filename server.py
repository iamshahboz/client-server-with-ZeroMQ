import logging
from zmq_message import ZMQSubscriber
from pydantic import BaseModel 
import struct 
from enum import IntEnum



class RadioMsg(BaseModel):
    """
    Base class for all radio messages
    """

    def to_bytes(self):
        """
        Serialise the message to a list of bytes
        """
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data):
        """
        Reconstruct the message from a list of bytes
        """
        raise NotImplementedError

class Action(IntEnum):
    TRACK = 0
    DEFOCUS = 1
    STOW = 2
    PAUSE = 3
    MOTOR_RESET = 4
    RESET_CALIBRATION = 5
    SOLVE_CALIBRATION = 6
    RESTART = 7
    
def int_to_bytes(integer: int) -> bytes:
    """
    TODO: SHould standardise this across all messages
    """
    byte1 = (integer >> 8) & 0xFF
    byte2 = integer & 0xFF
    return byte1, byte2

class HelioCmd(RadioMsg):
    """
    Send a command to a single / all heliostats
    """

    helio_id: int  # todo may need to convert to uint16
    action: Action

    def to_bytes(self):
        """
        helio_id should be a 16 bit int, so we need to split
        into 2 bytes
        """
        b0, b1 = int_to_bytes(self.helio_id)
        return [b0, b1, int(self.action)]

    @classmethod
    def from_bytes(cls, data):
        """
        Reconstruct the helio_id from the 2 bytes
        """
        helio_id = (data[0] << 8) + data[1]
        action = Action(data[2])
        return cls(helio_id=helio_id, action=action)
    
OPCODE_MAPPINGS = {
    HelioCmd: 0,

}


def serialize(data: RadioMsg) -> bytes:
    """
    serialize a BaseModel instance along with an address
    SCHEME: [OPCODE][DATA_LENGTH][DATA]
    """
    msg = []
    opcode = OPCODE_MAPPINGS[type(data)]
    msg.append(opcode)
    msg_data = data.to_bytes()
    msg.append(len(msg_data))
    msg.extend(msg_data)
    return msg


def deserialize(data: bytes) -> RadioMsg:
    """
    Format: [OPCODE][DATA_LENGTH][DATA]
    """
    print("********************DESERIALISING A MESSAGE****************")
    print(f"Full message length {len(data)} bytes {data}")
    deserialized = struct.unpack("BB", bytes(data[:2]))
    opcode, length = deserialized

    print(f"{opcode=}, {length=}")
    command_bytes = data[2 : 2 + length]  # Remove the processed bytes
    print(f"Just the data component len {len(command_bytes)} {command_bytes}")
    if not command_bytes:
        raise ValueError("Empty command bytes")
    for class_type, candidate_opcode in OPCODE_MAPPINGS.items():
        if candidate_opcode == opcode:
            return class_type.from_bytes(command_bytes)

    raise ValueError(f"Unknown opcode: {opcode}")



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
        deserialized = deserialize(msg)
        logging.info(f'Coming message is {deserialized}') 

if __name__ == '__main__':
    log_serialized_message()