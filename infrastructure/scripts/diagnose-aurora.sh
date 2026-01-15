#!/bin/bash
# Diagnostic script for Aurora Serverless v2 connectivity issues

set -e

STACK_NAME="${1:-production-rag-stack}"
REGION="${2:-us-east-1}"

echo "========================================="
echo "Aurora Serverless v2 Diagnostics"
echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo "========================================="
echo ""

# Get cluster identifier
CLUSTER_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
    --output text 2>/dev/null | cut -d'.' -f1)

if [ -z "$CLUSTER_ID" ]; then
    echo "❌ Could not find Aurora cluster in stack outputs"
    exit 1
fi

echo "✅ Cluster ID: $CLUSTER_ID"
echo ""

# Check cluster status
echo "1. Checking cluster status..."
CLUSTER_STATUS=$(aws rds describe-db-clusters \
    --db-cluster-identifier $CLUSTER_ID \
    --region $REGION \
    --query 'DBClusters[0].Status' \
    --output text 2>/dev/null)

if [ "$CLUSTER_STATUS" == "available" ]; then
    echo "   ✅ Cluster status: $CLUSTER_STATUS"
else
    echo "   ⚠️  Cluster status: $CLUSTER_STATUS (not yet available)"
fi
echo ""

# Check instance status
echo "2. Checking instance status..."
INSTANCE_STATUS=$(aws rds describe-db-instances \
    --filters "Name=db-cluster-id,Values=$CLUSTER_ID" \
    --region $REGION \
    --query 'DBInstances[0].DBInstanceStatus' \
    --output text 2>/dev/null)

if [ "$INSTANCE_STATUS" == "available" ]; then
    echo "   ✅ Instance status: $INSTANCE_STATUS"
else
    echo "   ⚠️  Instance status: $INSTANCE_STATUS (not yet available)"
fi
echo ""

# Check endpoint
echo "3. Checking cluster endpoint..."
ENDPOINT=$(aws rds describe-db-clusters \
    --db-cluster-identifier $CLUSTER_ID \
    --region $REGION \
    --query 'DBClusters[0].Endpoint' \
    --output text 2>/dev/null)

echo "   Endpoint: $ENDPOINT"
echo ""

# Check security groups
echo "4. Checking security groups..."
VPC_SG_IDS=$(aws rds describe-db-clusters \
    --db-cluster-identifier $CLUSTER_ID \
    --region $REGION \
    --query 'DBClusters[0].VpcSecurityGroups[*].VpcSecurityGroupId' \
    --output text 2>/dev/null)

echo "   Security Groups: $VPC_SG_IDS"

for SG_ID in $VPC_SG_IDS; do
    echo ""
    echo "   Security Group: $SG_ID"
    aws ec2 describe-security-groups \
        --group-ids $SG_ID \
        --region $REGION \
        --query 'SecurityGroups[0].IpPermissions[?FromPort==`5432`]' \
        --output table 2>/dev/null || echo "   ❌ Could not describe security group"
done
echo ""

# Check ECS service
echo "5. Checking ECS service..."
CLUSTER_NAME=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'StackResources[?ResourceType==`AWS::ECS::Cluster`].PhysicalResourceId' \
    --output text 2>/dev/null)

SERVICE_NAME=$(aws cloudformation describe-stack-resources \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'StackResources[?ResourceType==`AWS::ECS::Service`].PhysicalResourceId' \
    --output text 2>/dev/null | rev | cut -d'/' -f1 | rev)

if [ -n "$SERVICE_NAME" ] && [ -n "$CLUSTER_NAME" ]; then
    RUNNING_COUNT=$(aws ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --region $REGION \
        --query 'services[0].runningCount' \
        --output text 2>/dev/null)

    DESIRED_COUNT=$(aws ecs describe-services \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --region $REGION \
        --query 'services[0].desiredCount' \
        --output text 2>/dev/null)

    echo "   ECS Service: $SERVICE_NAME"
    echo "   Running: $RUNNING_COUNT / $DESIRED_COUNT tasks"
fi
echo ""

# Check recent logs
echo "6. Checking recent ECS logs..."
LOG_GROUP="/ecs/$(echo $STACK_NAME | sed 's/-stack//')"
echo "   Log Group: $LOG_GROUP"

aws logs tail $LOG_GROUP \
    --since 5m \
    --format short \
    --region $REGION 2>/dev/null | grep -i "error\|aurora\|postgres\|connection" | tail -20 || echo "   No recent logs found"
echo ""

echo "========================================="
echo "Diagnostic Summary"
echo "========================================="
echo ""
echo "If cluster/instance status is not 'available':"
echo "  - Wait 5-10 minutes for Aurora to fully initialize"
echo "  - Run this script again to check status"
echo ""
echo "If status is 'available' but connection fails:"
echo "  - Check security group rules allow Fargate → Aurora (port 5432)"
echo "  - Verify Fargate tasks have egress to 0.0.0.0/0"
echo "  - Check ECS task logs: aws logs tail $LOG_GROUP --follow"
echo ""
echo "To manually test connection from a Fargate task:"
echo "  aws ecs execute-command \\"
echo "    --cluster $CLUSTER_NAME \\"
echo "    --task <task-id> \\"
echo "    --container rag-app \\"
echo "    --interactive \\"
echo "    --command '/bin/bash'"
echo ""
