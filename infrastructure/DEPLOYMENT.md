# AWS Deployment Guide

## Architecture

### Simplified Architecture

The system has been streamlined to use **PostgreSQL RDS only** with integrated web-based document management:

**Web Application** (ECS Fargate):
- **Main Chat Page** (`/`) - Query documents with conversation history sidebar
- **Document Management** (`/manage`) - Upload, view, and manage documents directly in browser

**Data Storage** (PostgreSQL RDS):
- **Document Embeddings**: pgvector extension for semantic search
- **Conversation History**: Persistent storage across deployments
- **Metadata**: Document and chunk information

**Complete Flow**:
```
User → ALB → ECS Fargate Container
         ↓
    FastAPI Application
         ↓
   ┌─────┴─────┐
   ↓           ↓
RDS (pgvector)  Ollama (Optional SLM)
   ↓
OpenAI API (Embeddings + LLM)
```

**Key Benefits**:
- ✅ **No S3 + Lambda complexity**: Documents uploaded directly through web UI
- ✅ **No DynamoDB**: Everything in PostgreSQL for simplicity
- ✅ **Unified interface**: All operations in one place
- ✅ **Cost-effective**: Fewer services = lower AWS costs (~$14/month for RDS only)
- ✅ **Easier to debug**: Single application to monitor

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Docker installed
3. OpenAI API Key

## Quick Deploy

```bash
# Make script executable
chmod +x infrastructure/scripts/deploy.sh

# Deploy to production
./infrastructure/scripts/deploy.sh production us-east-1

# Deploy to dev
./infrastructure/scripts/deploy.sh dev us-east-1
```

## Manual Deployment Steps

### 1. Create ECR Repository

```bash
aws ecr create-repository --repository-name production-rag --region us-east-1
```

### 2. Build and Push Docker Image

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
cd infrastructure/docker
docker build -t production-rag:latest -f Dockerfile ../../

# Tag and push
docker tag production-rag:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/production-rag:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/production-rag:latest
```

### 3. Package Lambda Function

```bash
cd infrastructure/lambda/ingestion
pip install -r requirements.txt -t .
zip -r lambda-package.zip .
aws s3 cp lambda-package.zip s3://your-lambda-bucket/
```

### 4. Deploy CloudFormation Stack

```bash
aws cloudformation deploy \
    --template-file infrastructure/cloudformation/main.yaml \
    --stack-name production-rag-stack \
    --parameter-overrides \
        EnvironmentName=production \
        OpenAIApiKey=sk-your-key \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

## Configuration

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| EnvironmentName | production | Environment (dev/staging/production) |
| OpenAIApiKey | (required) | OpenAI API key |
| EC2InstanceType | g4dn.xlarge | GPU instance for SLM |
| FargateTaskCPU | 1024 | Fargate CPU (1 vCPU) |
| FargateTaskMemory | 2048 | Fargate memory (2GB) |
| DesiredCount | 2 | Number of Fargate tasks |

### Cost Optimization

**Development**:
```bash
# Use smaller instances
--parameter-overrides \
    EC2InstanceType=g4dn.xlarge \
    DesiredCount=1 \
    FargateTaskCPU=512 \
    FargateTaskMemory=1024
```

**Production**:
```bash
# Scale up for performance
--parameter-overrides \
    EC2InstanceType=g4dn.2xlarge \
    DesiredCount=3 \
    FargateTaskCPU=2048 \
    FargateTaskMemory=4096
```

## Post-Deployment Setup

### Initialize Conversations Table

The conversations table is automatically created by the application on first startup. However, you can manually initialize it if needed:

```bash
# Get RDS endpoint from CloudFormation outputs
RDS_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query "Stacks[0].Outputs[?OutputKey=='RDSEndpoint'].OutputValue" \
    --output text)

# Get DB password from Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id production-rag-db-password \
    --query SecretString \
    --output text | jq -r .password)

# Run migration script
PGPASSWORD=$DB_PASSWORD psql \
    -h $RDS_ENDPOINT \
    -U raguser \
    -d ragdb \
    -f infrastructure/scripts/init-conversations-db.sql
```

### Verify Conversation Storage

Check that conversations are being stored in PostgreSQL:

```bash
# Connect to RDS
PGPASSWORD=$DB_PASSWORD psql -h $RDS_ENDPOINT -U raguser -d ragdb

# List conversations
SELECT conversation_id, title, updated_at FROM conversations ORDER BY updated_at DESC LIMIT 10;

# Count total conversations
SELECT COUNT(*) FROM conversations;

# Exit psql
\q
```

