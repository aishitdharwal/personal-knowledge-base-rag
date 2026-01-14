#!/bin/bash

# Script to explore PostgreSQL database with pgvector
# Usage: ./explore_db.sh [environment]

set -e

ENVIRONMENT=${1:-production}
REGION="ap-south-1"

echo "=================================================="
echo "PostgreSQL Database Explorer"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "=================================================="
echo ""

# Get RDS endpoint
echo "🔍 Getting RDS endpoint..."
DB_HOST=$(aws cloudformation describe-stacks \
    --stack-name ${ENVIRONMENT}-rag-stack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' \
    --output text)

if [ -z "$DB_HOST" ]; then
    echo "❌ Could not find RDS endpoint"
    exit 1
fi

echo "✅ RDS Endpoint: $DB_HOST"
echo ""

# Get database password from Secrets Manager
echo "🔑 Getting database password..."
DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id ${ENVIRONMENT}-rag-db-password \
    --region $REGION \
    --query 'SecretString' \
    --output text | jq -r '.password')

if [ -z "$DB_PASSWORD" ]; then
    echo "❌ Could not retrieve database password"
    exit 1
fi

echo "✅ Retrieved database password"
echo ""

# Database connection details
DB_NAME="ragdb"
DB_USER="raguser"
DB_PORT="5432"

# Export for psql
export PGPASSWORD="$DB_PASSWORD"

echo "=================================================="
echo "📊 Database Statistics"
echo "=================================================="
echo ""

# Check if database is accessible
echo "Testing connection..."
if psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Connected successfully to PostgreSQL"
else
    echo "❌ Could not connect to database"
    echo ""
    echo "Make sure:"
    echo "  1. RDS is publicly accessible"
    echo "  2. Security group allows your IP (port 5432)"
    echo "  3. psql is installed (brew install postgresql)"
    exit 1
fi

echo ""

# Function to run query and display results
run_query() {
    local description=$1
    local query=$2
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 $description"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT -c "$query"
    echo ""
}

# Check pgvector extension
run_query "Check pgvector extension" \
"SELECT * FROM pg_extension WHERE extname = 'vector';"

# Database size
run_query "Database size" \
"SELECT pg_size_pretty(pg_database_size('$DB_NAME')) as database_size;"

# Table list
run_query "All tables" \
"SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Embedding configuration
run_query "Embedding configuration" \
"SELECT * FROM embedding_config;"

# Document count
run_query "Total documents" \
"SELECT 
    COUNT(DISTINCT doc_id) as total_documents,
    COUNT(*) as total_chunks
FROM document_chunks;"

# Documents with chunk counts
run_query "Documents and their chunk counts" \
"SELECT 
    doc_name,
    doc_id,
    COUNT(*) as num_chunks,
    pg_size_pretty(SUM(pg_column_size(text))) as text_size,
    pg_size_pretty(SUM(pg_column_size(embedding))) as embedding_size
FROM document_chunks 
GROUP BY doc_id, doc_name
ORDER BY num_chunks DESC;"

# Sample chunks
run_query "Sample chunks (first 3)" \
"SELECT 
    id,
    doc_name,
    chunk_id,
    LEFT(text, 100) || '...' as text_preview,
    vector_dims(embedding) as embedding_dimension
FROM document_chunks 
ORDER BY id 
LIMIT 3;"

# Index information
run_query "Indexes on document_chunks table" \
"SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'document_chunks';"

# Vector statistics
run_query "Vector dimension statistics" \
"SELECT 
    vector_dims(embedding) as dimension,
    COUNT(*) as count
FROM document_chunks 
GROUP BY vector_dims(embedding);"

# Check for HNSW index
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 HNSW Index Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HNSW_EXISTS=$(psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT -t -c \
    "SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'document_chunks_embedding_idx';")

if [ "$HNSW_EXISTS" -gt 0 ]; then
    echo "✅ HNSW index exists (fast vector search enabled)"
else
    echo "⚠️  HNSW index does not exist (searches will be slower)"
    echo ""
    echo "To create HNSW index for faster searches, run:"
    echo "  psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT -c \\"
    echo "    \"CREATE INDEX document_chunks_embedding_idx ON document_chunks \\"
    echo "    USING hnsw (embedding vector_cosine_ops);\""
fi

echo ""

# Interactive mode option
echo "=================================================="
echo "🎯 Quick Actions"
echo "=================================================="
echo ""
echo "1. Open interactive psql session"
echo "2. Test vector search"
echo "3. View recent documents"
echo "4. View actual vector embeddings (first 3 chunks)"
echo "5. View vector statistics and norms"
echo "6. Compare two vectors (cosine similarity)"
echo "7. Create HNSW index (if not exists)"
echo "8. Exit"
echo ""
read -p "Choose an option (1-8): " choice

