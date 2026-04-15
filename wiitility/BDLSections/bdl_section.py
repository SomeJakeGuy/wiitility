from io import BytesIO
from typing import Self

PADDING = "This is padding data to alignment"

class BDLSection:
    magic: str
    data: BytesIO
    
    def __init__(self, magic: str):
        self.magic = magic

    @classmethod
    def import_section(cls, raw_bytes: BytesIO) -> Self:
        """
        Import a section from raw bytes.
        This method must be overridden in subclasses to provide proper implementation.
        Raises AttributeError: If not properly overridden in a subclass.
        """
        raise AttributeError("Import section is not properly overwritten")
        return cls()
    
    def export_section(self) -> BytesIO:
        """
        Export a section from raw bytes.
        This method must be overridden in subclasses to provide proper implementation.
        Raises AttributeError: If not properly overridden in a subclass.
        """
        raise AttributeError("Export section is not properly overwritten")
        return BytesIO()
