"""
Lambda function for automatic document ingestion from S3 to PostgreSQL + pgvector

This function is triggered by S3 events when files are uploaded to the documents bucket.
It processes the document, generates embeddings, and stores them in PostgreSQL.
"""

import json
import os
import boto3
import tempfile
from typing import List, Tuple
import PyPDF2
import re

# AWS clients
s3_client = boto3.client('s3')
secrets_client = boto3.client('secretsmanager')
textract_client = boto3.client('textract')

# Environment variables
SECRETS_ARN = os.environ['SECRETS_ARN']
DB_PASSWORD_SECRET = os.environ.get('DB_PASSWORD_SECRET')
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'ragdb')
DB_USER = os.environ.get('DB_USER', 'raguser')
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', '1000'))
CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', '200'))
EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER', 'openai')
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'text-embedding-3-small')

# Global connections (reused across invocations)
db_connection = None
openai_api_key = None


def get_secrets():
    """Retrieve API keys from Secrets Manager"""
    global openai_api_key
    
    if openai_api_key:
        return
    
    try:
        response = secrets_client.get_secret_value(SecretId=SECRETS_ARN)
        secrets = json.loads(response['SecretString'])
        openai_api_key = secrets.get('OPENAI_API_KEY')
        print("✅ Retrieved API keys from Secrets Manager")
    except Exception as e:
        print(f"❌ Error getting secrets: {e}")
        raise


def get_db_password():
    """Get database password from Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=DB_PASSWORD_SECRET)
        secret = json.loads(response['SecretString'])
        return secret['password']
    except Exception as e:
        print(f"❌ Error getting database password: {e}")
        raise


def get_db_connection():
    """Get or create database connection"""
    global db_connection
    
    if db_connection:
        try:
            # Test if connection is alive
            cursor = db_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return db_connection
        except:
            db_connection = None
    
    # Create new connection
    try:
        import psycopg2
        
        db_password = get_db_password()
        
        db_connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=db_password
        )
        
        # Enable pgvector extension
        cursor = db_connection.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        db_connection.commit()
        cursor.close()
        
        print(f"✅ Connected to PostgreSQL at {DB_HOST}")
        return db_connection
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        raise


def ensure_tables_exist(conn, dimension: int = 1536):
    """Ensure database tables exist"""
    cursor = conn.cursor()
    
    try:
        # Check if embedding_config table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'embedding_config'
            )
        """)
        
        if not cursor.fetchone()[0]:
            print("⚠️  Tables don't exist, creating them...")
            
            # Create embedding_config table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embedding_config (
                    id SERIAL PRIMARY KEY,
                    provider VARCHAR(100) NOT NULL,
                    model VARCHAR(200) NOT NULL,
                    dimension INTEGER NOT NULL
                )
            """)
            
            # Create document_chunks table with vector dimension
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id SERIAL PRIMARY KEY,
                    doc_id VARCHAR(255) NOT NULL,
                    chunk_id INTEGER NOT NULL,
                    doc_name VARCHAR(500) NOT NULL,
                    text TEXT NOT NULL,
                    start_char INTEGER NOT NULL,
                    end_char INTEGER NOT NULL,
                    embedding VECTOR({dimension})
                )
            """)
            
            # Create index on doc_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS document_chunks_doc_id_idx 
                ON document_chunks(doc_id)
            """)
            
            conn.commit()
            print(f"✅ Created database tables with vector dimension {dimension}")
        
        cursor.close()
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        print(f"❌ Error ensuring tables: {e}")
        raise


def get_embedding_config(conn):
    """Get embedding configuration from database"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT provider, model, dimension FROM embedding_config LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            return {
                'provider': result[0],
                'model': result[1],
                'dimension': result[2]
            }
        return None
    except Exception as e:
        cursor.close()
        print(f"⚠️  No embedding config found: {e}")
        return None


def set_embedding_config(conn, provider: str, model: str, dimension: int):
    """Set embedding configuration in database"""
    cursor = conn.cursor()
    try:
        # Delete existing config
        cursor.execute("DELETE FROM embedding_config")
        
        # Insert new config
        cursor.execute("""
            INSERT INTO embedding_config (provider, model, dimension)
            VALUES (%s, %s, %s)
        """, (provider, model, dimension))
        
        conn.commit()
        cursor.close()
        print(f"✅ Set embedding config: {provider}/{model} ({dimension}d)")
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        print(f"❌ Error setting embedding config: {e}")
        raise


