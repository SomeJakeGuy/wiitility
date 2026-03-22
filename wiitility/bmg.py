from io import BytesIO

import wiitility.bytes_helpers as bh
from wiitility.BMGSections.bmg_section import BMGSection
from wiitility.BMGSections.inf1 import INF1Section
from wiitility.BMGSections.dat1 import DAT1Section
from wiitility.BMGSections.flw1 import FLW1Section
from wiitility.BMGSections.fli1 import FLI1Section

class BMG:
    """
    BMG (Binary Message Data) file handler for parsing and exporting binary message data.
    The BMG class manages the structure of BMG files which contain multiple sections
    (INF1, DAT1, FLW1, FLI1) that store message information and data.
    Attributes:
        section_count (int): Number of sections in the BMG file.
        sections (list[bmg_section]): List of parsed section objects.
        flw1_section_offset (int): Offset to the FLW1 section in the file.
        unknown (int): Unknown single byte value from file header.
    Methods:
        __init__(raw_bytes: BytesIO) -> None:
            Parses a BMG file from raw bytes. Validates magic numbers and reads
            all sections from the file.
        add_header_to_section(section: bmg_section) -> BytesIO:
            Wraps a section with its BMG header (magic and size) and applies
            32-byte alignment padding. Returns the complete section data.
        export_bmg() -> BytesIO:
            Reconstructs the complete BMG file from the current sections list.
            Rebuilds the header and all sections with proper formatting and padding.
            Returns the complete BMG file as bytes.
    """
    section_count: int
    sections: list[BMGSection]

    def __init__(self, raw_bytes: BytesIO):
        data_magic = bh.read_str(raw_bytes, 0x0, 4)
        assert data_magic == "MESG"

        file_magic = bh.read_str(raw_bytes, 0x4, 4)
        assert file_magic == "bmg1"

        self.flw1_section_offset = bh.read_u32(raw_bytes, 0x8)
        self.section_count = bh.read_u32(raw_bytes, 0xC)
        self.unknown = bh.read_u8(raw_bytes, 0x10)
        # 15 bytes of padding

        self.sections = []

        offset = 0x20
        for section in range(self.section_count):
            section_magic = bh.read_str(raw_bytes, offset, 4)
            section_size = bh.read_u32(raw_bytes, offset + 0x4) - 0x8
            offset += 8
            
            raw_bytes.seek(offset, 0)
            section_bytes = raw_bytes.read(section_size)
            section_bytes = BytesIO(section_bytes)
            
            match section_magic:
                case "INF1":
                    section = INF1Section.import_section(section_bytes)
                case "DAT1":
                    section = DAT1Section.import_section(section_bytes)
                case "FLW1":
                    section = FLW1Section.import_section(section_bytes)
                case "FLI1":
                    section = FLI1Section.import_section(section_bytes)
            
            self.sections.append(section)
            offset += section_size

    def add_header_to_section(self, section: BMGSection) -> BytesIO:
        data = BytesIO()

        section_bytes = section.export_section()
        section_size = section_bytes.seek(0, 2) + 0x8
        
        padding = 0
        if section_size % 32:
            padding = 32 - section_size % 32
            section_size += padding
        
        bh.write_str(data, 0x0, section.magic, 4)
        bh.write_u32(data, 0x4, section_size)
        bh.write_bytes(data, 0x8, section_bytes.getvalue())
        bh.write_bytes(data, section_size - padding, b'\x00' * padding)

        return data
    
    def get_section(self, section_magic: str) -> list[BMGSection]:
        out: list[BMGSection] = []

        for section in self.sections:
            if section.magic == section_magic:
                out.append(section)
        
        return out

    def export_bmg(self) -> BytesIO:
        data = BytesIO()

        bh.write_str(data, 0x0, "MESG", 4)
        bh.write_str(data, 0x4, "bmg1", 4)
        bh.write_u32(data, 0x8, 0) # Write the flw1_section_offset later
        bh.write_u32(data, 0xC, len(self.sections))
        bh.write_u8(data, 0x10, self.unknown)
        bh.write_bytes(data, 0x11, b'\x00' * 15)

        offset = 0x20
        for section in self.sections:
            if section.magic == "FLW1":
                bh.write_u32(data, 0x8, offset)
            
            section_bytes = self.add_header_to_section(section)
            bh.write_bytes(data, offset, section_bytes.getvalue())
            offset += len(section_bytes.getvalue())

        return data
