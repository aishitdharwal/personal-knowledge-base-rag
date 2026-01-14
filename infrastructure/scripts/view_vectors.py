#!/usr/bin/env python3
"""
Script to visualize embeddings from PostgreSQL database
Usage: python view_vectors.py [environment] [--limit N]
"""

import os
import sys
import json
import argparse
import subprocess
import psycopg2
import numpy as np
from typing import List, Tuple

def get_db_credentials(environment: str, region: str) -> Tuple[str, str]:
    """Get database host and password from AWS"""
    
    # Get RDS endpoint
    result = subprocess.run([
        'aws', 'cloudformation', 'describe-stacks',
        '--stack-name', f'{environment}-rag-stack',
        '--region', region,
        '--query', 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue',
        '--output', 'text'
    ], capture_output=True, text=True)
    
    db_host = result.stdout.strip()
    if not db_host:
        raise Exception("Could not find RDS endpoint")
    
    # Get password from Secrets Manager
    result = subprocess.run([
        'aws', 'secretsmanager', 'get-secret-value',
        '--secret-id', f'{environment}-rag-db-password',
        '--region', region,
        '--query', 'SecretString',
        '--output', 'text'
    ], capture_output=True, text=True)
    
    secret = json.loads(result.stdout.strip())
    db_password = secret['password']
    
    return db_host, db_password

def connect_to_db(host: str, password: str) -> psycopg2.extensions.connection:
    """Connect to PostgreSQL database"""
    conn = psycopg2.connect(
        host=host,
        port=5432,
        database='ragdb',
        user='raguser',
        password=password
    )
    return conn

def view_vectors(environment: str, region: str, limit: int = 5):
    """View vectors from database"""
    
    print("=" * 60)
    print(f"📊 Viewing Vectors from {environment} environment")
    print("=" * 60)
    print()
    
    # Get credentials
    print("🔑 Getting database credentials...")
    db_host, db_password = get_db_credentials(environment, region)
    print(f"✅ Connected to {db_host}")
    print()
    
    # Connect to database
    conn = connect_to_db(db_host, db_password)
    cursor = conn.cursor()
    
    # Get embedding dimension
    cursor.execute("SELECT vector_dims(embedding) FROM document_chunks LIMIT 1")
    result = cursor.fetchone()
    if not result:
        print("❌ No vectors found in database")
        return
    
    dimension = result[0]
    print(f"Vector dimension: {dimension}")
    print()
    
    # Fetch vectors
    cursor.execute(f"""
        SELECT 
            id,
            doc_name,
            LEFT(text, 100) as text_preview,
            embedding
        FROM document_chunks 
        ORDER BY id 
        LIMIT {limit}
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("❌ No chunks found")
        return
    
    print(f"Found {len(rows)} chunks")
    print()
    
    for idx, (chunk_id, doc_name, text_preview, embedding_str) in enumerate(rows, 1):
        # Parse vector from pgvector format
        # pgvector returns vectors as strings like "[0.1, 0.2, 0.3, ...]"
        embedding = np.array(eval(embedding_str))
        
        print("─" * 60)
        print(f"Chunk {idx}: ID={chunk_id}")
        print(f"Document: {doc_name}")
        print(f"Text: {text_preview}...")
        print()
        print(f"Vector shape: {embedding.shape}")
        print(f"Vector norm (L2): {np.linalg.norm(embedding):.4f}")
        print()
        print("First 10 dimensions:")
        print(embedding[:10])
        print()
        print("Last 10 dimensions:")
        print(embedding[-10:])
        print()
        
        # Statistics
        print("Statistics:")
        print(f"  Min value: {embedding.min():.6f}")
        print(f"  Max value: {embedding.max():.6f}")
        print(f"  Mean value: {embedding.mean():.6f}")
        print(f"  Std dev: {embedding.std():.6f}")
        print()
    
    # Compare first two vectors if we have at least 2
    if len(rows) >= 2:
        print("=" * 60)
        print("📏 Comparing First Two Vectors")
        print("=" * 60)
        print()
        
        vec1 = np.array(eval(rows[0][3]))
        vec2 = np.array(eval(rows[1][3]))
        
        # Cosine similarity
        cosine_sim = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        
        # Euclidean distance
        l2_distance = np.linalg.norm(vec1 - vec2)
        
        # Cosine distance (used by pgvector)
        cosine_distance = 1 - cosine_sim
        
        print(f"Vector 1: {rows[0][2][:60]}...")
        print(f"Vector 2: {rows[1][2][:60]}...")
        print()
        print(f"Cosine similarity: {cosine_sim:.6f}")
        print(f"Cosine distance: {cosine_distance:.6f}")
        print(f"Euclidean (L2) distance: {l2_distance:.6f}")
        print()
        
        if cosine_sim > 0.9:
            print("✅ Very similar vectors (cosine sim > 0.9)")
        elif cosine_sim > 0.7:
            print("📊 Moderately similar vectors (0.7 < cosine sim < 0.9)")
        else:
            print("❌ Dissimilar vectors (cosine sim < 0.7)")
    
    cursor.close()
    conn.close()

def export_vectors_to_numpy(environment: str, region: str, output_file: str):
    """Export all vectors to numpy file"""
    
    print("=" * 60)
    print(f"💾 Exporting Vectors to {output_file}")
    print("=" * 60)
    print()
    
    # Get credentials
    print("🔑 Getting database credentials...")
    db_host, db_password = get_db_credentials(environment, region)
    print(f"✅ Connected to {db_host}")
    print()
    
    # Connect to database
    conn = connect_to_db(db_host, db_password)
    cursor = conn.cursor()
    
    # Fetch all vectors
    print("📥 Fetching all vectors...")
    cursor.execute("""
        SELECT 
            id,
            doc_name,
            text,
            embedding
        FROM document_chunks 
        ORDER BY id
    """)
    
    rows = cursor.fetchall()
    print(f"Found {len(rows)} vectors")
    
    # Convert to numpy arrays
    vectors = []
    metadata = []
    
    for chunk_id, doc_name, text, embedding_str in rows:
        embedding = np.array(eval(embedding_str))
        vectors.append(embedding)
        metadata.append({
            'id': chunk_id,
            'doc_name': doc_name,
            'text': text[:200]  # First 200 chars
        })
    
    vectors = np.array(vectors)
    
    # Save to file
    np.savez(
        output_file,
        vectors=vectors,
        metadata=metadata
    )
    
    print(f"✅ Saved {len(vectors)} vectors to {output_file}")
    print(f"   Shape: {vectors.shape}")
    print(f"   Size: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
    
    cursor.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description='View vectors from PostgreSQL database')
    parser.add_argument('environment', nargs='?', default='production', 
                       help='Environment name (default: production)')
    parser.add_argument('--region', default='ap-south-1',
                       help='AWS region (default: ap-south-1)')
    parser.add_argument('--limit', type=int, default=5,
                       help='Number of vectors to display (default: 5)')
    parser.add_argument('--export', type=str,
                       help='Export all vectors to numpy file (e.g., vectors.npz)')
    
    args = parser.parse_args()
    
    try:
        if args.export:
            export_vectors_to_numpy(args.environment, args.region, args.export)
        else:
            view_vectors(args.environment, args.region, args.limit)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
