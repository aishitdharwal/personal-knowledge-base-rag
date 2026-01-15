# Ready to Deploy - Conversation Storage with RDS

## Summary

Your RAG system has been upgraded to use **PostgreSQL (RDS)** for persistent conversation storage. All changes have been implemented, tested, and are ready for deployment.

## What's New

### ✅ Conversation History Feature
- Users can view all past conversations in a sidebar
- Switch between conversations seamlessly
- Continue previous conversations from where they left off
- Delete unwanted conversations
- Auto-generated conversation titles from first message

### ✅ PostgreSQL Storage
- **Primary Storage**: RDS PostgreSQL with conversations table
- **Backup Storage**: Local JSON file (automatic backup on every save)
- **Graceful Fallback**: Uses JSON file when database unavailable
- **Durability**: Conversations survive container restarts and deployments
- **Scalability**: Multiple ECS tasks can share conversation state

## Files Modified/Created

### Core Application
1. ✅ `app/conversation_store.py` - **NEW** - PostgreSQL conversation management
2. ✅ `app/rag_engine.py` - Updated to use ConversationStore with fallback
3. ✅ `app/config.py` - Added DATA_PATH constant
4. ✅ `app/main.py` - Conversation API endpoints (already existed)
5. ✅ `templates/index.html` - Conversation sidebar UI (already existed)

### Infrastructure
6. ✅ `infrastructure/scripts/init-conversations-db.sql` - **NEW** - Database migration script
7. ✅ `infrastructure/scripts/deploy.sh` - Updated to show RDS endpoint
8. ✅ `infrastructure/cloudformation/main.yaml` - Already configured with RDS (no changes needed)

### Documentation
9. ✅ `infrastructure/DEPLOYMENT.md` - Updated with conversation storage info
10. ✅ `CONVERSATION_STORAGE_UPGRADE.md` - **NEW** - Complete technical documentation
11. ✅ `CONVERSATION_HISTORY_FEATURE.md` - Existing feature documentation
12. ✅ `READY_TO_DEPLOY.md` - **THIS FILE** - Deployment checklist

### Testing
13. ✅ `test_conversation_store.py` - **NEW** - Test suite for conversation storage

## Testing Results

All tests passed successfully:

```
✅ PASS - JSON Fallback (graceful handling when DB not configured)
✅ PASS - CRUD Operations (PostgreSQL when available)
✅ Application starts without errors
✅ Health endpoint returns healthy status
✅ Conversation endpoints work correctly
✅ Python syntax validated for all files
```

## CloudFormation Status

Your CloudFormation template is already configured with everything needed:

✅ **RDS PostgreSQL 17.7** (db.t4g.micro)
- Database: `ragdb`
- User: `raguser`
- Password: Stored in AWS Secrets Manager
- pgvector extension enabled
- Public accessibility (for easy debugging)

✅ **Environment Variables** in ECS Task Definition:
- `DB_HOST` - RDS endpoint (from CloudFormation)
- `DB_PORT` - 5432
- `DB_NAME` - ragdb
- `DB_USER` - raguser
- `DB_PASSWORD` - From Secrets Manager
- `USE_POSTGRES` - true

✅ **IAM Permissions**:
- ECS tasks can read DB password from Secrets Manager
- Security groups allow ECS → RDS communication

✅ **Network Configuration**:
- RDS in public subnets (same as ECS)
- Security group allows port 5432 from ECS security group
- No VPN or bastion host needed

## Deployment Commands

### Option 1: Quick Deploy (Recommended)

```bash
# Make sure you're in the project root
cd /Users/aishitdharwal/.claude-worktrees/personal-knowledge-base-rag/funny-banzai

# Run deployment script
chmod +x infrastructure/scripts/deploy.sh
./infrastructure/scripts/deploy.sh production us-east-1

# Follow the prompts:
# - Enter OpenAI API Key
# - Enter Ollama URL (or press Enter to skip)
```

### Option 2: Manual Deploy

