from enum import IntEnum
from io import BytesIO
import bytes_helpers as bh

NODE_SIZE = 0x8
type flw_node = FLWTextNode | FLWConditionNode | FLWEventNode

class NodeType(IntEnum):
    text = 1
    condition = 2
    event = 3

class FLWTextNode:
    node_type: int = NodeType.text

    def __init__(self,
                 unknown1: int,
                 message_ID: int,
                 next_flow_ID: int,
                 validity: int,
                 unknown2: int):
        
        self.unknown1: int = unknown1
        self.message_ID: int = message_ID
        self.next_flow_ID: int = next_flow_ID
        self.validity: int = validity
        self.unknown2: int = unknown2
    
    @classmethod
    def unpack_node(cls, raw_bytes: BytesIO):
        assert raw_bytes.seek(0, 2) == NODE_SIZE

        unknown1 = bh.read_u8(raw_bytes, 0x1)
        message_ID = bh.read_u16(raw_bytes, 0x2)
        next_flow_ID = bh.read_u16(raw_bytes, 0x4)
        validity = bh.read_u8(raw_bytes, 0x6)
        unknown2 = bh.read_u8(raw_bytes, 0x7)

        return cls(unknown1, message_ID, next_flow_ID, validity, unknown2)
    
    def repack_node(self) -> BytesIO:
        data = BytesIO()

        bh.write_u8(data, 0x0, self.node_type)
        bh.write_u8(data, 0x1, self.unknown1)
        bh.write_u16(data, 0x2, self.message_ID)
        bh.write_u16(data, 0x4, self.next_flow_ID)
        bh.write_u8(data, 0x6, self.validity)
        bh.write_u8(data, 0x7, self.unknown2)

        return data

class FLWConditionNode:
    node_type: int = 2

    def __init__(self,
                 unknown1: int,
                 condition_type: int,
                 condition_argument: int,
                 branch_node_ID: int):
        
        self.unknown1: int = unknown1
        self.condition_type: int = condition_type
        self.condition_argument: int = condition_argument
        self.branch_node_ID: int = branch_node_ID
    
    @classmethod
    def unpack_node(cls, raw_bytes: BytesIO):
        assert raw_bytes.seek(0, 2) == NODE_SIZE

        unknown1 = bh.read_u8(raw_bytes, 0x1)
        condition_type = bh.read_u16(raw_bytes, 0x2)
        condition_argument = bh.read_u16(raw_bytes, 0x4)
        branch_node_ID = bh.read_u16(raw_bytes, 0x6)

        return cls(unknown1, condition_type, condition_argument, branch_node_ID)
    
    def repack_node(self) -> BytesIO:
        data = BytesIO()

        bh.write_u8(data, 0x0, self.node_type)
        bh.write_u8(data, 0x1, self.unknown1)
        bh.write_u16(data, 0x2, self.condition_type)
        bh.write_u16(data, 0x4, self.condition_argument)
        bh.write_u16(data, 0x6, self.branch_node_ID)

        return data

class FLWEventNode:
    node_type: int = NodeType.event

    def __init__(self,
                 event_type: int,
                 branch_node_ID: int,
                 event_argument: int):
        
        self.event_type: int = event_type
        self.branch_node_ID: int = branch_node_ID
        self.event_argument: int = event_argument
    
    @classmethod
    def unpack_node(cls, raw_bytes: BytesIO):
        assert raw_bytes.seek(0, 2) == NODE_SIZE

        event_type = bh.read_u8(raw_bytes, 0x1)
        branch_node_ID = bh.read_u16(raw_bytes, 0x2)
        event_argument = bh.read_u32(raw_bytes, 0x4)

        return cls(event_type, branch_node_ID, event_argument)
    
    def repack_node(self) -> BytesIO:
        data = BytesIO()

        bh.write_u8(data, 0x0, self.node_type)
        bh.write_u8(data, 0x1, self.event_type)
        bh.write_u16(data, 0x2, self.branch_node_ID)
        bh.write_u32(data, 0x4, self.event_argument)

        return data

class FLW1Section:
    """
    Represents a FLW1 (Flow) section containing flow nodes and branch nodes.
    This class handles the parsing and serialization of flow control data used in
    Wii game files. It manages a collection of flow nodes (text, condition, event)
    and branch node references.
    Attributes:
        flow_nodes (list[flw_node]): List of flow nodes in this section.
        branch_nodes (list[int]): List of branch node IDs.
    Methods:
        __init__(flow_nodes, branch_nodes): Initialize a FLW1Section with optional
            flow nodes and branch nodes.
        unpack_section(raw_bytes): Class method that deserializes a FLW1Section
            from raw binary data (BytesIO). Reads the flow node count and branch
            node count from the header, then parses each node based on its type
            (text, condition, or event). Returns a populated FLW1Section instance.
        repack_section(): Serializes the FLW1Section back into binary format (BytesIO).
            Writes the header with node counts, then serializes each flow node and
            branch node sequentially. Returns the packed data as BytesIO.
    """
    flow_nodes: list[flw_node]
    branch_nodes: list[int]

    def __init__(self, flow_nodes: list[flw_node] = [], branch_nodes: list[int] = []):
        self.flow_node_count = len(flow_nodes)
        self.branch_node_count = len(branch_nodes)

        self.flow_nodes = flow_nodes
        self.branch_nodes = branch_nodes

    @classmethod
    def unpack_section(cls, raw_bytes: BytesIO):
        section = cls()
        
        flow_node_count = bh.read_u16(raw_bytes, 0x0)
        branch_node_count = bh.read_u16(raw_bytes, 0x2)
        
        offset = 0x8
        for flow_node_index in range(flow_node_count):
            node_type = bh.read_u8(raw_bytes, offset)
            node_bytes = bh.read_bytes(raw_bytes, offset, 0x8)
            node_bytes = BytesIO(node_bytes)

            if node_type == NodeType.text:
                node = FLWTextNode.unpack_node(node_bytes)
            elif node_type == NodeType.condition:
                node = FLWConditionNode.unpack_node(node_bytes)
            elif node_type == NodeType.event:
                node = FLWEventNode.unpack_node(node_bytes)
            
            section.flow_nodes.append(node)
            offset += 0x8
        
        for branch_node_index in range(branch_node_count):
            branch_node_id = bh.read_u16(raw_bytes, offset)
            section.branch_nodes.append(branch_node_id)
            offset += 0x2
        
        return section
    
    def repack_section(self) -> BytesIO:
        data = BytesIO()

        self.flow_node_count = len(self.flow_nodes)
        self.branch_node_count = len(self.branch_nodes)

        bh.write_u16(data, 0x0, self.flow_node_count)
        bh.write_u16(data, 0x2, self.branch_node_count)
        bh.write_u32(data, 0x4, 0)

        offset = 0x8
        for flow_node in self.flow_nodes:
            flow_data = flow_node.repack_node()
            bh.write_bytes(data, offset, flow_data.getvalue())

            offset += 0x8

        for branch_node in self.branch_nodes:
            bh.write_u16(data, offset, branch_node)
            
            offset += 0x2
        
        return data