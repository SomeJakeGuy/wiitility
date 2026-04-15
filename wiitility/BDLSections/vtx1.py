from enum import IntEnum
from io import BytesIO
from typing import NamedTuple

from wiitility import bytes_helpers as bh
from wiitility.BDLSections.bdl_section import BDLSection, PADDING

VTX1_MAGIC = "VTX1"

class AttributeType(IntEnum):
    POSITION_MATRIX = 0x0
    TEX_MATRIX_0 = 0x1
    TEX_MATRIX_1 = 0x2
    TEX_MATRIX_2 = 0x3
    TEX_MATRIX_3 = 0x4
    TEX_MATRIX_4 = 0x5
    TEX_MATRIX_5 = 0x6
    TEX_MATRIX_6 = 0x7
    TEX_MATRIX_7 = 0x8
    POSITION = 0x9
    NORMAL = 0xA
    COLOR_0 = 0xB
    COLOR_1 = 0xC
    TEX_0 = 0xD
    TEX_1 = 0xE
    TEX_2 = 0xF
    TEX_3 = 0x10
    TEX_4 = 0x11
    TEX_5 = 0x12
    TEX_6 = 0x13
    TEX_7 = 0x14
    TANGENT = 0x19
    NULL = 0xFF

class PrimitiveDataType(IntEnum):
    UNSIGNED_BYTE = 0x0
    SIGNED_BYTE = 0x1
    UNSIGNED_SHORT = 0x2
    SIGNED_SHORT = 0x3
    FLOAT = 0x4

class ColorDataType(IntEnum):
    RGB565 = 0x0
    RGB8 = 0x1
    RGBX8 = 0x2
    RGBA4 = 0x3
    RGBA6 = 0x4
    RGBA8 = 0x5

class Vec3:
    x: int | float
    y: int | float
    z: int | float

    def __init__(self, x: int | float = 0, y: int | float = 0, z: int | float = 0):
        self.x = x
        self.y = y
        self.z = z

AttributeToOffset = {
    AttributeType.POSITION: 0xC,
    AttributeType.NORMAL: 0x10,
    AttributeType.TANGENT: 0x14,
    AttributeType.COLOR_0: 0x18,
    AttributeType.COLOR_1: 0x1C,
    AttributeType.TEX_0: 0x20,
    AttributeType.TEX_1: 0x24,
    AttributeType.TEX_2: 0x28,
    AttributeType.TEX_3: 0x2C,
    AttributeType.TEX_4: 0x30,
    AttributeType.TEX_5: 0x34,
    AttributeType.TEX_6: 0x38,
    AttributeType.TEX_7: 0x3C,
}

class VertexFormat(NamedTuple):
    attribute_type: AttributeType
    component_count: int
    component_type: PrimitiveDataType | ColorDataType
    component_shift: int

class Vertex:
    vertex_format: VertexFormat
    points: list[Vec3]

    def __init__(self, vertex_format: VertexFormat, points: list[Vec3]):
        if points:
            assert isinstance(points[0], Vec3)
        else:
            points = []
        
        self.vertex_format = vertex_format
        self.points = points

