#!/bin/bash
# Deployment validation script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ENVIRONMENT=${1:-production}
STACK_NAME="${ENVIRONMENT}-rag-stack"
AWS_REGION=${2:-us-east-1}

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Validation${NC}"
echo -e "${GREEN}Environment: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}========================================${NC}"

# Get ALB endpoint
echo -e "${YELLOW}Getting ALB endpoint...${NC}"
ALB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${AWS_REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`ALBEndpoint`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$ALB_ENDPOINT" ]; then
    echo -e "${RED}Error: Could not get ALB endpoint. Stack may not be deployed.${NC}"
    exit 1
fi

echo -e "${GREEN}ALB Endpoint: ${ALB_ENDPOINT}${NC}"

# Test main page
echo -e "${YELLOW}Testing main chat page (/)...${NC}"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${ALB_ENDPOINT}/")

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ Main page is accessible${NC}"
else
    echo -e "${RED}✗ Main page returned status: ${HTTP_STATUS}${NC}"
    exit 1
fi

# Test manage page
echo -e "${YELLOW}Testing document management page (/manage)...${NC}"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://${ALB_ENDPOINT}/manage")

if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ Document management page is accessible${NC}"
else
    echo -e "${RED}✗ Document management page returned status: ${HTTP_STATUS}${NC}"
    exit 1
fi

# Test health endpoint
echo -e "${YELLOW}Testing health endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s "http://${ALB_ENDPOINT}/health")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "$HEALTH_RESPONSE"
    exit 1
fi

# Test documents endpoint
echo -e "${YELLOW}Testing documents list endpoint...${NC}"
DOCS_RESPONSE=$(curl -s "http://${ALB_ENDPOINT}/documents")

if echo "$DOCS_RESPONSE" | grep -q "documents"; then
    echo -e "${GREEN}✓ Documents endpoint is working${NC}"
    DOC_COUNT=$(echo "$DOCS_RESPONSE" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['documents']))" 2>/dev/null || echo "0")
    echo -e "${GREEN}  Current document count: ${DOC_COUNT}${NC}"
else
    echo -e "${RED}✗ Documents endpoint failed${NC}"
    exit 1
fi

# Check ECS service
echo -e "${YELLOW}Checking ECS service status...${NC}"
CLUSTER_NAME="${ENVIRONMENT}-rag-cluster"
SERVICE_NAME="${ENVIRONMENT}-rag-service"

RUNNING_COUNT=$(aws ecs describe-services \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --region ${AWS_REGION} \
    --query 'services[0].runningCount' \
    --output text 2>/dev/null || echo "0")

DESIRED_COUNT=$(aws ecs describe-services \
    --cluster ${CLUSTER_NAME} \
    --services ${SERVICE_NAME} \
    --region ${AWS_REGION} \
    --query 'services[0].desiredCount' \
    --output text 2>/dev/null || echo "0")

if [ "$RUNNING_COUNT" = "$DESIRED_COUNT" ] && [ "$RUNNING_COUNT" != "0" ]; then
    echo -e "${GREEN}✓ ECS service is healthy (${RUNNING_COUNT}/${DESIRED_COUNT} tasks running)${NC}"
else
    echo -e "${YELLOW}⚠ ECS service status: ${RUNNING_COUNT}/${DESIRED_COUNT} tasks running${NC}"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Validation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Application URLs:${NC}"
echo -e "  Main Chat: ${GREEN}http://${ALB_ENDPOINT}${NC}"
echo -e "  Document Management: ${GREEN}http://${ALB_ENDPOINT}/manage${NC}"
echo -e "  Health Check: ${GREEN}http://${ALB_ENDPOINT}/health${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Visit the main chat page to start querying"
echo "2. Visit /manage to upload and manage documents"
echo "3. Monitor logs: aws logs tail /ecs/${ENVIRONMENT}-rag --follow --region ${AWS_REGION}"
