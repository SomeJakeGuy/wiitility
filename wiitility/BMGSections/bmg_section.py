from io import BytesIO
from typing import Self

class BMGSection:
    """
    Base class for BMG file sections.
    Provides the interface for unpacking and repacking binary section data.
    Subclasses must override unpack_section() and repack_section() methods.
    Attributes:
        magic (str): The magic identifier for this section type.
    """
    magic: str

    def __init__(self, magic: str):
        self.magic = magic

    @classmethod
    def unpack_section(cls, raw_bytes: BytesIO) -> Self:
        """
        Unpack a section from raw bytes.
        This method must be overridden in subclasses to provide proper implementation.
        Raises AttributeError: If not properly overridden in a subclass.
        """
        raise AttributeError("Unpack section is not properly overwritten")
        return cls()
    
    def repack_section(self) -> BytesIO:
        """
        Repack a section from raw bytes.
        This method must be overridden in subclasses to provide proper implementation.
        Raises AttributeError: If not properly overridden in a subclass.
        """
        raise AttributeError("Repack section is not properly overwritten")
        return BytesIO()
