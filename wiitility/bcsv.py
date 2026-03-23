from enum import IntEnum
from io import BytesIO
from typing import NamedTuple

import wiitility.bytes_helpers as bh

BCSV_HEADER_SIZE: int = 0x10
BCSV_FIELD_SIZE: int = 0xC
BCSV_MAX_STRING_LENGTH: int = 0x20

type BCSVKey = int | str | BCSVField
type BCSVValue = int | str | float


class BCSVFileError(ValueError):
    pass


def calculate_field_hash(field_name: str) -> int:
    """
    Field names are stored internally in RAM/Wii games as hashes, as they are faster lookup tables. So, we will
    calculate the hast and the resulting hash is a 32-bit value. The field name is expected to be an ASCII-string.
    """
    field_hash: int = 0

    for ch in field_name.encode("ascii"):
        if ch == b"\x00":
            break
        ch = ch - 256 if ch >= 128 else ch
        field_hash = (field_hash * 0x1F) + ch

    return field_hash & 0xFFFFFFFF


class BCSVType(IntEnum):
    """
    Indicates the type of data that will be stored in each field type.
    Strings are deprecated and should use of type STRING_OFFSET instead.
    Longs, Short, and Byte should all AND the read value with the field's bitmask and then
        shift the result by the field's shift amount.
    LONG and LONG_2 are 32-bit signed integers
    FLOAT are 32-bit
    Short are 16-bit signed integers
    BYTE is single char/8-bit integers.
    Floats are read and written as is.
    String_Offset return the offset from the start of the string pool table where the string can be found.
    """
    LONG = 0 # 32-bit integer. Signedness is not specified.
    STRING = 1 # Embedded string. Deprecated.
    FLOAT = 2 # Single-precision floating-point value.
    LONG_2 = 3 # 32-bit integer.
    SHORT = 4 # 16-bit integer.
    BYTE = 5 # Single character as 8bit integer.
    STRING_OFFSET = 6 # 32-bit offset into string table.


class BCSVTypeSize(IntEnum):
    """Returns the size of the field based on its BCSVType."""
    WORD = 4
    HALF_WORD = 2
    BYTE = 1
    STRING = 32


class StringPoolElement(NamedTuple):
    value: str
    offset: int


