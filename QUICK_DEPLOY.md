# Quick Deployment Guide

## 🚀 One-Command Deployment

```bash
# Deploy to production
./infrastructure/scripts/deploy.sh production ap-south-1

# Validate deployment
./infrastructure/scripts/validate-deployment.sh production ap-south-1
```

## 📋 Pre-Deployment Checklist

- [ ] AWS CLI configured
- [ ] Docker installed and running
- [ ] OpenAI API key ready
- [ ] Ollama server URL (if using local LLM)

## 🎯 What Gets Deployed

### Application
- **Main Chat Page**: `http://ALB-ENDPOINT/`
- **Document Management**: `http://ALB-ENDPOINT/manage`

### Infrastructure
- VPC with 2 public subnets
- Application Load Balancer
- ECS Fargate (1-2 tasks)
- S3 bucket for documents
- Lambda for document processing
- OpenSearch for vector storage
- DynamoDB for metadata

## ✅ Post-Deployment Validation

### Automatic Validation
```bash
./infrastructure/scripts/validate-deployment.sh production us-east-1
```

### Manual Checks
```bash
# Get ALB endpoint
ALB=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ALBEndpoint`].OutputValue' \
    --output text)

# Test endpoints
curl http://${ALB}/                    # Main page
curl http://${ALB}/manage              # Document management
curl http://${ALB}/health              # Health check
curl http://${ALB}/documents           # List documents
```

## 📊 Monitor Deployment

```bash
# Watch ECS logs
aws logs tail /ecs/production-rag --follow

# Watch Lambda logs
aws logs tail /aws/lambda/production-rag-ingestion --follow

# Check service status
aws ecs describe-services \
    --cluster production-rag-cluster \
    --services production-rag-service
```

## 🔄 Update Deployment

### Update Code Only
```bash
# Rebuild and push Docker image
./infrastructure/scripts/deploy.sh production us-east-1

# Force ECS to pull new image
aws ecs update-service \
    --cluster production-rag-cluster \
    --service production-rag-service \
    --force-new-deployment
```

### Update Configuration
```bash
aws cloudformation update-stack \
    --stack-name production-rag-stack \
    --use-previous-template \
    --parameters \
        ParameterKey=OllamaURL,ParameterValue=http://NEW-IP:11434 \
        ParameterKey=EnvironmentName,UsePreviousValue=true \
        ParameterKey=OpenAIApiKey,UsePreviousValue=true \
    --capabilities CAPABILITY_IAM
```

## 🗑️ Teardown

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
    --stack-name production-rag-stack

# Wait for deletion
aws cloudformation wait stack-delete-complete \
    --stack-name production-rag-stack

# Delete ECR repository
aws ecr delete-repository \
    --repository-name production-rag \
    --force
```

## 🐛 Troubleshooting

### Deployment Fails
```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
    --stack-name production-rag-stack \
    --max-items 20

# Check stack status
aws cloudformation describe-stacks \
    --stack-name production-rag-stack
```

### Service Not Healthy
```bash
# Check ECS task status
aws ecs list-tasks \
    --cluster production-rag-cluster \
    --service-name production-rag-service

# Get task details
TASK_ARN=$(aws ecs list-tasks \
    --cluster production-rag-cluster \
    --service-name production-rag-service \
    --query 'taskArns[0]' \
    --output text)

aws ecs describe-tasks \
    --cluster production-rag-cluster \
    --tasks ${TASK_ARN}

# Check logs
aws logs tail /ecs/production-rag --follow
```

### Page Not Loading
```bash
# Check ALB target health
aws elbv2 describe-target-health \
    --target-group-arn $(aws elbv2 describe-target-groups \
        --names production-rag-tg \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text)

# Check security groups
aws ec2 describe-security-groups \
    --filters "Name=tag:Name,Values=production-rag-*"
```

## 💰 Cost Estimate

### Production (~$380/month)
- ECS Fargate (2 tasks): ~$30
- EC2 g4dn.xlarge (Ollama): ~$240
- ALB: ~$20
- OpenSearch (2 nodes): ~$70
- S3 + DynamoDB: ~$10
- Data Transfer: ~$10

### Development (~$120/month)
- ECS Fargate (1 task): ~$15
- EC2 g4dn.xlarge: ~$80
- ALB: ~$20
- OpenSearch (1 node): ~$5

### Cost Optimization
```bash
# Deploy with smaller instances
./infrastructure/scripts/deploy.sh dev us-east-1

# Or update parameters
--parameter-overrides \
    DesiredCount=1 \
    FargateTaskCPU=512 \
    FargateTaskMemory=1024
```

## 📱 Access Application

### URLs
```bash
# Get ALB endpoint
ALB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ALBEndpoint`].OutputValue' \
    --output text)

echo "Main Chat: http://${ALB_ENDPOINT}"
echo "Document Management: http://${ALB_ENDPOINT}/manage"
```

### First Steps
1. Visit `/manage` to upload documents
2. Select or drag files (txt, md, pdf)
3. Click "Upload Files"
4. Go to `/` to start chatting
5. Ask questions about your documents

## 🔐 Security Notes

- ALB is public but can be restricted via security groups
- ECS tasks run in public subnets (can be moved to private)
- OpenAI API key stored in Secrets Manager
- S3 bucket has encryption enabled
- All resources tagged with environment name

## 📞 Support

For issues:
1. Run validation script
2. Check logs
3. Review CloudFormation events
4. Check ECS service health
5. Verify security groups allow traffic

## 🎉 Success!

Your RAG system is deployed! Access it at:
- **Main Chat**: `http://ALB-ENDPOINT/`
- **Manage Docs**: `http://ALB-ENDPOINT/manage`
