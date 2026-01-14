"""
Lambda function for document ingestion pipeline
Triggered by S3 upload -> Process -> Chunk -> Embed -> Store in Vector DB
"""

import json
import boto3
import os
from typing import List, Dict
import PyPDF2
from io import BytesIO
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# AWS Clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
textract_client = boto3.client('textract')
secrets_client = boto3.client('secretsmanager')

# Environment variables
VECTOR_STORE_TABLE = os.environ['VECTOR_STORE_TABLE']
METADATA_TABLE = os.environ['METADATA_TABLE']
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
SECRETS_ARN = os.environ['SECRETS_ARN']

# Tables
vector_table = dynamodb.Table(VECTOR_STORE_TABLE)
metadata_table = dynamodb.Table(METADATA_TABLE)

# OpenSearch client
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    os.environ['AWS_REGION'],
    'es',
    session_token=credentials.token
)

opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)

# Configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
OCR_MIN_TEXT_LENGTH = 100


def get_openai_key():
    """Get OpenAI API key from Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=SECRETS_ARN)
        secrets = json.loads(response['SecretString'])
        return secrets['OPENAI_API_KEY']
    except Exception as e:
        print(f"Error getting secret: {str(e)}")
        raise


def extract_text_from_pdf(pdf_bytes: bytes, file_key: str) -> str:
    """Extract text from PDF using PyPDF2, with Textract fallback for scanned PDFs"""
    # Try PyPDF2 first
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        text = ""
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text.strip():
                text += f"\n--- Page {page_num + 1} ---\n{page_text}"
        
        print(f"Extracted {len(text)} characters via PyPDF2")
        
        # Check if OCR is needed
        if len(text.strip()) < OCR_MIN_TEXT_LENGTH:
            print(f"Minimal text found, using Textract OCR")
            text = extract_text_with_textract(pdf_bytes)
        
        return text.strip()
    
    except Exception as e:
        print(f"PyPDF2 failed: {str(e)}, trying Textract")
        return extract_text_with_textract(pdf_bytes)


def extract_text_with_textract(pdf_bytes: bytes) -> str:
    """Extract text using AWS Textract"""
    try:
        # Check file size (5MB limit for synchronous)
        file_size_mb = len(pdf_bytes) / (1024 * 1024)
        
        if file_size_mb > 5:
            raise Exception(f"PDF too large ({file_size_mb:.2f}MB) for Textract synchronous API")
        
        # Call Textract
        response = textract_client.detect_document_text(
            Document={'Bytes': pdf_bytes}
        )
        
        # Extract text
        text = ""
        for item in response.get('Blocks', []):
            if item['BlockType'] == 'LINE':
                text += item['Text'] + '\n'
        
        print(f"Extracted {len(text)} characters via Textract")
        return text.strip()
    
    except Exception as e:
        print(f"Textract failed: {str(e)}")
        raise


def chunk_text(text: str, doc_id: str, doc_name: str) -> List[Dict]:
    """Split text into chunks with overlap"""
    chunks = []
    start = 0
    chunk_id = 0
    
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        
        chunks.append({
            'doc_id': doc_id,
            'chunk_id': str(chunk_id),
            'text': chunk_text,
            'doc_name': doc_name,
            'start_char': start,
            'end_char': end
        })
        
        start += CHUNK_SIZE - CHUNK_OVERLAP
        chunk_id += 1
    
    print(f"Created {len(chunks)} chunks")
    return chunks


def get_embedding(text: str, openai_key: str) -> List[float]:
    """Get embedding from OpenAI"""
    import openai
    
    openai.api_key = openai_key
    
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        raise


def store_in_opensearch(chunks: List[Dict], embeddings: List[List[float]]):
    """Store chunks and embeddings in OpenSearch"""
    index_name = "rag-vectors"
    
    # Create index if it doesn't exist
    if not opensearch_client.indices.exists(index=index_name):
        opensearch_client.indices.create(
            index=index_name,
            body={
                "settings": {
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "doc_id": {"type": "keyword"},
                        "chunk_id": {"type": "keyword"},
                        "text": {"type": "text"},
                        "doc_name": {"type": "keyword"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1536,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib"
                            }
                        }
                    }
                }
            }
        )
        print(f"Created OpenSearch index: {index_name}")
    
    # Index documents
    for chunk, embedding in zip(chunks, embeddings):
        doc_id = f"{chunk['doc_id']}_{chunk['chunk_id']}"
        
        opensearch_client.index(
            index=index_name,
            id=doc_id,
            body={
                "doc_id": chunk['doc_id'],
                "chunk_id": chunk['chunk_id'],
                "text": chunk['text'],
                "doc_name": chunk['doc_name'],
                "embedding": embedding
            }
        )
    
    print(f"Stored {len(chunks)} chunks in OpenSearch")


def store_metadata(doc_id: str, doc_name: str, num_chunks: int, file_size: int):
    """Store document metadata in DynamoDB"""
    metadata_table.put_item(
        Item={
            'doc_id': doc_id,
            'doc_name': doc_name,
            'num_chunks': num_chunks,
            'file_size': file_size,
            'status': 'processed',
            'timestamp': str(boto3.Session().resource('dynamodb').meta.client._make_request('DescribeEndpoints', {})['Endpoints'][0]['CurrentTime'])
        }
    )
    print(f"Stored metadata for {doc_id}")


def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        # Get S3 event details
        s3_event = event['Records'][0]['s3']
        bucket_name = s3_event['bucket']['name']
        file_key = s3_event['object']['key']
        file_size = s3_event['object']['size']
        
        print(f"Processing file: {file_key} from bucket: {bucket_name}")
        
        # Download file from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_bytes = response['Body'].read()
        
        # Generate document ID
        doc_id = file_key.split('/')[-1].split('.')[0]  # Use filename without extension
        doc_name = file_key.split('/')[-1]
        
        # Extract text based on file type
        file_extension = file_key.lower().split('.')[-1]
        
        if file_extension == 'pdf':
            text = extract_text_from_pdf(file_bytes, file_key)
        elif file_extension in ['txt', 'md']:
            text = file_bytes.decode('utf-8')
        else:
            raise Exception(f"Unsupported file type: {file_extension}")
        
        # Chunk text
        chunks = chunk_text(text, doc_id, doc_name)
        
        # Get OpenAI API key
        openai_key = get_openai_key()
        
        # Generate embeddings for all chunks
        embeddings = []
        for chunk in chunks:
            embedding = get_embedding(chunk['text'], openai_key)
            embeddings.append(embedding)
        
        # Store in OpenSearch
        store_in_opensearch(chunks, embeddings)
        
        # Store metadata
        store_metadata(doc_id, doc_name, len(chunks), file_size)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Document processed successfully',
                'doc_id': doc_id,
                'chunks': len(chunks)
            })
        }
    
    except Exception as e:
        print(f"Error processing document: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