class BCSVField:
    """
    Represents a singular field of data in a BCSV file. Similar to a column in a data table.
    Fields are indexed by hashes and its named are defaulted to its hash stringified, however a
        field_hash->name converter function is provided.

    BCSV File Headers are comprised of 12 bytes in total.
    The first 4 bytes represent the field's hash. Currently, it is unknown how a field's name becomes a hash.
    The second 4 bytes represent the field's bitmask.
    The next 2 bytes represent the starting byte for the field within a given data line in the BCSV file.
    The second to last byte represents shift amount used on the field's value.
    The last byte represents the data type, see BCSVType for value -> type conversion.
    """
    field_hash: int = 0
    field_name: str = None
    field_bitmask: int = 0
    field_offset: int = 0
    field_shift: int = 0
    field_type: BCSVType = None


    def __init__(self, field_hash: int, field_bitmask: int, field_offset: int, data_shift: int, data_type: int):
        self.field_hash = field_hash
        self.field_name = str(self.field_hash)
        self.field_bitmask = field_bitmask
        self.field_offset = field_offset
        self.field_shift = data_shift
        self.field_type = BCSVType(data_type)


    @classmethod
    def import_field(cls, raw_bytes: BytesIO):
        field_hash: int = bh.read_u32(raw_bytes, 0x0)
        field_bitmask: int = bh.read_u32(raw_bytes, 0x4)
        field_offset: int = bh.read_u16(raw_bytes, 0x8)
        field_shift: int = bh.read_u8(raw_bytes, 0xA)
        field_type: int = bh.read_u8(raw_bytes, 0xB)
        return cls(field_hash, field_bitmask, field_offset, field_shift, field_type)


    def export_field(self) -> bytes:
        field_bytes: BytesIO = BytesIO()
        bh.write_u32(field_bytes, 0x0, self.field_hash)
        bh.write_u32(field_bytes, 0x4, self.field_bitmask)
        bh.write_u16(field_bytes, 0x8, self.field_offset)
        bh.write_u8(field_bytes, 0xA, self.field_shift)
        bh.write_u8(field_bytes, 0xB, self.field_type)
        return field_bytes.getvalue()


    def get_value_from_bytes(self, entry_bytes: BytesIO) -> BCSVValue | None:
        value: int | None = None
        match self.field_type:
            case BCSVType.LONG | BCSVType.LONG_2:
                value = bh.read_s32(entry_bytes, self.field_offset)
            case BCSVType.SHORT:
                value = bh.read_s16(entry_bytes, self.field_offset)
            case BCSVType.BYTE:
                value = bh.read_s8(entry_bytes, self.field_offset)
            case BCSVType.FLOAT:
                return bh.read_float(entry_bytes, self.field_offset)
            case BCSVType.STRING_OFFSET:
                return bh.read_u32(entry_bytes, self.field_offset)
            case BCSVType.STRING:
                return bh.read_str(entry_bytes, self.field_offset, BCSV_MAX_STRING_LENGTH)
            case _:
                raise TypeError(f"Unsupported BCSV Field type: {self.field_type}")

        return (value & self.field_bitmask) >> self.field_shift


    def set_value_in_buffer(self, entry_bytes: BytesIO, entry_value: BCSVValue, string_pool: list[StringPoolElement]):
        match self.field_type:
            case BCSVType.LONG | BCSVType.LONG_2:
                value: int = bh.read_s32(entry_bytes, self.field_offset)
                value |= (int(entry_value) << int(self.field_shift)) & int(self.field_bitmask)
                bh.write_s32(entry_bytes, self.field_offset, value)
            case BCSVType.SHORT:
                value: int = bh.read_s16(entry_bytes, self.field_offset)
                value |= (int(entry_value) << int(self.field_shift)) & int(self.field_bitmask)
                bh.write_s16(entry_bytes, self.field_offset, value)
            case BCSVType.BYTE:
                value: int = bh.read_s8(entry_bytes, self.field_offset)
                value |= (int(entry_value) << int(self.field_shift)) & int(self.field_bitmask)
                bh.write_s8(entry_bytes, self.field_offset, value)
            case BCSVType.FLOAT:
                bh.write_float(entry_bytes, self.field_offset, float(entry_value))
            case BCSVType.STRING:
                bh.write_str(entry_bytes, self.field_offset, str(entry_value), BCSVTypeSize.STRING)
            case BCSVType.STRING_OFFSET:
                value: str = str(entry_value)
                pool_element: StringPoolElement = next((element for element in string_pool if
                    element.value == value), None)
                if pool_element is None:
                    pool_offset: int = 0
                    if string_pool:
                        highest_pair: StringPoolElement = string_pool[-1]
                        # + 1 because null byte terminated
                        pool_offset: int = highest_pair.offset + len(highest_pair.value) + 1

                    pool_element = StringPoolElement(value, pool_offset)
                    string_pool.append(pool_element)

                bh.write_s32(entry_bytes, self.field_offset, pool_element.offset)
            case _:
                raise TypeError(f"Unsupported BCSV Field type: {self.field_type}")


    def get_field_size(self):
        match self.field_type:
            case BCSVType.LONG | BCSVType.LONG_2 | BCSVType.FLOAT | BCSVType.STRING_OFFSET:
                return BCSVTypeSize.WORD
            case BCSVType.SHORT:
                return BCSVTypeSize.HALF_WORD
            case BCSVType.BYTE:
                return BCSVTypeSize.BYTE
            case BCSVType.STRING:
                return BCSVTypeSize.STRING
            case _:
                raise TypeError(f"Unsupported BCSV Field type: {self.field_type}")


class BCSVEntry(dict[BCSVKey, BCSVValue]):
    @staticmethod
    def find_field(bcsv_field: BCSVKey) -> int | None:
        """Finds a specific BCSV field by its hash value or field name. Can return None as well if no field found."""
        if isinstance(bcsv_field, int):
            return bcsv_field
        elif isinstance(bcsv_field, str):
            return calculate_field_hash(bcsv_field)
        elif isinstance(bcsv_field, BCSVField):
            return bcsv_field.field_hash
        else:
            return None


    def __getitem__(self, key: BCSVKey) -> BCSVValue:
        bcsv_hash: int = BCSVEntry.find_field(key)
        return super().__getitem__(bcsv_hash)


    def __setitem__(self, key: BCSVKey, value: BCSVValue):
        if not isinstance(value, int | float | str):
            raise TypeError(f"Provided value {value} is not of valid types: {type(BCSVValue)}")

        bcsv_hash: int = BCSVEntry.find_field(key)
        super().__setitem__(bcsv_hash, value)