## Usage

### Access Application

```bash
# Get ALB endpoint
ALB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query 'Stacks[0].Outputs[?OutputKey==`ALBEndpoint`].OutputValue' \
    --output text)

# Open in browser
echo "Main Chat Page: http://${ALB_ENDPOINT}"
echo "Document Management: http://${ALB_ENDPOINT}/manage"
```

### Web Interface

The application provides two main pages:

1. **Main Chat Page** (`/`)
   - Clean, focused interface for chatting with documents
   - "Manage Documents" button with document count badge
   - Conversation history and settings
   - Source citations with each answer

2. **Document Management Page** (`/manage`)
   - Upload documents (drag-and-drop or file select)
   - Batch upload multiple files
   - Search and filter documents by name
   - Sort by name or chunk count
   - Bulk select and delete
   - View document details (all chunks)
   - Download original files
   - Statistics dashboard (total docs, chunks, selected)

**Navigation**: Click "📚 Manage Documents" button on main page, or visit `/manage` directly

### Monitor

```bash
# View ECS logs
aws logs tail /ecs/production-rag --follow

# View Lambda logs
aws logs tail /aws/lambda/production-rag-ingestion --follow

# Check OpenSearch health
aws opensearch describe-domain --domain-name production-rag-vectors
```

## Infrastructure Components

### Networking
- **VPC**: 10.0.0.0/16
- **Public Subnets**: 2 (for ALB)
- **Private Subnets**: 2 (for Fargate, Lambda, OpenSearch, EC2)
- **NAT Gateways**: 2 (high availability)

### Storage
- **S3**: Document storage
- **OpenSearch**: Vector database (2 nodes, t3.small.search)
- **DynamoDB**: Metadata (on-demand billing)

### Compute
- **Lambda**: Ingestion pipeline (3GB memory, 15min timeout)
- **ECS Fargate**: Web application (2 tasks, 1vCPU, 2GB each)
- **EC2**: SLM server (g4dn.xlarge with GPU)

### Security
- **Secrets Manager**: API keys
- **Security Groups**: Isolated network access
- **IAM Roles**: Least privilege access
- **VPC**: Private subnets for sensitive resources

## Estimated Costs

### Monthly Costs (Production)

| Resource | Specs | Est. Cost |
|----------|-------|-----------|
| EC2 (SLM) | g4dn.xlarge (24/7) | ~$190 |
| ECS Fargate | 2 tasks (1vCPU, 2GB) | ~$30 |
| OpenSearch | 2x t3.small.search | ~$70 |
| NAT Gateway | 2 gateways | ~$65 |
| ALB | Standard | ~$20 |
| S3 + DynamoDB | Light usage | ~$5 |
| **Total** | | **~$380/month** |

### Cost Optimization

**Development** (~$120/month):
- EC2: t3.medium ($30)
- Fargate: 1 task ($15)
- OpenSearch: 1x t3.small.search ($35)
- NAT: 1 gateway ($33)
- Others: ~$7

**Spot Instances** (Save ~70% on EC2):
```bash
# Modify CloudFormation template to use Spot instances
```

## Troubleshooting

### Lambda Timeouts
```bash
# Increase timeout in CloudFormation
Timeout: 900  # 15 minutes
```

### Fargate Out of Memory
```bash
# Increase memory
--parameter-overrides FargateTaskMemory=4096
```

### OpenSearch Performance
```bash
# Scale up instance type
InstanceType: t3.medium.search
```

### SLM Connection Issues
```bash
# Check security group allows Fargate → EC2:8080
# Check EC2 instance is running
aws ec2 describe-instances --instance-ids <instance-id>
```

## Cleanup

```bash
# Delete stack
aws cloudformation delete-stack --stack-name production-rag-stack

# Delete ECR repository
aws ecr delete-repository --repository-name production-rag --force

# Empty and delete S3 buckets
aws s3 rm s3://bucket-name --recursive
aws s3 rb s3://bucket-name
```

## Next Steps

1. **Custom Domain**: Add Route53 + ACM certificate for HTTPS
2. **CI/CD**: Set up GitHub Actions for automated deployments  
3. **Monitoring**: Add CloudWatch dashboards and alarms
4. **Backup**: Enable automated backups for DynamoDB and OpenSearch
5. **WAF**: Add Web Application Firewall for security
6. **Auto-scaling**: Configure ECS auto-scaling policies

## Support

For issues or questions:
1. Check CloudWatch Logs
2. Review stack events in CloudFormation console
3. Verify security group rules
4. Check IAM permissions
