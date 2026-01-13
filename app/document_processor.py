from typing import List
from app.models import DocumentChunk
from app.config import CHUNK_SIZE, CHUNK_OVERLAP
import PyPDF2
import os

class DocumentProcessor:
    """Handles document loading and chunking for txt, md, and pdf files"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_document(self, file_path: str) -> str:
        """
        Load text from a file (supports txt, md, pdf)
        
        Args:
            file_path: Path to the document
            
        Returns:
            Extracted text content
        """
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return self._load_pdf(file_path)
        else:
            # Handle .txt and .md files
            return self._load_text_file(file_path)
    
    def _load_text_file(self, file_path: str) -> str:
        """Load text from txt or md file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _load_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF file using PyPDF2
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text from all pages
        """
        text = ""
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                # Extract text from each page
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    # Add page separator for better context
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page_text
                
                # Clean up the text
                text = self._clean_pdf_text(text)
                
        except Exception as e:
            raise Exception(f"Error reading PDF file: {str(e)}")
        
        return text
    
    def _clean_pdf_text(self, text: str) -> str:
        """
        Clean up extracted PDF text
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Only keep non-empty lines
                cleaned_lines.append(line)
        
        # Join lines with single newline
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Replace multiple spaces with single space
        import re
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        
        return cleaned_text
    
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
