from io import BytesIO
from enum import IntEnum
import bytes_helpers as bh

class CameraType(IntEnum):
    normal = 0
    event = 1
    none = 2

class TalkType(IntEnum):
    normal = 0
    short = 1
    event = 2
    composite = 3
    flow = 4
    null = 5

class BalloonType(IntEnum):
    normal = 0
    unknown = 1
    call = 2
    fixed = 3
    signboard = 4
    info = 5
    icon = 6

class INF1Entry:
    entry_size: int = 0xC

    def __init__(self,
                 message_data_offset: int,
                 camera_ID: int,
                 sound_ID: int,
                 camera_type: CameraType | int,
                 talk_type: TalkType | int,
                 balloon_type: BalloonType | int,
                 area_ID: int,
                 gameeventvalue_index: int):
        
        if not isinstance(camera_type, int) and not isinstance(camera_type, CameraType):
            raise Exception(f"Bad Input camera type: {camera_type}")
        if not isinstance(talk_type, int) and not isinstance(talk_type, TalkType):
            raise Exception(f"Bad Input talk type: {talk_type}")
        if not isinstance(balloon_type, int) and not isinstance(balloon_type, BalloonType):
            raise Exception(f"Bad Input balloon type: {balloon_type}")
        
        self.message_data_offset: int = message_data_offset
        self.camera_ID: int = camera_ID
        self.sound_ID: int = sound_ID
        self.camera_type: CameraType = CameraType(camera_type)
        self.talk_type: TalkType = TalkType(talk_type)
        self.balloon_type: BalloonType = BalloonType(balloon_type)
        self.area_ID: int = area_ID
        self.gameeventvalue_index: int = gameeventvalue_index

    @classmethod
    def unpack_entry(cls, raw_bytes: BytesIO | bytes):
        if isinstance(raw_bytes, bytes):
            raw_bytes = BytesIO(raw_bytes)
        
        data_length = raw_bytes.seek(0,2)
        assert data_length == cls.entry_size
        
        message_data_offset = bh.read_u32(raw_bytes, 0x0)
        camera_ID = bh.read_u16(raw_bytes, 0x4)
        sound_ID = bh.read_u8(raw_bytes, 0x6)
        camera_type = bh.read_u8(raw_bytes, 0x7)
        talk_type = bh.read_u8(raw_bytes, 0x8)
        balloon_type = bh.read_u8(raw_bytes, 0x9)
        area_ID = bh.read_u8(raw_bytes, 0xA)
        gameeventvalue_index = bh.read_u8(raw_bytes, 0xB)

        return cls(message_data_offset,
                         camera_ID,
                         sound_ID,
                         camera_type,
                         talk_type,
                         balloon_type,
                         area_ID,
                         gameeventvalue_index)

    def repack_entry(self) -> BytesIO:
        data = BytesIO()

        bh.write_u32(data, 0x0, self.message_data_offset)
        bh.write_u16(data, 0x4, self.camera_ID)
        bh.write_u8(data, 0x6, self.sound_ID)
        bh.write_u8(data, 0x7, self.camera_type)
        bh.write_u8(data, 0x8, self.talk_type)
        bh.write_u8(data, 0x9, self.balloon_type)
        bh.write_u8(data, 0xA, self.area_ID)
        bh.write_u8(data, 0xB, self.gameeventvalue_index)

        return data

class INF1Section:
    """
    Represents an INF1 section from a BMG file.
    This class manages a collection of INF1 entries and provides methods to
    pack and unpack the section data to/from binary format.
    Attributes:
        data_offset (int): The byte offset where entry data begins (0x8).
        entry_size (int): The size in bytes of each entry (0xC).
        entries (list[INF1Entry]): List of INF1Entry objects in this section.
        entry_count (int): The number of entries in this section.
    Methods:
        __init__(entries): Initialize a new INF1Section with optional entries.
        add_entry(entry): Add an INF1Entry to the section.
        unpack_section(raw_bytes): Class method to deserialize an INF1 section from raw bytes.
        repack_section(): Serialize the section back into binary format.
    """
    data_offset = 0x8
    entry_size = 0xC
    entries: list[INF1Entry]

    def __init__(self, entries: list[INF1Entry] = []):
        # Make sure list is of INF1Entry
        assert isinstance(entries, list)
        if entries:
            assert isinstance(entries[0], INF1Entry)

        self.entry_count = len(entries)
        self.entries = entries
    
    def add_entry(self, entry: INF1Entry):
        """Add an entry to the section"""
        self.entries.append(entry)
        self.entry_count = len(self.entries)

    @classmethod
    def unpack_section(cls, raw_bytes: BytesIO):
        """
        Unpacks a BMG section from raw bytes into an INF1 section object.
        raw_bytes (BytesIO): A BytesIO object containing the section data to unpack.
        """
        entry_count = bh.read_u16(raw_bytes, 0x0)
        entry_size = bh.read_u16(raw_bytes, 0x2)
        assert entry_size == cls.entry_size

        section = cls()

        for entry_index in range(entry_count):
            raw_bytes.seek(cls.data_offset + entry_index * entry_size)
            entry_bytes: bytes = raw_bytes.read(entry_size)
            entry: INF1Entry = INF1Entry.unpack_entry(entry_bytes)
            section.add_entry(entry)

        return section

    def repack_section(self) -> BytesIO:
        data = BytesIO()

        entry_count = len(self.entries)
        bh.write_u16(data, 0x0, entry_count)
        bh.write_u16(data, 0x2, self.entry_size)
        bh.write_u32(data, 0x4, 0)

        offset = 0x8
        for entry in self.entries:
            entry_data = entry.repack_entry()
            bh.write_bytes(data, offset, entry_data.getvalue())
            offset += self.entry_size
        
        return data