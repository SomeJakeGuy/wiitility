from io import BytesIO
from enum import IntEnum
from typing import NamedTuple
import wiitility.bytes_helpers as bh
from wiitility.BMGSections.bmg_section import BMGSection

DAT1_MAGIC: str = "DAT1"

class TagIdentifier(IntEnum):
    """
    Identifies when a tag/action will be used when the console displays this in game.
    This can range from delaying more text from appearing, playing a sound effect, coloring text, etc.
    """
    delay = 0x01
    sound_effect = 0x02
    load_image = 0x03
    unknown1 = 0x04
    unknown2 = 0x05
    unknown3 = 0x06
    unknown4 = 0x07
    unknown5 = 0x08
    unknown6 = 0x09
    colour_text = 0xff

class Tag:
    """
    Container object for one or more tags that will be used within a Message object.
    """
    def __init__(self,
                 offset: int,
                 size: int,
                 identifier: TagIdentifier,
                 data = None):
        
        if not isinstance(identifier, int) and not isinstance(identifier, TagIdentifier):
            raise Exception("Bad Input")
        
        self.offset: int = offset
        self.size: int = size
        self.identifier: TagIdentifier = TagIdentifier(identifier)
        self.data = data

    @classmethod
    def import_tag(self, raw_bytes: BytesIO, offset: int):
        size = int.from_bytes(raw_bytes.read(1), "big")
        identifier = int.from_bytes(raw_bytes.read(1), "big")
        data = raw_bytes.read(size - 4)

        return Tag(offset, size, identifier, data)

    def export_tag(self) -> BytesIO:
        assert isinstance(self.data, bytes)
        data = BytesIO()

        bh.write_bytes(data, 0x0, b'\x00\x1A')
        bh.write_u8(data, 0x2, self.size)
        bh.write_u8(data, 0x3, self.identifier)
        bh.write_bytes(data, 0x4, self.data)

        return data

class Message(NamedTuple):
    """
    The collection of a single or multi-lined message that will be displayed in an event, sign, message bubble, etc.
    This also contains the list of actions/tags that will occur with the given message.
    """
    string: str
    tags: list[Tag]

class DAT1Section(BMGSection):
    """
    Represents a section of DAT1 message data containing multiple messages with their associated tags.
    This class handles the serialization and deserialization of message sections encoded in a binary format
    that combines UTF-8/Shift-JIS encoded text with embedded tag markers. Messages are delimited by null
    characters and can contain formatting or metadata tags at various offsets within the string.
    Attributes:
        messages (list[Message]): A list of Message objects contained in this section.
    """
    def __init__(self, messages: list[Message] = None):
        super().__init__(DAT1_MAGIC)

        if messages == None:
            messages = []
        self.messages: list[Message] = messages
    
    def add_message(self, message: Message):
        self.messages.append(message)
    
    @classmethod
    def import_section(cls, raw_bytes: BytesIO):
        data_length = raw_bytes.seek(0, 2)
        section = cls()

        string = ''
        tags = []
        
        raw_bytes.seek(0)
        while raw_bytes.tell() < data_length:
            char_bytes = raw_bytes.read(2)
            if char_bytes == b'\x00\x1A': # Found a tag
                offset = len(string)
                tag = Tag.import_tag(raw_bytes, offset)
                tags.append(tag)
            else:
                int_value = int.from_bytes(char_bytes)
                string += chr(int_value)
            
            if char_bytes == b'\x00\x00': # Reading a null character
                message = Message(string, tags)
                section.add_message(message)
                
                string = ''
                tags = []
        
        return section
        
    def export_section(self) -> BytesIO:
        """
        Export message section by serializing messages with their tags and characters into binary data.
        Iterates through each message's characters and associated tags, writing tag data before each character
        and any closing tags at the end of the string, encoding characters in Shift-JIS format.
        """
        data = BytesIO()

        for message in self.messages:
            string = message.string
            tags = message.tags

            offset = -1
            for offset, char in enumerate(string):
                current_tags = [tag for tag in tags if tag.offset == offset]
                for tag in current_tags:
                    tag_data = tag.export_tag()
                    data.write(tag_data.getvalue())
                
                int_value = ord(char)
                char_bytes = int.to_bytes(int_value, 2, 'big')
                data.write(char_bytes)
            
            if not string:
                data.write(b'\x00\x00')

            # Since message.string does not contains the tags themselves, we must also check to see if there are tags at the end of the string
            closing_tags = [tag for tag in tags if tag.offset == offset + 1]
            for tag in closing_tags:
                tag_data = tag.export_tag()
                data.write(tag_data.getvalue())
                
        return data