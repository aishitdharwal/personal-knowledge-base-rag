#!/bin/bash

# Diagnostic script to check Lambda S3 trigger configuration
# Run this to find out why Lambda isn't triggering

ENVIRONMENT=${1:-production}
REGION=${2:-ap-south-1}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="${ENVIRONMENT}-rag-docs-${ACCOUNT_ID}"
FUNCTION_NAME="${ENVIRONMENT}-rag-ingestion"

echo "=================================================="
echo "Lambda S3 Trigger Diagnostics"
echo "=================================================="
echo ""
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo "Bucket: $BUCKET"
echo "Function: $FUNCTION_NAME"
echo ""

# Check 1: S3 Bucket Notification Configuration
echo "1️⃣  Checking S3 bucket notification configuration..."
echo "=================================================="
aws s3api get-bucket-notification-configuration \
    --bucket $BUCKET \
    --region $REGION

NOTIF_COUNT=$(aws s3api get-bucket-notification-configuration \
    --bucket $BUCKET \
    --region $REGION \
    --query 'LambdaFunctionConfigurations | length(@)' \
    --output text)

if [ "$NOTIF_COUNT" == "0" ] || [ -z "$NOTIF_COUNT" ]; then
    echo ""
    echo "❌ NO S3 TRIGGER CONFIGURED!"
    echo ""
    echo "This is the problem. The S3 bucket has no Lambda trigger."
    echo ""
    echo "SOLUTION: The CloudFormation stack needs to be updated/created."
    echo "The S3 trigger is configured in the CloudFormation template."
    echo ""
else
    echo ""
    echo "✅ S3 trigger is configured ($NOTIF_COUNT notification(s))"
fi

echo ""
echo "=================================================="
echo ""

# Check 2: Lambda Function Exists
echo "2️⃣  Checking Lambda function..."
echo "=================================================="
LAMBDA_EXISTS=$(aws lambda get-function \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'Configuration.FunctionName' \
    --output text 2>/dev/null)

if [ -z "$LAMBDA_EXISTS" ]; then
    echo "❌ Lambda function does not exist!"
    echo ""
    echo "SOLUTION: Deploy the Lambda function:"
    echo "  ./infrastructure/scripts/deploy_lambda.sh $ENVIRONMENT $REGION"
else
    echo "✅ Lambda function exists: $LAMBDA_EXISTS"
    
    # Check VPC config
    VPC_CONFIG=$(aws lambda get-function-configuration \
        --function-name $FUNCTION_NAME \
        --region $REGION \
        --query 'VpcConfig' \
        --output json)
    
    echo ""
    echo "VPC Configuration:"
    echo "$VPC_CONFIG"
fi

echo ""
echo "=================================================="
echo ""

# Check 3: Lambda Permissions for S3
echo "3️⃣  Checking Lambda permissions for S3..."
echo "=================================================="
POLICY=$(aws lambda get-policy \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'Policy' \
    --output text 2>/dev/null)

if [ -z "$POLICY" ]; then
    echo "❌ No resource policy found on Lambda!"
    echo ""
    echo "SOLUTION: Lambda needs permission for S3 to invoke it."
    echo "This is typically set by CloudFormation."
else
    echo "✅ Lambda has resource policy"
    echo ""
    echo "Policy statements:"
    echo "$POLICY" | jq -r '.Statement[] | "- Principal: \(.Principal) | Action: \(.Action)"' 2>/dev/null || echo "$POLICY"
fi

echo ""
echo "=================================================="
echo ""

# Check 4: Recent Lambda Invocations
echo "4️⃣  Checking recent Lambda invocations..."
echo "=================================================="
INVOCATIONS=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Invocations \
    --dimensions Name=FunctionName,Value=$FUNCTION_NAME \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum \
    --region $REGION \
    --query 'Datapoints[0].Sum' \
    --output text)

if [ "$INVOCATIONS" == "0.0" ] || [ -z "$INVOCATIONS" ] || [ "$INVOCATIONS" == "None" ]; then
    echo "❌ No invocations in the last hour"
else
    echo "✅ Invocations in last hour: $INVOCATIONS"
fi

echo ""
echo "=================================================="
echo ""

# Check 5: CloudFormation Stack Status
echo "5️⃣  Checking CloudFormation stack..."
echo "=================================================="
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name ${ENVIRONMENT}-rag-stack \
    --region $REGION \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null)

if [ -z "$STACK_STATUS" ]; then
    echo "❌ CloudFormation stack not found!"
else
    echo "✅ Stack status: $STACK_STATUS"
    
    # Check if S3InvokeLambdaPermission exists
    echo ""
    echo "Checking for S3InvokeLambdaPermission resource..."
    PERMISSION_EXISTS=$(aws cloudformation describe-stack-resources \
        --stack-name ${ENVIRONMENT}-rag-stack \
        --region $REGION \
        --query 'StackResources[?LogicalResourceId==`S3InvokeLambdaPermission`].ResourceStatus' \
        --output text 2>/dev/null)
    
    if [ -z "$PERMISSION_EXISTS" ]; then
        echo "❌ S3InvokeLambdaPermission resource not found in stack"
    else
        echo "✅ S3InvokeLambdaPermission status: $PERMISSION_EXISTS"
    fi
fi

echo ""
echo "=================================================="
echo ""

# Summary and Recommendations
echo "📋 SUMMARY & NEXT STEPS"
echo "=================================================="
echo ""

if [ "$NOTIF_COUNT" == "0" ] || [ -z "$NOTIF_COUNT" ]; then
    echo "🔴 ROOT CAUSE: S3 bucket has no Lambda trigger configured"
    echo ""
    echo "SOLUTION:"
    echo "  1. The CloudFormation stack needs to be updated/deployed"
    echo "  2. The stack should have already created this, but it's missing"
    echo ""
    echo "QUICK FIX - Manually add S3 trigger:"
    echo ""
    echo "aws lambda add-permission \\"
    echo "  --function-name $FUNCTION_NAME \\"
    echo "  --statement-id s3-invoke \\"
    echo "  --action lambda:InvokeFunction \\"
    echo "  --principal s3.amazonaws.com \\"
    echo "  --source-arn arn:aws:s3:::$BUCKET \\"
    echo "  --region $REGION"
    echo ""
    echo "aws s3api put-bucket-notification-configuration \\"
    echo "  --bucket $BUCKET \\"
    echo "  --notification-configuration '{"
    echo "    \"LambdaFunctionConfigurations\": ["
    echo "      {"
    echo "        \"LambdaFunctionArn\": \"arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}\","
    echo "        \"Events\": [\"s3:ObjectCreated:*\"]"
    echo "      }"
    echo "    ]"
    echo "  }' \\"
    echo "  --region $REGION"
    echo ""
    echo "OR:"
    echo "  Re-deploy CloudFormation stack (recommended):"
    echo "  ./infrastructure/scripts/deploy.sh $ENVIRONMENT $REGION"
else
    echo "✅ S3 trigger appears to be configured"
    echo ""
    echo "If Lambda still isn't triggering, check:"
    echo "  1. Lambda logs for errors"
    echo "  2. Lambda execution role permissions"
    echo "  3. VPC configuration (Lambda needs internet access)"
    echo ""
    echo "View logs:"
    echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow --region $REGION"
fi

echo ""
echo "=================================================="
