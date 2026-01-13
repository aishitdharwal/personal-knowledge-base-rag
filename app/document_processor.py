from typing import List
from app.models import DocumentChunk
from app.config import CHUNK_SIZE, CHUNK_OVERLAP

class DocumentProcessor:
    """Handles document loading and chunking"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_document(self, file_path: str) -> str:
        """Load text from a file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def chunk_text(self, text: str, doc_id: str, doc_name: str) -> List[DocumentChunk]:
        """
        Split text into fixed-size chunks with overlap
        
        Args:
            text: The text to chunk
            doc_id: Unique document identifier
            doc_name: Document filename
            
        Returns:
            List of DocumentChunk objects
        """
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size
            
            # Get the chunk text
            chunk_text = text[start:end]
            
            # Create chunk object
            chunk = DocumentChunk(
                doc_id=doc_id,
                doc_name=doc_name,
                chunk_id=chunk_id,
                text=chunk_text,
                start_char=start,
                end_char=end
            )
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            start += self.chunk_size - self.chunk_overlap
            chunk_id += 1
        
        return chunks
    
    def process_document(self, file_path: str, doc_id: str, doc_name: str) -> List[DocumentChunk]:
        """
        Complete document processing pipeline
        
        Args:
            file_path: Path to the document
            doc_id: Unique document identifier
            doc_name: Document filename
            
        Returns:
            List of processed chunks
        """
        text = self.load_document(file_path)
        chunks = self.chunk_text(text, doc_id, doc_name)
        return chunks
