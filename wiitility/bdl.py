from io import BytesIO

from wiitility import bytes_helpers as bh
from wiitility.BDLSections.bdl_section import BDLSection, PADDING
from wiitility.BDLSections.inf1 import INF1Section
from wiitility.BDLSections.vtx1 import VTX1Section

class BDL:
    section_count: int
    sections: dict[str, BDLSection]

    def __init__(self, raw_bytes: BytesIO):
        data_magic = bh.read_str(raw_bytes, 0x0, 4)
        assert data_magic == "J3D2"

        file_magic = bh.read_str(raw_bytes, 0x4, 4)
        assert file_magic == "bdl4"

        self.size = bh.read_u32(raw_bytes, 0x8)
        self.section_count = bh.read_u32(raw_bytes, 0xC)
        magic = bh.read_str(raw_bytes, 0x10, 4)
        assert magic == "SVR3"
        # 12 bytes of padding

        self.sections = {}

        offset = 0x20
        for section in range(self.section_count):
            section_magic = bh.read_str(raw_bytes, offset, 4)
            section_size = bh.read_u32(raw_bytes, offset + 0x4)
            
            raw_bytes.seek(offset, 0)
            section_bytes = raw_bytes.read(section_size)
            section_data = BytesIO(section_bytes)
            
            match section_magic:
                case "INF1":
                    section = INF1Section.import_section(section_data)
                case "VTX1":
                    section = VTX1Section.import_section(section_data)
                case _:
                    section = BDLSection(section_magic)
                    section.data = section_data

            
            self.sections[section.magic] = section
            offset += section_size

    def add_header_to_section(self, section: BDLSection) -> BytesIO:
        try:
            section_data = section.export_section()
        except:
            section_data = section.data
        section_size = section_data.seek(0, 2)
        
        padding = 0
        if section_size % 32:
            padding = 32 - section_size % 32
            section_size += padding
        
        bh.write_str(section_data, 0x0, section.magic, 4)
        bh.write_u32(section_data, 0x4, section_size)
        bh.align(section_data, 0x20, PADDING)

        return section_data

    def export_bdl(self) -> BytesIO:
        data = BytesIO()

        bh.write_str(data, 0x0, "J3D2", 4)
        bh.write_str(data, 0x4, "bdl4", 4)
        bh.write_u32(data, 0x8, 0) # Write the file size later
        bh.write_u32(data, 0xC, len(self.sections.keys()))
        bh.write_str(data, 0x10, "SVR3", 4)
        bh.write_bytes(data, 0x14, b'\xff' * 12)

        vertex_count: int = 0
        vertex_count_position: int = 0

        offset = 0x20
        for magic, section in self.sections.items():
            section_data = self.add_header_to_section(section)
            section_size = section_data.seek(0, 2)

            if section.magic == "INF1":
                vertex_count_position = offset + 0x10
            elif section.magic == "VTX1":
                vertex_count = section.vertex_count

            bh.write_bytes(data, offset, section_data.getvalue())
            bh.write_str(data, offset, magic, 4)
            bh.write_u32(data, offset + 0x4, section_size)
            offset += section_size
        
        bh.write_u32(data, vertex_count_position, vertex_count)

        data_size = data.seek(0, 2)
        bh.write_u32(data, 0x8, data_size)

        return data