class BCSV:
    """
    BCSV Files are table-structured format files that contain a giant header block and data entry block.
    These files remark a similar structure to modern day data tables, with one key difference
        The header block contains the definition of all field headers (columns) and field data
            Definition of these headers does not matter.
        The data block contains the table row data one line at a time. Each row is represented as a single list index,
            where a dictionary maps the key (column) to the value.
        And lastly, all strings are defined in a string table that is appended at the end of the data itself.
    BCSV Files also start with 16 bytes that are useful to explain the rest of the structure of the file.
    """
    fields: list[BCSVField]
    entries: list[BCSVEntry]


    def __init__(self, fields: list[BCSVField] = None, entries: list[BCSVEntry] = None):
        if fields is None:
            fields = []

        if entries is None:
            entries = []

        self.fields = fields
        self.entries = entries


    @classmethod
    def import_bcsv(cls, raw_data: BytesIO, field_names: dict[int, str] = None):
        data_length: int = raw_data.seek(0, 2)
        if data_length < BCSV_HEADER_SIZE:
            raise BCSVFileError("Provided BCSV BytesIO is not in a valid format.")

        if field_names is None:
            field_names = {}

        bcsv: BCSV = cls() # initialize the class with some empty entry/field lists.
        entry_count: int = bh.read_u32(raw_data, 0x0)
        field_count: int = bh.read_u32(raw_data, 0x4)
        entry_data_offset: int = bh.read_u32(raw_data, 0x8)
        entry_size_bytes: int = bh.read_u32(raw_data, 0xC)

        # Load all headers of this file
        fields_size: int = entry_data_offset - BCSV_HEADER_SIZE # BCSV Field details start after the above 16 bytes
        remainder_bytes: int = fields_size % BCSV_FIELD_SIZE
        read_field_count: int = int(fields_size / BCSV_FIELD_SIZE)
        if remainder_bytes != 0 or not read_field_count == field_count:
            raise BCSVFileError("When trying to read the fields block of the BCSV file, field block has an "
                f"incorrect size.\nExpected field count: {field_count}\nExpected Byte count: {fields_size}\n"
                f"Remainder Bytes: {remainder_bytes}\nAmount of fields found: {read_field_count}")

        # Load all data entries / rows of this table.
        calc_data_size: int = entry_data_offset + (entry_size_bytes * entry_count)
        if calc_data_size > data_length:
            raise BCSVFileError("When trying to read the data entries block of the BCSV file, the entry size "
                f"was incorrect.\nExpected data size: {data_length}\nCalculated data size: {calc_data_size}")

        offset: int = BCSV_HEADER_SIZE
        for field_index in range(field_count):
            field_bytes: BytesIO = BytesIO(bh.read_bytes(raw_data, offset, BCSV_FIELD_SIZE))
            bcsv_field: BCSVField = BCSVField.import_field(field_bytes)
            if bcsv_field.field_hash in field_names:
                bcsv_field.field_name = field_names[bcsv_field.field_hash]
            bcsv.fields.append(bcsv_field)
            offset += BCSV_FIELD_SIZE

        # Read everything after the calculated data size until the end of the BCSV byte data.
        string_table_bytes: BytesIO = BytesIO(bh.read_bytes(raw_data, calc_data_size))

        offset = entry_data_offset
        for entry_index in range(entry_count):
            bcsv_entry: BCSVEntry = BCSVEntry()
            entry_bytes: BytesIO = BytesIO(bh.read_bytes(raw_data, offset, entry_size_bytes))

            for bcsv_field in bcsv.fields:
                value: BCSVValue = bcsv_field.get_value_from_bytes(entry_bytes)
                if bcsv_field.field_type == BCSVType.STRING_OFFSET:
                    value = bh.read_str(string_table_bytes, value) # Read until a null byte is hit
                bcsv_entry[bcsv_field] = value
            bcsv.entries.append(bcsv_entry)
            offset += entry_size_bytes

        return bcsv


    def export_bcsv(self) -> BytesIO:
        field_count: int = len(self.fields)
        entry_count: int = len(self.entries)
        entry_data_offset: int  = BCSV_HEADER_SIZE + (BCSV_FIELD_SIZE * field_count)
        entry_size: int = self.calculate_data_entry_size()

        bcsv_data: BytesIO = BytesIO()
        bh.write_u32(bcsv_data, 0x0, entry_count)
        bh.write_u32(bcsv_data, 0x4, field_count)
        bh.write_u32(bcsv_data, 0x8, entry_data_offset)
        bh.write_u32(bcsv_data, 0xC, entry_size)

        # Write the header data back into the bcsv file
        offset = BCSV_HEADER_SIZE
        for field in self.fields:
            if not isinstance(field, BCSVField):
                raise TypeError(f"Field provided is not of type 'BCSVField'.\nReceived field type: {type(field)}\n"
                    f"Field: {field}\nField Index: {self.fields.index(field)}")
            bh.write_bytes(bcsv_data, offset, field.export_field())
            offset += BCSV_FIELD_SIZE

        # Now write the entries back into the bcsv file
        # String pool will contain a list
        string_pool: list[StringPoolElement] = []
        for entry in self.entries:
            if not isinstance(entry, BCSVEntry):
                raise TypeError(f"Entry provided is not of type 'BCSVEntry'.\nReceived entry type: {type(entry)}\n"
                    f"Entry: {entry}\nEntry Index: {self.entries.index(entry)}")

            entry_bytes: BytesIO = BytesIO(bytearray(entry_size))
            # Loop through all fields to write into the bcsv for each entry
            for field in entry.keys():
                field.set_value_in_buffer(entry_bytes, entry[field], string_pool)

            # Update the entry bytes into the BCSV data object.
            bh.write_bytes(bcsv_data, offset, entry_bytes.getvalue())
            offset += entry_size

        # Create an empty string pool to write data to and eventually append to the end.
        string_pool_bytes: BytesIO = BytesIO()
        for pool_element in string_pool:
            bh.write_str(string_pool_bytes, pool_element.offset, pool_element.value, len(pool_element.value) + 1)

        # Add the string pool bytes into BCSV data.
        bh.write_bytes(bcsv_data, offset, string_pool_bytes.getvalue())
        return bcsv_data


    def calculate_data_entry_size(self) -> int:
        """
        Calculates the size of the entry based on the field's data type.
        Order of the entry size calculation is the following:
            STRING < FLOAT < LONG < LONG_2 < SHORT < BYTE < STRING_OFFSET
        """
        return max([field.field_offset + field.get_field_size() for field in self.fields])


    def add_bcsv_field(self, bcsv_field: BCSVField, default_value: BCSVValue):
        """Adds a new BCSVField and a default value to all existing data entries."""
        if bcsv_field.field_hash in [field.field_hash for field in self.fields]:
            raise BCSVFileError(f"BCSVField with hash '{bcsv_field.field_hash}' already exists as a field.")

        self.fields.append(bcsv_field)
        for data_entry in self.entries:
            data_entry[bcsv_field] = default_value


    def remove_bcsv_field(self, key: BCSVKey):
        if isinstance(key, str):
            field_found: BCSVField = next((field for field in self.fields if field.field_name == key), None)
        elif isinstance(key, int):
            field_found: BCSVField = next((field for field in self.fields if field.field_hash == key), None)
        elif isinstance(key, BCSVField):
            field_found: BCSVField = next((field for field in self.fields if field == key), None)
        else:
            raise TypeError(f"Field provided is not of type '{type(BCSVKey)}.' Field Provided: {type(key)}")

        if field_found is None:
            raise ValueError(f"No BCSVField was with key: {key}")

        for entry in self.entries:
            del entry[key]

        self.fields.remove(key)

    def add_bcsv_entry(self, bcsv_entry: BCSVEntry):
        """Adds a new data entry using field names or hashes as keys with complete field validation."""
        if not self.fields:
            raise KeyError("Cannot add a BCSVEntry to a BCSV with no defined fields.")
        elif bcsv_entry is None or len(bcsv_entry.keys()) == 0:
            raise ValueError("Cannot add an empty BCSVEntry to the BCSV.")

        self.entries.append(bcsv_entry)


    def remove_bcsv_entry(self, bcsv_entry: int | BCSVEntry):
        """Deletes a BCSVEntry by either the Entry itself or the index number."""
        if isinstance(bcsv_entry, int):
            entry: BCSVEntry = self.entries[bcsv_entry]
        elif isinstance(bcsv_entry, BCSVEntry):
            entry: BCSVEntry = bcsv_entry
        else:
            raise ValueError(f"Cannot index BCSVEntry with value of type {type(bcsv_entry)}")

        self.entries.remove(entry)