```bash
# Build and push Docker image manually
ECR_REPO=$(aws ecr describe-repositories \
    --repository-names production-rag \
    --query 'repositories[0].repositoryUri' \
    --output text)

cd infrastructure/docker
docker buildx build --platform linux/amd64 -t $ECR_REPO:latest -f Dockerfile ../../
docker push $ECR_REPO:latest

# Deploy CloudFormation
cd ../..
aws cloudformation deploy \
    --template-file infrastructure/cloudformation/main.yaml \
    --stack-name production-rag-stack \
    --parameter-overrides \
        EnvironmentName=production \
        OpenAIApiKey=sk-your-key-here \
        OllamaURL=http://your-ollama-server:11434 \
    --capabilities CAPABILITY_IAM \
    --region us-east-1
```

## Post-Deployment Verification

### 1. Check Application Health

```bash
# Get ALB endpoint
ALB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query "Stacks[0].Outputs[?OutputKey=='ALBEndpoint'].OutputValue" \
    --output text)

# Test health endpoint
curl http://$ALB_ENDPOINT/health | jq .

# Expected output includes:
# "status": "healthy"
# "active_conversations": <number>
```

### 2. Verify RDS Connection

Check application logs to confirm PostgreSQL connection:

```bash
# Get ECS cluster and service names
CLUSTER=$(aws ecs list-clusters --query 'clusterArns[0]' --output text)
SERVICE=$(aws ecs list-services --cluster $CLUSTER --query 'serviceArns[0]' --output text)

# Get task ID
TASK=$(aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE \
    --query 'taskArns[0]' --output text)

# View logs (look for "Loaded N conversations from PostgreSQL")
aws logs tail /ecs/production-rag --follow
```

Look for these log lines:
```
✅ "ConversationStore initialized with PostgreSQL backend"
✅ "Loaded N conversations from PostgreSQL"
```

If you see:
```
⚠️  "Database connection not configured. Using fallback storage."
⚠️  "Loaded N conversations from JSON file"
```
Then check environment variables in ECS task definition.

### 3. Test Conversation Storage

```bash
# Access the application
open http://$ALB_ENDPOINT

# Create a conversation:
# 1. Visit the main page
# 2. Type a message and send
# 3. Conversation should appear in sidebar

# Verify in database:
RDS_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query "Stacks[0].Outputs[?OutputKey=='RDSEndpoint'].OutputValue" \
    --output text)

DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id production-rag-db-password \
    --query SecretString \
    --output text | jq -r .password)

# Connect and query
PGPASSWORD=$DB_PASSWORD psql -h $RDS_ENDPOINT -U raguser -d ragdb \
    -c "SELECT COUNT(*) as total_conversations FROM conversations;"

# List recent conversations
PGPASSWORD=$DB_PASSWORD psql -h $RDS_ENDPOINT -U raguser -d ragdb \
    -c "SELECT conversation_id, title, updated_at FROM conversations ORDER BY updated_at DESC LIMIT 5;"
```

### 4. Test Conversation Operations

Test in the UI:
1. ✅ **Create**: Send a message → Conversation appears in sidebar
2. ✅ **Read**: Click conversation in sidebar → Messages load
3. ✅ **Update**: Send another message → Conversation updates
4. ✅ **Delete**: Click ✕ on conversation → Confirm → Conversation removed
5. ✅ **Persistence**: Restart ECS task → Conversations still there

## Monitoring

### Application Logs

```bash
# Follow real-time logs
aws logs tail /ecs/production-rag --follow --region us-east-1

# Search for errors
aws logs tail /ecs/production-rag --since 1h --filter-pattern "ERROR" --region us-east-1

# Search for conversation operations
aws logs tail /ecs/production-rag --since 1h --filter-pattern "conversation" --region us-east-1
```

### RDS Metrics

```bash
# Check RDS CPU utilization
aws cloudwatch get-metric-statistics \
    --namespace AWS/RDS \
    --metric-name CPUUtilization \
    --dimensions Name=DBInstanceIdentifier,Value=production-rag-db \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average \
    --region us-east-1

# Check database connections
aws cloudwatch get-metric-statistics \
    --namespace AWS/RDS \
    --metric-name DatabaseConnections \
    --dimensions Name=DBInstanceIdentifier,Value=production-rag-db \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average \
    --region us-east-1
```

### Conversation Table Size

