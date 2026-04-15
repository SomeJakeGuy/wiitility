from enum import IntEnum
from io import BytesIO

from wiitility import bytes_helpers as bh
from wiitility.BDLSections.bdl_section import BDLSection, PADDING

INF1_MAGIC = "INF1"

class HierarchyNodeType(IntEnum):
    FINISH = 0x00
    NEW_NODE = 0x01
    END_NODE = 0x02
    JOINT = 0x10
    MATERIAL = 0x11
    SHAPE = 0x12

class HierarchyNode:
    type: HierarchyNodeType
    data: int

    def __init__(self, type: HierarchyNodeType, data: int):
        self.type = type
        self.data = data

class INF1Section(BDLSection):
    hierarchy_nodes: list[HierarchyNode]

    flags: int
    matrix_group_count: int
    vertex_count: int

    def __init__(self, hierarchy_nodes: list[HierarchyNode] = None, flags: int = 0, matrix_group_count: int = 0, vertex_count: int = 0):
        super().__init__(INF1_MAGIC)

        if hierarchy_nodes:
            assert isinstance(hierarchy_nodes[0], HierarchyNode)
        else:
            hierarchy_nodes = []
        
        self.hierarchy_nodes = hierarchy_nodes

        self.flags = flags
        self.matrix_group_count = matrix_group_count
        self.vertex_count = vertex_count

    def export_section_with_vertex_count(self, vertex_count: int) -> BytesIO:
        data = self.export_section()
        bh.write_u32(data, 0x10, vertex_count)
        return data

    @classmethod
    def import_section(cls, raw_bytes: BytesIO):
        magic = bh.read_str(raw_bytes, 0x0, 4)
        assert magic == INF1_MAGIC
        
        size = bh.read_u32(raw_bytes, 0x4)
        flags = bh.read_u16(raw_bytes, 0x8)
        # 2 bytes of padding
        matrix_group_count = bh.read_u32(raw_bytes, 0xC)
        vertex_count = bh.read_u32(raw_bytes, 0x10)
        hierarchy_data_offset = bh.read_u32(raw_bytes, 0x14)
        
        hierarchy_nodes: list[HierarchyNode] = []

        offset = hierarchy_data_offset
        while offset < size:
            node_type = bh.read_u16(raw_bytes, offset + 0x0)
            node_data = bh.read_u16(raw_bytes, offset + 0x2)

            node: HierarchyNode = HierarchyNode(node_type, node_data)
            hierarchy_nodes.append(node)
            
            if node.type == HierarchyNodeType.FINISH:
                break
            
            offset += 0x4
        
        return cls(hierarchy_nodes, flags, matrix_group_count, vertex_count)

    def export_section(self) -> BytesIO:
        data = BytesIO()

        bh.write_u16(data, 0x8, self.flags)
        bh.write_s16(data, 0xA, -1) # 2 bytes of padding

        shape_nodes: list[HierarchyNode] = [node for node in self.hierarchy_nodes
                                            if node.type == HierarchyNodeType.SHAPE]
        
        bh.write_u32(data, 0xC, len(shape_nodes))
        bh.write_u32(data, 0x10, 0) # Vertex count, written in VTX1

        hierarchy_data_offset = 0x18
        bh.write_u32(data, 0x14, hierarchy_data_offset)

        offset = hierarchy_data_offset
        for hierarchy_node in self.hierarchy_nodes:
            bh.write_u16(data, offset + 0x0, hierarchy_node.type)
            bh.write_u16(data, offset + 0x2, hierarchy_node.data)
            offset += 0x4

        return data
