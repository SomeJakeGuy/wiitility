from enum import IntEnum
from io import BytesIO

class BcsvType(IntEnum):
    long = 0 # 32-bit integer. Signedness is not specified. ANDed with the bitmask and shifted right by the field's shift amount.
    str = 1 # Embedded string. Deprecated. Use STRING_OFFSET instead.
    float = 2 # Single-precision floating-point value.
    long_2 = 3 # 32-bit integer. Signedness is not specified. ANDed with the bitmask and shifted right by the field's shift amount.
    short = 4 # 16-bit integer. Signedness is not specified. ANDed with the bitmask and shifted right by the field's shift amount.
    char = 5 # 8-bit integer. Signedness is not specified. ANDed with the bitmask and shifted right by the field's shift amount.
    string_offset = 6 # 32-bit offset into string table.

class BcsvField:
    field_hash: int = 0
    field_name: str = None
    field_bitmask: int = 0
    field_offset: int = 0
    field_data_shift: int = 0
    field_data_type: BcsvType = None

    def __init__(self, field_hash: int, field_bitmask: int, field_offset: int, field_data_shift: int, field_data_type: int):
        self.field_hash = field_hash
        self.field_name = str(self.field_hash)
        self.field_bitmask = field_bitmask
        self.field_offset = field_offset
        self.field_data_shift = field_data_shift
        self.field_data_type = BcsvType(field_data_type)

class Bcsv:
    def __init__(self, raw_data: BytesIO):
        self.header_list:list[BcsvField] = []
        self.field_list = []

        raw_data.seek(0)
        row_count = int.from_bytes(raw_data.read(4), byteorder='big')
        fields = int.from_bytes(raw_data.read(4), byteorder='big')
        data_entry_offset = int.from_bytes(raw_data.read(4), byteorder='big')
        row_size = int.from_bytes(raw_data.read(4), byteorder='big')