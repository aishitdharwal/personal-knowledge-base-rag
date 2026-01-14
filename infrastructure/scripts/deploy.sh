#!/bin/bash
# Deployment script for RAG system to AWS (Simplified)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
AWS_REGION=${2:-us-east-1}
STACK_NAME="${ENVIRONMENT}-rag-stack"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}RAG System Deployment${NC}"
echo -e "${GREEN}Environment: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}Region: ${AWS_REGION}${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Prompt for OpenAI API Key
read -sp "Enter OpenAI API Key: " OPENAI_API_KEY
echo

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}Error: OpenAI API Key is required${NC}"
    exit 1
fi

# Prompt for Ollama URL
read -p "Enter Ollama URL (e.g., http://10.0.1.100:11434): " OLLAMA_URL
echo

if [ -z "$OLLAMA_URL" ]; then
    echo -e "${YELLOW}Warning: No Ollama URL provided, using default${NC}"
    OLLAMA_URL="http://localhost:11434"
fi

# Create ECR repository if it doesn't exist
echo -e "${YELLOW}Creating ECR repository...${NC}"
aws ecr create-repository \
    --repository-name ${ENVIRONMENT}-rag \
    --region ${AWS_REGION} \
    2>/dev/null || echo "Repository already exists"

# Get ECR repository URI
ECR_REPO=$(aws ecr describe-repositories \
    --repository-names ${ENVIRONMENT}-rag \
    --region ${AWS_REGION} \
    --query 'repositories[0].repositoryUri' \
    --output text)

echo -e "${GREEN}ECR Repository: ${ECR_REPO}${NC}"

# Login to ECR
echo -e "${YELLOW}Logging in to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${ECR_REPO}

# Build Docker image for linux/amd64 platform (cross-platform build for Mac ARM -> Linux x86)
echo -e "${YELLOW}Building Docker image for linux/amd64...${NC}"
cd infrastructure/docker
docker buildx build --platform linux/amd64 -t ${ENVIRONMENT}-rag:latest -f Dockerfile ../../ --load

# Tag and push image
echo -e "${YELLOW}Pushing Docker image to ECR...${NC}"
docker tag ${ENVIRONMENT}-rag:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest

cd ../..

# Package Lambda function
echo -e "${YELLOW}Packaging Lambda function...${NC}"
cd infrastructure/lambda/ingestion
python3 -m pip install -r requirements.txt -t . 2>/dev/null || true
zip -r ../../../lambda-package.zip . -x "*.pyc" -x "__pycache__/*" 2>/dev/null || true
cd ../../..

# Upload Lambda package to S3 (optional, using inline code for now)
# Skipping S3 upload since we're using inline code in CloudFormation

# Deploy CloudFormation stack
echo -e "${YELLOW}Deploying CloudFormation stack...${NC}"
aws cloudformation deploy \
    --template-file infrastructure/cloudformation/main.yaml \
    --stack-name ${STACK_NAME} \
    --parameter-overrides \
        EnvironmentName=${ENVIRONMENT} \
        OpenAIApiKey=${OPENAI_API_KEY} \
        OllamaURL=${OLLAMA_URL} \
    --capabilities CAPABILITY_IAM \
    --region ${AWS_REGION}

# Get stack outputs
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

ALB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`ALBEndpoint`].OutputValue' \
    --output text)

S3_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`DocumentsBucketName`].OutputValue' \
    --output text)

echo -e "${GREEN}Application URL: http://${ALB_ENDPOINT}${NC}"
echo -e "${GREEN}Upload documents to: s3://${S3_BUCKET}${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Upload documents: aws s3 cp your-document.pdf s3://${S3_BUCKET}/"
echo "2. Access the application: http://${ALB_ENDPOINT}"
echo "3. Monitor logs: aws logs tail /ecs/${ENVIRONMENT}-rag --follow --region ${AWS_REGION}"
echo ""
echo -e "${YELLOW}Update Ollama URL later:${NC}"
echo "aws cloudformation update-stack \\"
echo "  --stack-name ${STACK_NAME} \\"
echo "  --use-previous-template \\"
echo "  --parameters \\"
echo "    ParameterKey=OllamaURL,ParameterValue=http://NEW-IP:11434 \\"
echo "    ParameterKey=EnvironmentName,UsePreviousValue=true \\"
echo "    ParameterKey=OpenAIApiKey,UsePreviousValue=true \\"
echo "  --capabilities CAPABILITY_IAM \\"
echo "  --region ${AWS_REGION}"
