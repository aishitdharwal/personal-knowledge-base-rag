#!/bin/bash

# Script to package and deploy Lambda function for S3-triggered document ingestion
# Usage: ./deploy_lambda.sh [environment] [region]

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-ap-south-1}
FUNCTION_NAME="${ENVIRONMENT}-rag-ingestion"

echo "=================================================="
echo "Lambda Ingestion Pipeline Deployment"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"
echo "=================================================="
echo ""

# Create temporary directory for Lambda package
TEMP_DIR=$(mktemp -d)
echo "📁 Created temp directory: $TEMP_DIR"

# Copy Lambda function code
echo "📄 Copying Lambda function code..."
cp lambda/ingestion_function.py $TEMP_DIR/index.py

# Install dependencies using Docker for Lambda compatibility
echo "📦 Installing Python dependencies (Lambda-compatible)..."

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Using Docker to build Lambda-compatible package..."
    
    # Use AWS Lambda Python base image to install dependencies
    # Use --only-binary to avoid compilation
    docker run --rm \
        -v "$TEMP_DIR":/var/task \
        --entrypoint /bin/bash \
        public.ecr.aws/lambda/python:3.11 \
        -c "pip install --only-binary=:all: psycopg2-binary pgvector PyPDF2 openai -t /var/task --quiet --no-warn-conflicts 2>&1 || echo 'Install completed with warnings'"
    
    echo "✅ Dependencies installed via Docker"
else
    echo "Docker not available, using pip with platform-specific wheels..."
    
    # Install with platform-specific wheels for Lambda
    python3 -m pip install \
        --platform manylinux2014_x86_64 \
        --target=$TEMP_DIR \
        --implementation cp \
        --python-version 3.11 \
        --only-binary=:all: \
        --upgrade \
        psycopg2-binary \
        pgvector \
        PyPDF2 \
        openai \
        --quiet --no-warn-conflicts 2>&1 | grep -v "WARNING\|incompatible" || true
    
    echo "✅ Dependencies installed via pip"
fi

# Check if psycopg2 was installed
if [ ! -d "$TEMP_DIR/psycopg2" ]; then
    echo "⚠️  psycopg2 not found, checking for installation..."
    ls -la $TEMP_DIR | head -20
fi

# Create deployment package
echo "📦 Creating deployment package..."
cd $TEMP_DIR
zip -r9 ../lambda-package.zip . > /dev/null 2>&1
cd - > /dev/null

PACKAGE_PATH="$TEMP_DIR/../lambda-package.zip"
PACKAGE_SIZE=$(du -h $PACKAGE_PATH | cut -f1)
echo "✅ Package created: $PACKAGE_SIZE"

# Get DB password secret ARN
echo "🔍 Getting DB password secret ARN..."
DB_SECRET_ARN=$(aws secretsmanager describe-secret \
    --secret-id ${ENVIRONMENT}-rag-db-password \
    --region $REGION \
    --query 'ARN' \
    --output text 2>/dev/null)

if [ -z "$DB_SECRET_ARN" ]; then
    echo "❌ Could not find DB password secret"
    exit 1
fi

echo "✅ DB Secret ARN: $DB_SECRET_ARN"

# Get RDS endpoint
echo "🔍 Getting RDS endpoint..."
DB_HOST=$(aws cloudformation describe-stacks \
    --stack-name ${ENVIRONMENT}-rag-stack \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$DB_HOST" ]; then
    echo "❌ Could not find RDS endpoint"
    exit 1
fi

echo "✅ RDS Endpoint: $DB_HOST"

# Get API keys secret ARN
echo "🔍 Getting API keys secret ARN..."
SECRETS_ARN=$(aws secretsmanager describe-secret \
    --secret-id ${ENVIRONMENT}-rag-api-keys \
    --region $REGION \
    --query 'ARN' \
    --output text 2>/dev/null)

if [ -z "$SECRETS_ARN" ]; then
    echo "❌ Could not find API keys secret"
    exit 1
fi

echo "✅ Secrets ARN: $SECRETS_ARN"

# Update Lambda function code
echo "⬆️  Updating Lambda function code..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://$PACKAGE_PATH \
    --region $REGION \
    > /dev/null 2>&1

echo "✅ Lambda code updated"

# Wait for update to complete
echo "⏳ Waiting for update to complete..."
aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $REGION 2>/dev/null

# Update Lambda environment variables
echo "⚙️  Updating environment variables..."
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment "Variables={SECRETS_ARN=$SECRETS_ARN,DB_PASSWORD_SECRET=$DB_SECRET_ARN,DB_HOST=$DB_HOST,DB_PORT=5432,DB_NAME=ragdb,DB_USER=raguser,CHUNK_SIZE=1000,CHUNK_OVERLAP=200,EMBEDDING_PROVIDER=openai,EMBEDDING_MODEL=text-embedding-3-small}" \
    --region $REGION \
    > /dev/null 2>&1

echo "✅ Environment variables updated"

# Update Lambda execution role permissions
echo "🔐 Updating Lambda execution role permissions..."
LAMBDA_ROLE=$(aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'Role' \
    --output text 2>/dev/null)

ROLE_NAME=$(echo $LAMBDA_ROLE | awk -F'/' '{print $NF}')

# Add DB secret access
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name DBSecretAccess \
    --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"secretsmanager:GetSecretValue\",\"Resource\":\"$DB_SECRET_ARN\"}]}" \
    --region $REGION \
    > /dev/null 2>&1

echo "✅ Lambda role updated with DB secret access"

# Clean up
echo "🧹 Cleaning up..."
rm -rf $TEMP_DIR
rm -f $PACKAGE_PATH

echo ""
echo "=================================================="
echo "✅ Lambda Deployment Complete!"
echo "=================================================="
echo ""
echo "Function Name: $FUNCTION_NAME"
echo "Region: $REGION"
echo "Database: $DB_HOST"
echo ""
echo "Test the function:"
echo "  1. Upload a file to S3:"
echo "     ACCOUNT_ID=\$(aws sts get-caller-identity --query Account --output text)"
echo "     echo 'Test document' > test.txt"
echo "     aws s3 cp test.txt s3://${ENVIRONMENT}-rag-docs-\${ACCOUNT_ID}/"
echo ""
echo "  2. Check Lambda logs:"
echo "     aws logs tail /aws/lambda/$FUNCTION_NAME --follow --region $REGION"
echo ""
echo "  3. Verify in database:"
echo "     ./infrastructure/scripts/explore_db.sh $ENVIRONMENT"
echo "=================================================="
