from typing import List
from app.models import DocumentChunk
from app.config import (
    CHUNK_SIZE, 
    CHUNK_OVERLAP,
    OCR_ENABLED,
    OCR_PRIMARY,
    OCR_FALLBACK,
    OCR_MIN_TEXT_LENGTH,
    OCR_LANGUAGES,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    TEXTRACT_MAX_PAGES,
    TEXTRACT_TIMEOUT
)
import PyPDF2
import os
import re
import ssl
import certifi

class DocumentProcessor:
    """Handles document loading and chunking for txt, md, and pdf files with OCR support"""
    
    def __init__(self, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ocr_enabled = OCR_ENABLED
        
        # Fix SSL certificate issues for EasyOCR downloads
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
        except Exception:
            pass
        
        # Lazy load OCR libraries
        self.easyocr_available = False
        self.textract_available = False
        self.easyocr_reader = None
        self.textract_client = None
        
        self._check_ocr_availability()
    
    def _check_ocr_availability(self):
        """Check which OCR libraries are available"""
        # Check EasyOCR
        try:
            import easyocr
            self.easyocr_available = True
            print("[OCR] EasyOCR is available")
        except Exception:
            print("[OCR] EasyOCR not available")
        
        # Check AWS Textract
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
        2. If minimal text found, use OCR (EasyOCR → Tesseract fallback)
        
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
            try:
                text = self._ocr_pdf(file_path)
                print(f"[OCR] Successfully extracted {len(text.strip())} characters via OCR")
            except Exception as e:
                print(f"[OCR] OCR failed: {str(e)}")
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
    
    def _ocr_pdf(self, file_path: str) -> str:
        """
        Perform OCR on PDF with AWS Textract
        
        Uses:
        1. AWS Textract (primary - cloud, highest quality)
        2. EasyOCR (fallback - local, if enabled)
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            OCR-extracted text
        """
        print(f"[OCR] Starting OCR process...")
        
        # Try primary OCR method
        if OCR_PRIMARY == 'textract' and self.textract_available:
            print(f"[OCR] Using AWS Textract (primary engine)...")
            try:
                result = self._ocr_with_textract(file_path)
                print(f"[OCR] AWS Textract completed successfully")
                return result
            except Exception as e:
                print(f"[OCR] AWS Textract failed: {str(e)}")
                # Try fallback if configured
                if OCR_FALLBACK == 'easyocr' and self.easyocr_available:
                    print(f"[OCR] Trying EasyOCR (fallback)...")
                    images = self._convert_pdf_to_images(file_path)
                    try:
                        result = self._ocr_with_easyocr(images)
                        print(f"[OCR] EasyOCR completed successfully")
                        return result
                    except Exception as e2:
                        print(f"[OCR] EasyOCR also failed: {str(e2)}")
                        raise Exception(f"Both OCR engines failed. Textract: {str(e)}, EasyOCR: {str(e2)}")
                else:
                    # No fallback configured or available
                    raise
        
        elif OCR_PRIMARY == 'easyocr' and self.easyocr_available:
            print(f"[OCR] Using EasyOCR (primary engine)...")
            images = self._convert_pdf_to_images(file_path)
            try:
                result = self._ocr_with_easyocr(images)
                print(f"[OCR] EasyOCR completed successfully")
                return result
            except Exception as e:
                print(f"[OCR] EasyOCR failed: {str(e)}")
                # No fallback for EasyOCR
                raise
        
        else:
            error_msg = f"No OCR engine available. Primary: {OCR_PRIMARY} (available: {self.textract_available if OCR_PRIMARY == 'textract' else self.easyocr_available})"
            print(f"[OCR] ERROR: {error_msg}")
            raise Exception(error_msg)
    
    def _convert_pdf_to_images(self, file_path: str) -> list:
        """Convert PDF to images for OCR"""
        print(f"[OCR] Converting PDF to images...")
        try:
            from pdf2image import convert_from_path
            print(f"[OCR] Converting with DPI=200 (this may take a moment)...")
            images = convert_from_path(file_path, dpi=200)
            print(f"[OCR] Converted {len(images)} pages to images")
            return images
        except Exception as e:
            error_msg = f"Failed to convert PDF to images: {str(e)}"
            print(f"[OCR] ERROR: {error_msg}")
            raise Exception(error_msg)
    
    def _ocr_with_easyocr(self, images: list) -> str:
        """Perform OCR using EasyOCR"""
        import numpy as np
        
        # Initialize EasyOCR reader (lazy loading)
        if self.easyocr_reader is None:
            try:
                import easyocr
                print(f"[OCR] Loading EasyOCR model for languages: {OCR_LANGUAGES}")
                print(f"[OCR] This may take a moment on first run (downloading models)...")
                
                # Create reader with CPU (safer, more compatible)
                self.easyocr_reader = easyocr.Reader(OCR_LANGUAGES, gpu=False, verbose=False)
                print(f"[OCR] EasyOCR model loaded successfully")
            except Exception as e:
                error_msg = f"Failed to load EasyOCR model: {str(e)}"
                print(f"[OCR] ERROR: {error_msg}")
                raise Exception(error_msg)
        
        text = ""
        total_pages = len(images)
        
        for i, image in enumerate(images):
            try:
                print(f"[OCR] EasyOCR processing page {i + 1}/{total_pages}...")
                
                # Convert PIL Image to numpy array
                image_array = np.array(image)
                
                # Perform OCR with timeout protection
                results = self.easyocr_reader.readtext(image_array)
                
                # Extract text from results
                page_text = ' '.join([result[1] for result in results])
                
                text += f"\n--- Page {i + 1} (OCR: EasyOCR) ---\n"
                text += page_text + '\n'
                
                print(f"[OCR] EasyOCR page {i + 1}/{total_pages} complete ({len(page_text)} chars)")
                
            except Exception as e:
                print(f"[OCR] Warning: Page {i + 1} failed: {str(e)}")
                text += f"\n--- Page {i + 1} (OCR: EasyOCR - Error) ---\n"
                text += f"[Error processing page: {str(e)}]\n"
                # Continue with other pages
        
        if not text.strip():
            raise Exception("EasyOCR produced no text output")
        
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
            'easyocr_available': self.easyocr_available,
            'textract_available': self.textract_available,
            'primary_engine': OCR_PRIMARY if self.ocr_enabled else None,
            'fallback_engine': OCR_FALLBACK if self.ocr_enabled else None,
            'languages': OCR_LANGUAGES if self.ocr_enabled else None
        }
    
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
        
        # Use synchronous API
        print(f"[OCR] Calling Textract API (direct PDF)...")
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
            if 'UnsupportedDocumentException' in error_msg or 'unsupported document format' in error_msg:
                print(f"[OCR] PDF format not supported, converting to images first...")
                # Convert PDF to images and try again
                text = self._ocr_pdf_via_images(file_path)
            else:
                raise Exception(f"Textract API call failed: {error_msg}")
        
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
