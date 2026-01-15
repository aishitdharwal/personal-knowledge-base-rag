#!/bin/bash

# Test script for Lambda S3 Ingestion Pipeline
# This script tests the complete pipeline end-to-end

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-ap-south-1}

echo "=================================================="
echo "Testing Lambda S3 Ingestion Pipeline"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "=================================================="
echo ""

# Get AWS account ID
echo "🔍 Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✅ Account ID: $ACCOUNT_ID"
echo ""

# Create test document
echo "📄 Creating test document..."
TEST_FILE="test-$(date +%s).txt"
cat > $TEST_FILE << EOF
This is a test document for the RAG system.

It contains multiple paragraphs to test chunking.

The Lambda function should:
1. Download this file from S3
2. Extract the text
3. Chunk it into pieces
4. Generate embeddings via OpenAI
5. Store in PostgreSQL with pgvector

If you can see this in the database, everything works!
EOF

echo "✅ Created test file: $TEST_FILE"
echo ""

# Upload to S3
echo "📤 Uploading to S3..."
BUCKET="production-rag-docs-${ACCOUNT_ID}"
S3_KEY="test-upload_${TEST_FILE}"

aws s3 cp $TEST_FILE s3://${BUCKET}/${S3_KEY}
echo "✅ Uploaded to s3://${BUCKET}/${S3_KEY}"
echo ""

# Wait a moment
echo "⏳ Waiting 5 seconds for Lambda trigger..."
sleep 5
echo ""

# Check Lambda logs
echo "📋 Checking Lambda logs..."
FUNCTION_NAME="${ENVIRONMENT}-rag-ingestion"

echo "Recent logs (last 30 seconds):"
aws logs filter-log-events \
    --log-group-name /aws/lambda/${FUNCTION_NAME} \
    --start-time $(($(date +%s) - 30))000 \
    --region $REGION \
    --query 'events[].message' \
    --output text | tail -20

echo ""

# Wait for processing
echo "⏳ Waiting 10 seconds for processing to complete..."
sleep 10
echo ""

# Check database
echo "💾 Checking database..."
DB_HOST=$(aws cloudformation describe-stacks \
    --stack-name ${ENVIRONMENT}-rag-stack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' \
    --output text)

DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id ${ENVIRONMENT}-rag-db-password \
    --region $REGION \
    --query 'SecretString' \
    --output text | jq -r '.password')

echo "Querying database for test document..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U raguser -d ragdb -t -c \
    "SELECT COUNT(*) FROM document_chunks WHERE doc_name LIKE '%${TEST_FILE}%';"

CHUNK_COUNT=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U raguser -d ragdb -t -c \
    "SELECT COUNT(*) FROM document_chunks WHERE doc_name LIKE '%${TEST_FILE}%';" | tr -d ' ')

echo ""

# Cleanup test file
rm $TEST_FILE

# Summary
echo "=================================================="
echo "Test Results"
echo "=================================================="
echo ""

if [ "$CHUNK_COUNT" -gt "0" ]; then
    echo "✅ SUCCESS!"
    echo ""
    echo "Test document was:"
    echo "  1. Uploaded to S3"
    echo "  2. Processed by Lambda"
    echo "  3. Stored in PostgreSQL"
    echo ""
    echo "Found $CHUNK_COUNT chunks in database"
    echo ""
    echo "Your Lambda S3 Ingestion Pipeline is working! 🎉"
else
    echo "❌ FAILED"
    echo ""
    echo "Test document was uploaded but not found in database."
    echo ""
    echo "Troubleshooting steps:"
    echo "  1. Check Lambda logs:"
    echo "     aws logs tail /aws/lambda/${FUNCTION_NAME} --follow"
    echo ""
    echo "  2. Verify Lambda is triggered:"
    echo "     aws lambda list-event-source-mappings --function-name ${FUNCTION_NAME}"
    echo ""
    echo "  3. Check S3 bucket notifications:"
    echo "     aws s3api get-bucket-notification-configuration --bucket ${BUCKET}"
    echo ""
    echo "  4. Review setup guide:"
    echo "     cat LAMBDA_SETUP.md"
fi

echo ""
echo "=================================================="

# Show sample of what was stored (if successful)
if [ "$CHUNK_COUNT" -gt "0" ]; then
    echo ""
    echo "Sample chunk from database:"
    echo "=================================================="
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U raguser -d ragdb -c \
        "SELECT doc_name, chunk_id, LEFT(text, 100) as sample_text 
         FROM document_chunks 
         WHERE doc_name LIKE '%${TEST_FILE}%' 
         LIMIT 1;"
    echo ""
fi
