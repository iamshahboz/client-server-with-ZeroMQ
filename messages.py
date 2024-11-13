from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import IntEnum
import logging
from pydantic import BaseModel, Field
import queue
import struct
from typing import Dict, List



# A NOTE ON ENDIANNESS: THE STM SEEMS TO DEFAULT TO LITTLE-ENDIAN SO WE ARE ADHERING
# STRICTLY TO THAT HERE. IF WE NEED TO SWITCH TO BIG, just search "little" and replace
# with "big" in this file. Unit tests should pick up inconsistency

logging.basicConfig(level=logging.INFO)
NUM_BYTES_IN_HELIO_STATE = 12
NUM_HELIOS_IN_POD = 6
NUM_BYTES_IN_TIMESTAMP = 4
FC_RADIO_ADDRESS = 255
RADIO_MESSAGE_FIXED_LENGTH = 16
MESSAGE_SERIALIZE_PORT = 8880
MESSAGE_SERIALIZE_CHANNEL = f"tcp://0.0.0.0:{MESSAGE_SERIALIZE_PORT}"
zmq_command_queue = queue.Queue()

DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def datetime_to_string(dt: datetime) -> str:
    """
    Convert a datetime object with timezone information to a string.
    """
    if dt is None:
        return None
    print(f"'{dt.strftime(DATE_TIME_FORMAT)}'")
    return dt.strftime(DATE_TIME_FORMAT)


def string_to_datetime(dt_str: str) -> datetime:
    """
    Convert a string to a datetime
    """
    return datetime.strptime(dt_str, DATE_TIME_FORMAT)


def now_as_str():
    return datetime_to_string(datetime.now())


@dataclass
class HelioAngle:
    # in rads
    elev: float
    tilt: float

    def to_bytes(self) -> List[int]:
        """
        Serialize the HelioAngle object to a list of bytes.

        Returns:
            List[int]: Serialized byte list.
        """
        bytes_list = []
        bytes_list.extend(struct.pack("f", self.elev))
        bytes_list.extend(struct.pack("f", self.tilt))
        return list(bytes_list)

    @classmethod
    def from_bytes(cls, bytes_list: List[int]):
        """
        Deserialize a list of bytes into the HelioAngle object.

        Args:
            bytes_list (List[int]): Byte list to deserialize.
        """
        print(bytes_list)
        elev, tilt = struct.unpack("ff", bytes(bytes_list[:8]))
        return HelioAngle(elev, tilt)


class PodStatus(IntEnum):
    OK = 1
    SAD = 2
    ERROR = 3
    ROCKING_BACKWARDS_AND_FORWARDS_IN_A_CORNER = 4


# intenum is needed to make fastapi work. See:
# https://stackoverflow.com/questions/73178664/why-doesnt-fastapi-handle-types-derived-from-int-and-enum-correctly
class Action(IntEnum):
    TRACK = 0
    DEFOCUS = 1
    STOW = 2
    PAUSE = 3
    MOTOR_RESET = 4
    RESET_CALIBRATION = 5
    SOLVE_CALIBRATION = 6
    RESTART = 7


class HelioAngleMsg(BaseModel):
    helio_id: int
    elev_rad: float
    tilt_rad: float


class HelioMode(IntEnum):
    TRACKING = 0
    STANDBY = 1
    STOWED = 2
    MANUAL = 3


class HelioStatus(IntEnum):
    MOVING = 0
    STOPPED = 1
    STOWED = 2
    ERROR = 3


def int_to_bytes(integer: int) -> bytes:
    """
    TODO: SHould standardise this across all messages
    """
    byte1 = (integer >> 8) & 0xFF
    byte2 = integer & 0xFF
    return byte1, byte2


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