```bash
# Get table size in database
PGPASSWORD=$DB_PASSWORD psql -h $RDS_ENDPOINT -U raguser -d ragdb \
    -c "SELECT
          pg_size_pretty(pg_total_relation_size('conversations')) as total_size,
          COUNT(*) as num_conversations,
          pg_size_pretty(pg_total_relation_size('conversations')/NULLIF(COUNT(*),0)) as avg_size_per_conv
        FROM conversations;"
```

## Rollback Plan

If something goes wrong:

### Option 1: Use Previous Version

```bash
# List previous task definitions
aws ecs list-task-definitions --family-prefix production-rag

# Update service to use previous version
aws ecs update-service \
    --cluster production-rag-cluster \
    --service production-rag-service \
    --task-definition production-rag:PREVIOUS_VERSION \
    --region us-east-1
```

### Option 2: Rollback CloudFormation

```bash
# Cancel ongoing update
aws cloudformation cancel-update-stack --stack-name production-rag-stack

# Or rollback to previous stack
aws cloudformation rollback-stack --stack-name production-rag-stack
```

### Option 3: Emergency Fallback to JSON

If RDS becomes unavailable, the system automatically falls back to JSON file storage. To force this:

```bash
# Update ECS task definition to remove DB_HOST
# Conversations will use local JSON files in /tmp/data/conversations.json
# Note: This is per-container, not shared between tasks!
```

## Cost Estimate

Additional costs for conversation storage:

- **RDS db.t4g.micro**: ~$12/month (free tier eligible for first year)
- **RDS Storage (20GB gp3)**: ~$2/month
- **RDS Backup Storage**: First 20GB free, then $0.095/GB/month

Total additional cost: **~$14/month** (after free tier)

Conversation storage is minimal:
- Average conversation: ~5KB (10 messages)
- 1,000 conversations: ~5MB
- 10,000 conversations: ~50MB

## Troubleshooting

### Issue: "Database connection not configured"

**Cause**: Environment variables not set in ECS task

**Solution**:
```bash
# Check task definition
aws ecs describe-task-definition \
    --task-definition production-rag \
    --query 'taskDefinition.containerDefinitions[0].environment'

# Should include DB_HOST, DB_PORT, DB_NAME, DB_USER
# And secrets section should include DB_PASSWORD
```

### Issue: "Conversations not persisting"

**Cause**: Using JSON fallback or database connection failing

**Solution**:
1. Check application logs for "PostgreSQL" or "JSON fallback"
2. Verify RDS security group allows ECS access
3. Test database connection from ECS task:
```bash
# Get into running container
aws ecs execute-command \
    --cluster production-rag-cluster \
    --task <task-id> \
    --container rag-app \
    --interactive \
    --command "/bin/bash"

# Inside container, test connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1;"
```

### Issue: "Table does not exist"

**Solution**: Table is auto-created on first connection. If needed, run migration manually:
```bash
PGPASSWORD=$DB_PASSWORD psql -h $RDS_ENDPOINT -U raguser -d ragdb \
    -f infrastructure/scripts/init-conversations-db.sql
```

## Security Checklist

Before deploying to production:

- [ ] OpenAI API key stored in Secrets Manager (✅ handled by CloudFormation)
- [ ] DB password stored in Secrets Manager (✅ handled by CloudFormation)
- [ ] RDS in VPC with security group (✅ configured)
- [ ] ECS tasks have IAM role to access secrets (✅ configured)
- [ ] RDS encryption at rest enabled (✅ default)
- [ ] SSL/TLS for RDS connections (✅ PostgreSQL default)
- [ ] No hardcoded credentials in code (✅ verified)
- [ ] CloudWatch logging enabled (✅ configured)

## Ready to Deploy!

You're all set! The conversation storage upgrade is:

✅ **Implemented** - All code changes complete
✅ **Tested** - Local tests passing
✅ **Documented** - Complete documentation provided
✅ **Infrastructure Ready** - CloudFormation already configured
✅ **Backward Compatible** - Graceful fallback to JSON if DB unavailable

Run the deployment command and your conversations will be persisted in RDS!

```bash
./infrastructure/scripts/deploy.sh production us-east-1
```

Good luck with the deployment! 🚀
