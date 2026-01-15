#!/bin/bash

# Alternative deployment using pip download and manual packaging
# This avoids Docker compilation issues

set -e

ENVIRONMENT=${1:-production}
REGION=${2:-ap-south-1}
FUNCTION_NAME="${ENVIRONMENT}-rag-ingestion"

echo "=================================================="
echo "Lambda Ingestion Pipeline Deployment (No Docker)"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Function: $FUNCTION_NAME"
echo "=================================================="
echo ""

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo "📁 Created temp directory: $TEMP_DIR"

# Copy Lambda function
echo "📄 Copying Lambda function code..."
cp lambda/ingestion_function.py $TEMP_DIR/index.py

# Install dependencies using pip with platform-specific wheels
echo "📦 Installing dependencies (platform-specific wheels)..."

python3 -m pip install \
    --platform manylinux2014_x86_64 \
    --target=$TEMP_DIR \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    psycopg2-binary \
    2>&1 | tail -5

python3 -m pip install \
    --platform manylinux2014_x86_64 \
    --target=$TEMP_DIR \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    pgvector \
    2>&1 | tail -5

python3 -m pip install \
    --platform manylinux2014_x86_64 \
    --target=$TEMP_DIR \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    PyPDF2 \
    2>&1 | tail -5

python3 -m pip install \
    --platform manylinux2014_x86_64 \
    --target=$TEMP_DIR \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    openai \
    2>&1 | tail -5

echo "✅ Dependencies installed"

# Verify psycopg2 installation
if [ -d "$TEMP_DIR/psycopg2" ]; then
    echo "✅ psycopg2 verified"
else
    echo "❌ psycopg2 not found!"
    echo "Contents of $TEMP_DIR:"
    ls -la $TEMP_DIR | head -20
fi

# Create package
echo "📦 Creating deployment package..."
cd $TEMP_DIR
zip -r9 -q ../lambda-package.zip .
cd - > /dev/null

PACKAGE_PATH="$TEMP_DIR/../lambda-package.zip"
PACKAGE_SIZE=$(du -h $PACKAGE_PATH | cut -f1)
echo "✅ Package created: $PACKAGE_SIZE"

# Get secrets and config
echo "🔍 Getting configuration..."
DB_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id ${ENVIRONMENT}-rag-db-password --region $REGION --query 'ARN' --output text)
DB_HOST=$(aws cloudformation describe-stacks --stack-name ${ENVIRONMENT}-rag-stack --region $REGION --query 'Stacks[0].Outputs[?OutputKey==`RDSEndpoint`].OutputValue' --output text)
SECRETS_ARN=$(aws secretsmanager describe-secret --secret-id ${ENVIRONMENT}-rag-api-keys --region $REGION --query 'ARN' --output text)

echo "✅ Configuration retrieved"

# Update Lambda
echo "⬆️  Updating Lambda function..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://$PACKAGE_PATH \
    --region $REGION \
    --no-cli-pager > /dev/null

echo "✅ Lambda code updated"

echo "⏳ Waiting for update..."
aws lambda wait function-updated --function-name $FUNCTION_NAME --region $REGION

echo "⚙️  Updating environment..."
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment "Variables={SECRETS_ARN=$SECRETS_ARN,DB_PASSWORD_SECRET=$DB_SECRET_ARN,DB_HOST=$DB_HOST,DB_PORT=5432,DB_NAME=ragdb,DB_USER=raguser,CHUNK_SIZE=1000,CHUNK_OVERLAP=200,EMBEDDING_PROVIDER=openai,EMBEDDING_MODEL=text-embedding-3-small}" \
    --region $REGION \
    --no-cli-pager > /dev/null

echo "✅ Environment updated"

# Update Lambda execution role permissions
LAMBDA_ROLE=$(aws lambda get-function-configuration --function-name $FUNCTION_NAME --region $REGION --query 'Role' --output text)
ROLE_NAME=$(echo $LAMBDA_ROLE | awk -F'/' '{print $NF}')

aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name DBSecretAccess \
    --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"secretsmanager:GetSecretValue\",\"Resource\":\"$DB_SECRET_ARN\"}]}" \
    > /dev/null

# Add Textract permissions for OCR
aws iam put-role-policy \
    --role-name $ROLE_NAME \
    --policy-name TextractAccess \
    --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["textract:DetectDocumentText","textract:AnalyzeDocument"],"Resource":"*"}]}' \
    > /dev/null

echo "✅ IAM permissions updated"

# Cleanup
rm -rf $TEMP_DIR $PACKAGE_PATH

echo ""
echo "=================================================="
echo "✅ Deployment Complete!"
echo "=================================================="
echo ""
echo "Test:"
echo "  aws s3 cp test.txt s3://production-rag-docs-265402432236/"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