class HeartBeat(RadioMsg):
    """
    Give a millisecond-precision timestamp
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now())

    def to_bytes(self):
        """
        Timestamp is only member and stored as milliseconds uint64
        """
        # get 64 bit milliseconds
        milliseconds = int(self.timestamp.timestamp() * 1000)
        # print(f"Timestamp: {self.timestamp}, milliseconds: {milliseconds}")
        # now encode milliseconds to bytes
        bytes_value = milliseconds.to_bytes(8, byteorder="little")
        return list(bytes_value)

    @classmethod
    def from_bytes(cls, data: List[int]) -> "HeartBeat":
        """
        Timestamp is uint64
        """
        # <Q makes it little-endian. See comment above for endianness
        milliseconds = struct.unpack("<Q", bytes(data))[0]
        # print(f"Milliseconds: {milliseconds}")
        return cls(timestamp=datetime.fromtimestamp(milliseconds / 1000))


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


class ActuatorDirection(IntEnum):
    EXTEND = 0
    RETRACT = 1


class JoystickCmd(BaseModel):
    """
    Command a single heliostat to move in the specified
    direction until commanded to stop

    set direction to 1 = extend, -1 = retract, 0 = stop
    """

    helio_id: int
    elev_direction: float = 0.0
    tilt_direction: float = 0.0


class HelioTargetPoseCmd(BaseModel):
    """
    Command a single heliostat to target a particular pose in 3d space
    """

    helio_id: int
    x: float
    y: float
    z: float

    def to_bytes(self) -> List[int]:
        """
        14 bytes: id, x,y,z
        """
        bytes_list = []
        bytes_list.extend(
            self.helio_id.to_bytes(2, byteorder="little")
        )  # helioid is uint16
        bytes_list.extend(struct.pack("f", self.x))
        bytes_list.extend(struct.pack("f", self.y))
        bytes_list.extend(struct.pack("f", self.z))
        return bytes_list

    @classmethod
    def from_bytes(cls, bytes_list: List[int]):
        """
        Deserialize a list of bytes into the CalibObservation object.

        Args:
            bytes_list (List[int]): Byte list to deserialize.
        """
        offset = 0
        helio_id = int.from_bytes(bytes_list[offset : offset + 2], byteorder="little")
        offset += 2
        x = struct.unpack("f", bytes(bytes_list[offset : offset + 4]))[0]
        offset += 4
        y = struct.unpack("f", bytes(bytes_list[offset : offset + 4]))[0]
        offset += 4
        z = struct.unpack("f", bytes(bytes_list[offset : offset + 4]))[0]
        # offset += 4
        return cls(helio_id=helio_id, x=x, y=y, z=z)


class PodConfigUpdateCmd(BaseModel):
    """
    A full or partial config update. Use is_valid_partial_config()
    to validate.
    """

    pod_id: int
    config: Dict


def byte_str_to_int_list(byte_str: bytes) -> list:
    """
    I think the issue here is the ASCII encoding
    when we don't do it this very specific way we get
    issues

    Grab the bytes 2 chars at a time, and convert them
    to a base 8 int (ie, a byte)
    """
    byte_list = []
    for i in range(0, len(byte_str), 2):
        byte_int = int(byte_str[i : i + 2], 16)
        byte_list.append(byte_int)
    return byte_list


def int_list_to_bytes(int_list):
    """Converts a list of integers to a bytes object.

    Args:
        int_list: A list of integers.

    Returns:
        A bytes object containing the integers in hexadecimal format.
    """

    hex_strings = [f"{i:02x}".encode() for i in int_list]
    return b"".join(hex_strings)


def get_milliseconds_since_midnight(t: datetime) -> int:
    """
    Used for constructing radio messages
    """
    midnight = t.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_since_midnight = (t - midnight).seconds
    milliseconds_since_midnight = seconds_since_midnight * 1000 + t.microsecond // 1000
    return milliseconds_since_midnight


def time_to_bytes(t: datetime) -> List[int]:
    """
    Take only the time (not the date) part and send
    """
    milliseconds_since_midnight = get_milliseconds_since_midnight(t)
    bytes_list = [
        (milliseconds_since_midnight >> 24) & 0xFF,
        (milliseconds_since_midnight >> 16) & 0xFF,
        (milliseconds_since_midnight >> 8) & 0xFF,
        milliseconds_since_midnight & 0xFF,
    ]
    return bytes_list


def get_time_point_from_milliseconds_since_midnight(
    milliseconds_since_midnight: int,
) -> datetime:
    """
    Convert milliseconds since midnight to a datetime object representing today's date and time.

    Args:
        milliseconds_since_midnight (int): Milliseconds since midnight.

    Returns:
        datetime: Corresponding datetime object.
    """
    now = datetime.now()
    midnight = datetime.combine(now.date(), datetime.min.time())
    time_point = midnight + timedelta(milliseconds=milliseconds_since_midnight)

    # Check if the calculated time is in the future and adjust if necessary
    if time_point > now:
        time_point -= timedelta(days=1)

    return time_point


def bytes_to_time(bytes_list: List[int]) -> datetime:
    """
    Convert a list of bytes representing milliseconds since midnight to a datetime object.

    Args:
        bytes_list (List[int]): List of 4 bytes representing milliseconds since midnight.

    Returns:
        datetime: Corresponding datetime object.
    """
    milliseconds_since_midnight = (
        (bytes_list[0] << 24)
        | (bytes_list[1] << 16)
        | (bytes_list[2] << 8)
        | bytes_list[3]
    )
    print(f"{milliseconds_since_midnight=}")
    return get_time_point_from_milliseconds_since_midnight(milliseconds_since_midnight)




class CalibObservation(RadioMsg):
    """
    A single piece of calibration data for a heliostat

    spot_error_uv is in meters
    positive u means spot to right of target, positive v means spot above target
    """

    timestamp: datetime
    spot_error_u: float
    spot_error_v: float
    helio_id: int = None
    elev_tilt_rads: HelioAngle = None

    def to_bytes(self):
        """
        Convert to bytes.
        Order: timestamp, spot_error_u, spot_error_v, helio_id, elev_tilt_rads
        """
        bytes_list = []
        bytes_list.extend(time_to_bytes(self.timestamp))
        bytes_list.extend(struct.pack("f", self.spot_error_u))
        bytes_list.extend(struct.pack("f", self.spot_error_v))
        bytes_list.extend(self.helio_id.to_bytes(2, byteorder="little"))
        bytes_list.extend(self.elev_tilt_rads.to_bytes())
        return bytes_list

    @classmethod
    def from_bytes(cls, bytes_list: List[int]):
        """
        Deserialize a list of bytes into the CalibObservation object.

        Args:
            bytes_list (List[int]): Byte list to deserialize.
        """
        offset = 0
        timestamp = bytes_to_time(bytes_list[offset : offset + NUM_BYTES_IN_TIMESTAMP])
        offset += NUM_BYTES_IN_TIMESTAMP
        spot_error_u = struct.unpack("f", bytes(bytes_list[offset : offset + 4]))[0]
        offset += 4
        spot_error_v = struct.unpack("f", bytes(bytes_list[offset : offset + 4]))[0]
        offset += 4
        helio_id = int.from_bytes(bytes_list[offset : offset + 2], byteorder="little")
        offset += 2
        elev_tilt_rads = HelioAngle.from_bytes(bytes_list[offset : offset + 8])
        return cls(
            timestamp=timestamp,
            spot_error_u=spot_error_u,
            spot_error_v=spot_error_v,
            helio_id=helio_id,
            elev_tilt_rads=elev_tilt_rads,
        )


# NOTE: This MUST be kept up to date with all the messages we want to send. This provides
# the opcodes that the radio will use and STUFF WILL BREAK if you change the order.
# So add new message types at the END.
OPCODE_MAPPINGS = {
    HelioCmd: 0,
    PodConfigUpdateCmd: 3,
    CalibObservation: 4,
    HelioTargetPoseCmd: 5,
    HeartBeat: 6,
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


def break_into_packets(message: List[int]) -> List[List[int]]:
    """
    Breaks a message into packets of fixed size with sequence numbers.

    [ADDRESS][PACKET NO][TOTAL_PACKETS][DATA]
    Args:
        message (List[int]): The message to be broken into packets.

    Returns:
        List[List[int]]: list of packets
    """
    packets = []
    data_size = RADIO_MESSAGE_FIXED_LENGTH - 3
    total_packages = (len(message) + data_size - 1) // data_size

    for i in range(total_packages):
        packet = []
        sequence_number = i + 1  # COUNT FROM ONE
        packet.append(FC_RADIO_ADDRESS)
        packet.append(sequence_number)
        packet.append(total_packages)

        start_offset = i * data_size
        end_offset = min(start_offset + data_size, len(message))
        packet.extend(message[start_offset:end_offset])

        # Pad with 0s if necessary
        if len(packet) < RADIO_MESSAGE_FIXED_LENGTH:
            packet.extend([0] * (RADIO_MESSAGE_FIXED_LENGTH - len(packet)))

        packets.append(packet)

    return packets