case $choice in
    1)
        echo ""
        echo "Starting interactive psql session..."
        echo "Type 'exit' or '\q' to quit"
        echo ""
        psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT
        ;;
    2)
        echo ""
        echo "Testing vector search with sample query..."
        echo ""
        run_query "Vector similarity search test" \
        "WITH query_embedding AS (
            SELECT embedding 
            FROM document_chunks 
            LIMIT 1
        )
        SELECT 
            doc_name,
            LEFT(text, 150) || '...' as text_preview,
            embedding <=> (SELECT embedding FROM query_embedding) as distance
        FROM document_chunks
        ORDER BY distance
        LIMIT 5;"
        ;;
    3)
        echo ""
        run_query "5 most recent documents" \
        "SELECT 
            doc_name,
            doc_id,
            COUNT(*) as chunks,
            MIN(id) as first_chunk_id
        FROM document_chunks 
        GROUP BY doc_id, doc_name
        ORDER BY MIN(id) DESC
        LIMIT 5;"
        ;;
    4)
        echo ""
        echo "Showing ACTUAL VECTOR VALUES for first 3 chunks..."
        echo ""
        run_query "First 3 vectors (raw embeddings)" \
        "SELECT 
            id,
            doc_name,
            LEFT(text, 80) || '...' as text_preview,
            vector_dims(embedding) as dimensions,
            embedding
        FROM document_chunks 
        ORDER BY id 
        LIMIT 3;"
        ;;
    5)
        echo ""
        echo "Vector Statistics and Norms..."
        echo ""
        run_query "Vector norms and statistics" \
        "SELECT 
            id,
            doc_name,
            LEFT(text, 60) || '...' as text_preview,
            vector_dims(embedding) as dimensions,
            -- L2 norm (magnitude)
            sqrt((embedding <#> embedding)) as l2_norm,
            -- First 5 dimensions as sample
            (embedding::text)::json->0 as dim_0,
            (embedding::text)::json->1 as dim_1,
            (embedding::text)::json->2 as dim_2,
            (embedding::text)::json->3 as dim_3,
            (embedding::text)::json->4 as dim_4
        FROM document_chunks 
        ORDER BY id 
        LIMIT 5;"
        ;;
    6)
        echo ""
        echo "Comparing first two vectors..."
        echo ""
        run_query "Vector comparison (cosine distance and similarity)" \
        "WITH first_two AS (
            SELECT 
                id,
                doc_name,
                LEFT(text, 100) as text_preview,
                embedding,
                ROW_NUMBER() OVER (ORDER BY id) as rn
            FROM document_chunks
            LIMIT 2
        )
        SELECT 
            a.id as vec1_id,
            a.text_preview as vec1_text,
            b.id as vec2_id,
            b.text_preview as vec2_text,
            -- Cosine distance (0 = identical, 2 = opposite)
            a.embedding <=> b.embedding as cosine_distance,
            -- Cosine similarity (-1 to 1, 1 = identical)
            1 - (a.embedding <=> b.embedding) as cosine_similarity,
            -- L2 distance (Euclidean)
            a.embedding <-> b.embedding as l2_distance,
            -- Inner product
            (a.embedding <#> b.embedding) as inner_product
        FROM first_two a, first_two b
        WHERE a.rn = 1 AND b.rn = 2;"
        ;;
    7)
        echo ""
        echo "Creating HNSW index..."
        psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT -c \
            "CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx 
             ON document_chunks USING hnsw (embedding vector_cosine_ops);"
        echo "✅ HNSW index created/verified"
        ;;
    8)
        echo "Goodbye!"
        ;;
    *)
        echo "Invalid option"
        ;;
esac

echo ""
echo "=================================================="
echo "💡 Pro Tips for Viewing Vectors"
echo "=================================================="
echo ""
echo "In psql session, try these queries:"
echo ""
echo "1. View full vector for a specific chunk:"
echo "   SELECT embedding FROM document_chunks WHERE id = 1;"
echo ""
echo "2. View first 10 dimensions of all vectors:"
echo "   SELECT id, embedding[1:10] FROM document_chunks LIMIT 5;"
echo ""
echo "3. View vector as JSON array:"
echo "   SELECT (embedding::text)::json FROM document_chunks LIMIT 1;"
echo ""
echo "4. Calculate vector norm (magnitude):"
echo "   SELECT id, sqrt(embedding <#> embedding) as norm"
echo "   FROM document_chunks LIMIT 5;"
echo ""
echo "5. Find most similar to a specific chunk:"
echo "   SELECT id, text, embedding <=> "
echo "     (SELECT embedding FROM document_chunks WHERE id = 1) as distance"
echo "   FROM document_chunks ORDER BY distance LIMIT 5;"
echo ""
echo "=================================================="
echo "Connection String (for manual access):"
echo "=================================================="
echo "psql -h $DB_HOST -U $DB_USER -d $DB_NAME -p $DB_PORT"
echo ""
echo "Password stored in AWS Secrets Manager:"
echo "  Secret: ${ENVIRONMENT}-rag-db-password"
echo "=================================================="

# Cleanup
unset PGPASSWORD