def generate_embeddings_openai(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using OpenAI"""
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=openai_api_key)
        
        # Batch embed
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        
        embeddings = [item.embedding for item in response.data]
        print(f"✅ Generated {len(embeddings)} embeddings via OpenAI")
        
        return embeddings
        
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        raise


def get_embedding_dimension() -> int:
    """Get embedding dimension for the configured model"""
    if EMBEDDING_PROVIDER == 'openai':
        if 'large' in EMBEDDING_MODEL:
            return 3072
        elif 'small' in EMBEDDING_MODEL:
            return 1536
        else:
            return 1536  # default
    return 384  # sentence-transformers default


def extract_text_with_textract(bucket: str, key: str) -> str:
    """
    Extract text from PDF using AWS Textract OCR
    """
    try:
        print(f"📸 Starting OCR with AWS Textract for s3://{bucket}/{key}")
        
        # Try direct PDF processing first
        try:
            response = textract_client.detect_document_text(
                Document={
                    'S3Object': {
                        'Bucket': bucket,
                        'Name': key
                    }
                }
            )
            
            # Extract text from response
            text = ""
            page_num = 1
            
            for block in response['Blocks']:
                if block['BlockType'] == 'LINE':
                    if 'Page' in block and block['Page'] != page_num:
                        text += f"\n--- Page {block['Page']} ---\n"
                        page_num = block['Page']
                    text += block['Text'] + "\n"
            
            print(f"✅ OCR extracted {len(text)} characters")
            return text
            
        except Exception as pdf_error:
            # If direct PDF fails, try converting to images and processing
            if 'UnsupportedDocumentException' in str(pdf_error):
                print("⚠️  Direct PDF OCR failed, trying image-based approach...")
                return extract_text_from_pdf_via_images(bucket, key)
            raise
        
    except Exception as e:
        print(f"❌ Error with Textract OCR: {e}")
        raise


def extract_text_from_pdf_via_images(bucket: str, key: str) -> str:
    """
    Fallback for unsupported PDFs - returns minimal text with warning
    Note: Full image-based OCR requires poppler binaries not available in Lambda
    """
    print("⚠️  PDF format not directly supported by Textract")
    print("💡 Suggestion: Pre-process this PDF or use a different format")
    print("💡 For now, returning minimal extracted text")
    
    # Return empty string - the PDF will be skipped or show minimal text
    return "[OCR not available for this PDF format - please pre-process or use text-based PDF]"


def extract_text_from_pdf(file_path: str, bucket: str = None, key: str = None) -> str:
    """Extract text from PDF, using OCR if needed"""
    text = ""
    
    try:
        # First try PyPDF2 for text extraction
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                
                if page_text.strip():
                    text += f"\n--- Page {page_num + 1} ---\n"
                    text += page_text
        
        # Check if we got meaningful text (more than 100 chars)
        if len(text.strip()) > 100:
            print(f"✅ Extracted {len(text)} characters from PDF (text-based)")
            return text
        
        # If text is too short, it's likely a scanned PDF - use OCR
        print("⚠️  PDF appears to be scanned/image-based, using OCR...")
        
        if not bucket or not key:
            print("❌ Cannot perform OCR: S3 bucket/key not provided")
            return text
        
        # Use AWS Textract for OCR
        return extract_text_with_textract(bucket, key)
        
    except Exception as e:
        print(f"❌ Error extracting PDF text: {e}")
        raise


def extract_text_from_file(file_path: str, bucket: str = None, key: str = None) -> str:
    """Extract text from file based on extension"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        return extract_text_from_pdf(file_path, bucket, key)
    elif ext in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def clean_text(text: str) -> str:
    """Clean extracted text"""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            cleaned_lines.append(line)
    
    cleaned_text = '\n'.join(cleaned_lines)
    cleaned_text = re.sub(r' +', ' ', cleaned_text)
    
    return cleaned_text


def chunk_text(text: str, doc_id: str, doc_name: str) -> List[Tuple[int, str, int, int]]:
    """
    Split text into chunks
    Returns: List of (chunk_id, text, start_char, end_char)
    """
    chunks = []
    start = 0
    chunk_id = 0
    
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        
        chunks.append((chunk_id, chunk_text, start, end))
        
        start += CHUNK_SIZE - CHUNK_OVERLAP
        chunk_id += 1
    
    print(f"✅ Created {len(chunks)} chunks")
    return chunks


def store_chunks_in_db(conn, doc_id: str, doc_name: str, chunks: List[Tuple], embeddings: List[List[float]]):
    """Store chunks and embeddings in PostgreSQL"""
    cursor = conn.cursor()
    
    try:
        for (chunk_id, text, start_char, end_char), embedding in zip(chunks, embeddings):
            cursor.execute("""
                INSERT INTO document_chunks (doc_id, chunk_id, doc_name, text, start_char, end_char, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (doc_id, chunk_id, doc_name, text, start_char, end_char, embedding))
        
        conn.commit()
        cursor.close()
        
        print(f"✅ Stored {len(chunks)} chunks in database")
        
    except Exception as e:
        conn.rollback()
        cursor.close()
        print(f"❌ Error storing chunks: {e}")
        raise


def process_document(bucket: str, key: str) -> dict:
    """
    Main document processing pipeline
    
    1. Download from S3
    2. Extract text
    3. Chunk text
    4. Generate embeddings
    5. Store in PostgreSQL
    """
    print(f"📄 Processing document: s3://{bucket}/{key}")
    
    # Extract doc_id and doc_name from S3 key
    # Expected format: doc_id_filename.ext or just filename.ext
    filename = os.path.basename(key)
    
    if '_' in filename:
        parts = filename.split('_', 1)
        doc_id = parts[0]
        doc_name = parts[1]
    else:
        doc_id = filename
        doc_name = filename
    
    # Download file to temp directory
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
        tmp_path = tmp_file.name
        
        try:
            print(f"⬇️  Downloading from S3...")
            s3_client.download_file(bucket, key, tmp_path)
            print(f"✅ Downloaded to {tmp_path}")
            
            # Extract text
            print("📖 Extracting text...")
            text = extract_text_from_file(tmp_path, bucket, key)
            text = clean_text(text)
            print(f"✅ Extracted {len(text)} characters")
            
            # Chunk text
            print("✂️  Chunking text...")
            chunks = chunk_text(text, doc_id, doc_name)
            
            # Get database connection
            conn = get_db_connection()
            
            # Get embedding dimension first
            dimension = get_embedding_dimension()
            
            # Ensure tables exist with correct dimension
            ensure_tables_exist(conn, dimension)
            
            # Check/set embedding config
            config = get_embedding_config(conn)
            
            if not config:
                print("⚙️  Setting initial embedding configuration...")
                set_embedding_config(conn, EMBEDDING_PROVIDER, EMBEDDING_MODEL, dimension)
            else:
                print(f"✅ Using existing config: {config['provider']}/{config['model']}")
                if config['provider'] != EMBEDDING_PROVIDER or config['model'] != EMBEDDING_MODEL:
                    print(f"⚠️  Warning: Configured provider/model differs from environment")
            
            # Generate embeddings
            print("🧮 Generating embeddings...")
            get_secrets()
            texts = [chunk[1] for chunk in chunks]
            embeddings = generate_embeddings_openai(texts)
            
            # Store in database
            print("💾 Storing in PostgreSQL...")
            store_chunks_in_db(conn, doc_id, doc_name, chunks, embeddings)
            
            # Create HNSW index if it doesn't exist
            try:
                cursor = conn.cursor()
                
                # Check current dimension of embedding column
                cursor.execute("""
                    SELECT atttypmod 
                    FROM pg_attribute 
                    WHERE attrelid = 'document_chunks'::regclass 
                    AND attname = 'embedding'
                """)
                
                result = cursor.fetchone()
                if result and result[0] == -1:
                    # No dimension set, need to alter column
                    print(f"⚙️  Setting embedding dimension to {dimension}...")
                    cursor.execute(f"""
                        ALTER TABLE document_chunks 
                        ALTER COLUMN embedding TYPE vector({dimension})
                    """)
                    conn.commit()
                    print(f"✅ Set embedding dimension to {dimension}")
                
                # Create the HNSW index
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx 
                    ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """)
                
                conn.commit()
                cursor.close()
                print(f"✅ HNSW index created")
            except Exception as e:
                print(f"⚠️  Could not create HNSW index: {e}")
                try:
                    conn.rollback()
                except:
                    pass
            
            return {
                'statusCode': 200,
                'doc_id': doc_id,
                'doc_name': doc_name,
                'chunks': len(chunks),
                'characters': len(text)
            }
            
        except Exception as e:
            print(f"❌ Error processing document: {e}")
            raise
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def lambda_handler(event, context):
    """
    Lambda handler triggered by S3 events
    """
    print("=" * 60)
    print("🚀 Lambda Ingestion Pipeline Started")
    print("=" * 60)
    
    try:
        # Parse S3 event
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            
            # Skip if not a supported file type
            ext = os.path.splitext(key)[1].lower()
            if ext not in ['.pdf', '.txt', '.md']:
                print(f"⏭️  Skipping unsupported file type: {key}")
                continue
            
            # Process document
            result = process_document(bucket, key)
            
            print("=" * 60)
            print("✅ Processing Complete!")
            print(f"   Document: {result['doc_name']}")
            print(f"   Chunks: {result['chunks']}")
            print(f"   Characters: {result['characters']}")
            print("=" * 60)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Success')
        }
        
    except Exception as e:
        print(f"❌ Lambda execution failed: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