class VTX1Section(BDLSection):
    vertices: list[Vertex]
    vertex_count: int

    def __init__(self, vertices: list[Vertex] = None):
        super().__init__(VTX1_MAGIC)

        if vertices:
            assert isinstance(vertices[0], Vertex)
        else:
            vertices = []
        
        self.vertices = vertices
        self.vertex_count = 0

    @classmethod
    def import_section(cls, raw_bytes: BytesIO):
        magic = bh.read_str(raw_bytes, 0x0, 4)
        assert magic == VTX1_MAGIC
        
        size = bh.read_u32(raw_bytes, 0x4)
        vertex_format_offset = bh.read_u32(raw_bytes, 0x8)
        position_data_array_offset = bh.read_u32(raw_bytes, 0xC)
        normal_data_array_offset = bh.read_u32(raw_bytes, 0x10)
        nbt_data_array_offset = bh.read_u32(raw_bytes, 0x14)
        
        color_data_array_offset = []
        for i in range(2):
            color_data_array_offset.append(bh.read_u32(raw_bytes, 0x18 + 0x4 * i))

        texcoord_data_array_offset = []
        for i in range(8):
            texcoord_data_array_offset.append(bh.read_u32(raw_bytes, 0x20 + 0x4 * i))
        
        vertex_formats: list[VertexFormat] = []

        # Read the vertex formats
        offset = vertex_format_offset
        while True:
            attribute_type = AttributeType(bh.read_u32(raw_bytes, offset + 0x0))
            component_count = bh.read_u32(raw_bytes, offset + 0x4)

            if attribute_type == AttributeType.COLOR_0 or attribute_type == AttributeType.COLOR_1:
                component_type = ColorDataType(bh.read_u32(raw_bytes, offset + 0x8))
            else:
                component_type = PrimitiveDataType(bh.read_u32(raw_bytes, offset + 0x8))
            
            component_shift = bh.read_u8(raw_bytes, offset + 0xC)

            vertex_format = VertexFormat(attribute_type, component_count, component_type, component_shift)
            vertex_formats.append(vertex_format)

            offset += 0x10

            if vertex_format.attribute_type == AttributeType.NULL:
                break
        
        # Read the vertex data
        offsets: list[int] = [position_data_array_offset, normal_data_array_offset, nbt_data_array_offset] + color_data_array_offset + texcoord_data_array_offset
        offsets = [offset for offset in offsets if offset != 0]
        
        vertices: list[Vertex] = []

        for offset, next_offset, vertex_format in zip(offsets, offsets[1:] + [size], vertex_formats[:-1]):
            points: list[Vec3] = []
            
            match vertex_format.component_type:
                case PrimitiveDataType.UNSIGNED_BYTE:
                    read_callback = bh.read_u8
                    size = 1
                case PrimitiveDataType.SIGNED_BYTE:
                    read_callback = bh.read_s8
                    size = 1
                case PrimitiveDataType.UNSIGNED_SHORT:
                    read_callback = bh.read_u16
                    size = 2
                case PrimitiveDataType.SIGNED_SHORT:
                    read_callback = bh.read_s16
                    size = 2
                case PrimitiveDataType.FLOAT:
                    read_callback = bh.read_float
                    size = 4

            while offset < next_offset:
                # Make sure we're not hitting the padding
                if offset % 0x20:
                    alignment_length = 0x20 - offset % 0x20
                    try:
                        string = bh.read_str(raw_bytes, offset, alignment_length)
                        if PADDING.startswith(string) and len(string) != 0:
                            offset = next_offset
                            continue
                    except:
                        pass
                
                x = read_callback(raw_bytes, offset) / 2 ** (size * 8 - vertex_format.component_shift)
                y = read_callback(raw_bytes, offset + size) / 2 ** (size * 8 - vertex_format.component_shift)
                z = read_callback(raw_bytes, offset + 2 * size) / 2 ** (size * 8 - vertex_format.component_shift)
                
                points.append(Vec3(x,y,z))

                offset += 3 * size
            
            vertex = Vertex(vertex_format, points)
            vertices.append(vertex)
            
        return cls(vertices)

    def export_section(self) -> BytesIO:
        data = BytesIO()
        
        # Initialise all the offsets to 0
        bh.write_u32(data, 0x8, 0)
        bh.write_u32(data, 0xC, 0)
        bh.write_u32(data, 0x10, 0)
        bh.write_u32(data, 0x14, 0)
        bh.write_u64(data, 0x18, 0)
        bh.write_u64(data, 0x20, 0)
        bh.write_u64(data, 0x28, 0)
        
        offset = 0x40
        bh.write_u32(data, 0x8, offset)
        for vertex_format in [vertex.vertex_format for vertex in self.vertices]:
            bh.write_u32(data, offset + 0x0, vertex_format.attribute_type)
            bh.write_u32(data, offset + 0x4, vertex_format.component_count)
            bh.write_u32(data, offset + 0x8, vertex_format.component_type)
            bh.write_u8(data, offset + 0xC, vertex_format.component_shift)
            bh.write_bytes(data, offset + 0xD, b'\xFF' * 3)

            offset += 0x10
        
        # Write the null vertex format
        bh.write_u32(data, offset + 0x0, AttributeType.NULL)
        bh.write_u32(data, offset + 0x4, 1)
        bh.write_u32(data, offset + 0x8, 0)
        bh.write_u8(data, offset + 0xC, 0)
        bh.write_bytes(data, offset + 0xD, b'\xFF' * 3)

        position_vertices: int = 0

        offset += 0x10
        
        for vertex in self.vertices:
            vertex_format = vertex.vertex_format
            if vertex_format.attribute_type == AttributeType.NULL:
                continue

            bh.write_u32(data, AttributeToOffset[vertex_format.attribute_type], offset)

            for point in vertex.points:
                match vertex_format.component_type:
                    case PrimitiveDataType.UNSIGNED_BYTE:
                        write_callback = bh.write_u8
                        size = 1
                        cast = int
                    case PrimitiveDataType.SIGNED_BYTE:
                        write_callback = bh.write_s8
                        size = 1
                        cast = int
                    case PrimitiveDataType.UNSIGNED_SHORT:
                        write_callback = bh.write_u16
                        size = 2
                        cast = int
                    case PrimitiveDataType.SIGNED_SHORT:
                        write_callback = bh.write_s16
                        size = 2
                        cast = int
                    case PrimitiveDataType.FLOAT:
                        write_callback = bh.write_float
                        size = 4
                        cast = float

                x = point.x * (2 ** (size * 8 - vertex_format.component_shift))
                y = point.y * (2 ** (size * 8 - vertex_format.component_shift))
                z = point.z * (2 ** (size * 8 - vertex_format.component_shift))
                
                write_callback(data, offset, cast(x))
                write_callback(data, offset + size, cast(y))
                write_callback(data, offset + 2 * size, cast(z))

                offset += 3 * size
                
            offset = bh.align(data, 0x20, PADDING)

            if vertex_format.attribute_type == AttributeType.POSITION:
                position_vertices = len(vertex.points)

        self.vertex_count = position_vertices

        return data
