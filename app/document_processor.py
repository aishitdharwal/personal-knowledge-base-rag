from typing import List
from app.models import DocumentChunk
from app.config import (
    CHUNK_SIZE, 
    CHUNK_OVERLAP,
    OCR_ENABLED,
    OCR_MIN_TEXT_LENGTH,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    TEXTRACT_MAX_PAGES,
    TEXTRACT_TIMEOUT
)
import PyPDF2
import os
import re

class DocumentProcessor:
    """Handles document loading and chunking for txt, md, and pdf files with OCR support"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ocr_enabled = OCR_ENABLED
        
        # Lazy load Textract client
        self.textract_available = False
        self.textract_client = None
        
        self._check_textract_availability()
    
    def _check_textract_availability(self):
        """Check if AWS Textract is available"""
        try:
            import boto3
            # Check if AWS credentials are configured (either in .env or via aws configure)
            if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                # Explicit credentials in .env
                self.textract_available = True
                print("[OCR] AWS Textract is available (using .env credentials)")
            else:
                # Try using default AWS credentials from ~/.aws/credentials
                try:
                    # Create a test session to check if credentials are available
                    session = boto3.Session()
                    credentials = session.get_credentials()
                    if credentials:
                        self.textract_available = True
                        print("[OCR] AWS Textract is available (using AWS CLI credentials)")
                    else:
                        print("[OCR] AWS Textract not configured (no credentials found)")
                except Exception as e:
                    print(f"[OCR] AWS Textract not available (credentials check failed: {str(e)})")
        except Exception:
            print("[OCR] AWS Textract not available (boto3 not installed)")
    
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
        Extract text from PDF file with OCR fallback for scanned documents
        
        Strategy:
        1. Try PyPDF2 text extraction (fast, works for text-based PDFs)
        2. If minimal text found, use AWS Textract OCR
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text from all pages
        """
        print(f"[PDF] Processing: {file_path}")
        
        # Step 1: Try standard text extraction
        try:
            text = self._extract_pdf_text(file_path)
            print(f"[PDF] Extracted {len(text.strip())} characters via PyPDF2")
        except Exception as e:
            print(f"[PDF] PyPDF2 extraction failed: {str(e)}")
            text = ""
        
        # Step 2: Check if OCR is needed
        if self.ocr_enabled and len(text.strip()) < OCR_MIN_TEXT_LENGTH:
            print(f"[OCR] Minimal text found ({len(text.strip())} chars), triggering OCR for {file_path}")
            
            if not self.textract_available:
                print(f"[OCR] AWS Textract not available. Using PyPDF2 text as fallback.")
                return self._clean_pdf_text(text)
            
            try:
                text = self._ocr_with_textract(file_path)
                print(f"[OCR] Successfully extracted {len(text.strip())} characters via AWS Textract")
            except Exception as e:
                print(f"[OCR] Textract failed: {str(e)}")
                print(f"[OCR] Using PyPDF2 extracted text as fallback")
                # Fall back to whatever text we extracted
        else:
            print(f"[PDF] Text extraction successful, OCR not needed")
        
        # Clean up the text
        text = self._clean_pdf_text(text)
        
        return text
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF using PyPDF2 (no OCR)"""
        text = ""
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    if page_text.strip():  # Only add if page has text
                        text += f"\n--- Page {page_num + 1} ---\n"
                        text += page_text
        
        except Exception as e:
            print(f"[PDF] Error extracting text: {str(e)}")
        
        return text
    
    def _ocr_with_textract(self, file_path: str) -> str:
        """Perform OCR using AWS Textract"""
        import boto3
        
        # Initialize Textract client (lazy loading)
        if self.textract_client is None:
            print(f"[OCR] Initializing AWS Textract client...")
            
            # Use explicit credentials if provided, otherwise use default AWS credentials
            if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
                print(f"[OCR] Using credentials from .env (region: {AWS_REGION})")
                self.textract_client = boto3.client(
                    'textract',
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                    region_name=AWS_REGION
                )
            else:
                print(f"[OCR] Using AWS CLI credentials (region: {AWS_REGION})")
                self.textract_client = boto3.client(
                    'textract',
                    region_name=AWS_REGION
                )
            
            print(f"[OCR] AWS Textract client initialized")
        
        # Read PDF file
        with open(file_path, 'rb') as document:
            pdf_bytes = document.read()
        
        # Check file size (Textract limit is 5MB for synchronous)
        file_size_mb = len(pdf_bytes) / (1024 * 1024)
        print(f"[OCR] PDF size: {file_size_mb:.2f} MB")
        
        if file_size_mb > 5:
            raise Exception(f"PDF too large ({file_size_mb:.2f}MB). Textract synchronous API supports up to 5MB.")
        
        text = ""
        
        # Try direct PDF processing first
        print(f"[OCR] Calling Textract API...")
        try:
            response = self.textract_client.detect_document_text(
                Document={'Bytes': pdf_bytes}
            )
            
            # Extract text from response
            page_num = 1
            for item in response.get('Blocks', []):
                if item['BlockType'] == 'PAGE':
                    text += f"\n--- Page {page_num} (OCR: AWS Textract) ---\n"
                    page_num += 1
                elif item['BlockType'] == 'LINE':
                    text += item['Text'] + '\n'
            
            print(f"[OCR] Textract extracted {len(text)} characters")
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's an unsupported format error
            if 'UnsupportedDocumentException' in error_msg or 'unsupported document format' in error_msg.lower():
                print(f"[OCR] PDF format not supported by Textract directly, converting to images...")
                # Convert PDF to images and try again
                text = self._ocr_pdf_via_images(file_path)
            else:
                raise Exception(f"Textract API call failed: {str(e)}")
        
        if not text.strip():
            raise Exception("Textract produced no text output")
        
        return text
    
    def _ocr_pdf_via_images(self, file_path: str) -> str:
        """Convert PDF to images and OCR each page with Textract"""
        from pdf2image import convert_from_path
        from PIL import Image
        import io
        
        print(f"[OCR] Converting PDF to images...")
        try:
            images = convert_from_path(file_path, dpi=200)
            print(f"[OCR] Converted {len(images)} pages to images")
        except Exception as e:
            raise Exception(f"Failed to convert PDF to images: {str(e)}")
        
        text = ""
        
        for i, image in enumerate(images):
            print(f"[OCR] Processing page {i + 1}/{len(images)} with Textract...")
            
            # Convert PIL Image to bytes (PNG format)
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            
            # Check image size (max 5MB for Textract)
            img_size_mb = len(img_bytes) / (1024 * 1024)
            if img_size_mb > 5:
                # Reduce quality if too large
                print(f"[OCR] Image too large ({img_size_mb:.2f}MB), reducing quality...")
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=85)
                img_bytes = img_byte_arr.getvalue()
            
            try:
                # Call Textract for this image
                response = self.textract_client.detect_document_text(
                    Document={'Bytes': img_bytes}
                )
                
                # Extract text from response
                text += f"\n--- Page {i + 1} (OCR: AWS Textract) ---\n"
                for item in response.get('Blocks', []):
                    if item['BlockType'] == 'LINE':
                        text += item['Text'] + '\n'
                
                print(f"[OCR] Page {i + 1} complete")
                
            except Exception as e:
                print(f"[OCR] Warning: Page {i + 1} failed: {str(e)}")
                text += f"\n--- Page {i + 1} (OCR: Error) ---\n"
                text += f"[Error: {str(e)}]\n"
        
        print(f"[OCR] Textract extracted {len(text)} characters (via images)")
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
    
    def get_ocr_status(self) -> dict:
        """Get OCR availability status"""
        return {
            'ocr_enabled': self.ocr_enabled,
            'textract_available': self.textract_available,
            'engine': 'textract' if self.ocr_enabled else None
        }
