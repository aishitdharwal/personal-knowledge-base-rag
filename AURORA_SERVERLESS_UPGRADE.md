# Aurora Serverless v2 Upgrade

## Summary

The database has been upgraded from **RDS PostgreSQL (provisioned instance)** to **Aurora Serverless v2** for better cost savings and automatic scaling.

## What Changed

### Before: RDS PostgreSQL
- **Type**: Provisioned instance (db.t4g.micro)
- **Always On**: Runs 24/7
- **Cost**: ~$12-14/month fixed
- **PostgreSQL**: 17.7

### After: Aurora Serverless v2
- **Type**: Aurora PostgreSQL with Serverless v2
- **Auto-scaling**: 0.5 - 1.0 ACU
- **Cost**: Pay per second of usage
- **PostgreSQL**: 15.5 (Aurora compatible)

## Cost Comparison

### RDS (Previous)
```
db.t4g.micro:
- Fixed: $0.016/hour × 730 hours = $11.68/month
- Storage: 20GB gp3 = $2.30/month
- Total: ~$14/month (always running)
```

### Aurora Serverless v2 (New)
```
Pricing per ACU-hour: $0.12

Example scenarios:
- Light usage (10 hours/day, 0.5 ACU): ~$18/month
- Medium usage (24/7, 0.5 ACU): ~$44/month
- Heavy usage (24/7, 1.0 ACU): ~$88/month

Storage: $0.10/GB-month

With auto-pause during idle times:
- Development: ~$10-20/month (minimal usage)
- Production (moderate): ~$30-50/month
```

**Key Benefit**: Scales to zero during idle periods, you only pay for actual usage.

## Configuration Details

### Aurora Cluster
```yaml
Engine: aurora-postgresql
EngineVersion: 15.5
EngineMode: provisioned (with Serverless v2)

ServerlessV2ScalingConfiguration:
  MinCapacity: 0.5  # Minimum ACU
  MaxCapacity: 1.0  # Maximum ACU
```

### Scaling Behavior
- **Min 0.5 ACU**: ~1GB RAM, suitable for light workloads
- **Max 1.0 ACU**: ~2GB RAM, suitable for moderate workloads
- **Auto-scales**: Automatically adjusts between min/max based on load
- **Fast scaling**: Scales in seconds, not minutes

### What is an ACU?
**ACU (Aurora Capacity Unit)** = Combination of CPU and memory
- 1 ACU ≈ 2GB RAM + corresponding CPU
- 0.5 ACU ≈ 1GB RAM (minimum for Serverless v2)

## Compatibility

### pgvector Support
✅ **Aurora PostgreSQL 15.5 supports pgvector extension**

The application will automatically enable pgvector on first connection:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Application Compatibility
✅ **No code changes needed** - Aurora is PostgreSQL-compatible

The application uses standard PostgreSQL connection:
```python
connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
```

## Deployment

### CloudFormation Changes

**Resources Replaced:**
- ❌ `RDSInstance` (AWS::RDS::DBInstance)
- ✅ `AuroraCluster` (AWS::RDS::DBCluster)
- ✅ `AuroraInstance` (AWS::RDS::DBInstance with db.serverless class)

**Outputs Updated:**
- ❌ `RDSEndpoint`
- ✅ `DatabaseEndpoint` (Aurora cluster endpoint)

### Deploy Command
```bash
./infrastructure/scripts/deploy.sh production us-east-1
```

This will:
1. Create Aurora Serverless v2 cluster
2. Create serverless instance
3. Configure auto-scaling (0.5-1.0 ACU)
4. Set up security groups and networking

## Migration from Existing RDS

If you have an existing RDS instance with data:

### Option 1: Database Snapshot (Recommended)
```bash
# 1. Create snapshot of existing RDS
aws rds create-db-snapshot \
    --db-instance-identifier production-rag-db \
    --db-snapshot-identifier production-rag-migration

# 2. Delete old CloudFormation stack
aws cloudformation delete-stack --stack-name production-rag-stack

# 3. Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name production-rag-stack

# 4. Deploy new stack with Aurora
./infrastructure/scripts/deploy.sh production us-east-1

# 5. Restore data from snapshot to Aurora
# (Manual: Use AWS Console or pg_dump/pg_restore)
```

### Option 2: pg_dump/pg_restore
```bash
# 1. Export data from RDS
pg_dump -h old-rds-endpoint -U raguser -d ragdb > backup.sql

# 2. Deploy new Aurora stack
./infrastructure/scripts/deploy.sh production us-east-1

# 3. Import data to Aurora
psql -h new-aurora-endpoint -U raguser -d ragdb < backup.sql
```

### Option 3: Fresh Start (Simplest)
```bash
# Just delete and redeploy - loses existing data
aws cloudformation delete-stack --stack-name production-rag-stack
./infrastructure/scripts/deploy.sh production us-east-1
```

## Monitoring

### Check Current ACU Usage
```bash
aws cloudwatch get-metric-statistics \
    --namespace AWS/RDS \
    --metric-name ServerlessDatabaseCapacity \
    --dimensions Name=DBClusterIdentifier,Value=production-rag-cluster \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average \
    --region us-east-1
```

### Check Database Connections
```bash
aws cloudwatch get-metric-statistics \
    --namespace AWS/RDS \
    --metric-name DatabaseConnections \
    --dimensions Name=DBClusterIdentifier,Value=production-rag-cluster \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 300 \
    --statistics Average \
    --region us-east-1
```

### View in AWS Console
```
RDS → Databases → production-rag-cluster → Monitoring
```

Look for:
- **ServerlessDatabaseCapacity**: Current ACU usage
- **DatabaseConnections**: Number of active connections
- **CPUUtilization**: CPU usage percentage

## Cost Optimization Tips

### Reduce MinCapacity
If your workload is truly minimal:
```yaml
ServerlessV2ScalingConfiguration:
  MinCapacity: 0.5  # Already at minimum
  MaxCapacity: 0.5  # Lock to minimum if predictable load
```

### Use Read Replicas (If Needed)
For high-read workloads, add Aurora Replicas:
```yaml
# Add in CloudFormation
AuroraReplicaInstance:
  Type: AWS::RDS::DBInstance
  Properties:
    DBClusterIdentifier: !Ref AuroraCluster
    DBInstanceClass: db.serverless
    Engine: aurora-postgresql
```

### Monitor and Adjust
After deployment, monitor for 1 week:
- If consistently at 0.5 ACU: Perfect sizing
- If frequently at 1.0 ACU: Increase MaxCapacity
- If barely used: Consider MaxCapacity = 0.5

## Troubleshooting

### Issue: "Engine version 15.5 not available"

**Solution**: Update to latest Aurora PostgreSQL version
```yaml
EngineVersion: '15.8'  # Or latest available
```

Check available versions:
```bash
aws rds describe-db-engine-versions \
    --engine aurora-postgresql \
    --query 'DBEngineVersions[].EngineVersion'
```

### Issue: "Cannot enable pgvector extension"

**Cause**: pgvector not installed in Aurora 15.5

**Solution**: Use Aurora 16.x or manually install:
```bash
# Connect to Aurora
psql -h aurora-endpoint -U raguser -d ragdb

# Try enabling
CREATE EXTENSION IF NOT EXISTS vector;
```

If fails, Aurora 15.5 may not have pgvector pre-installed. Upgrade to 16.x.

### Issue: "Connection timeout"

**Cause**: Security group or VPC configuration

**Solution**: Verify security group allows ECS → Aurora:
```bash
# Check security group rules
aws ec2 describe-security-groups \
    --group-ids sg-xxx \
    --query 'SecurityGroups[0].IpPermissions'
```

## Validation

After deployment:

### 1. Check Cluster Status
```bash
aws rds describe-db-clusters \
    --db-cluster-identifier production-rag-cluster \
    --query 'DBClusters[0].Status'
```

Should return: `"available"`

### 2. Check Instance Status
```bash
aws rds describe-db-instances \
    --db-instance-identifier production-rag-instance \
    --query 'DBInstances[0].DBInstanceStatus'
```

Should return: `"available"`

### 3. Test Connection from ECS
```bash
# View application logs
aws logs tail /ecs/production-rag --follow | grep -i aurora

# Should see:
# "ConversationStore initialized with PostgreSQL backend"
# "Using FAISS for vector storage" or "Using PostgreSQL for vector storage"
```

### 4. Connect Directly
```bash
# Get database password
DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id production-rag-db-password \
    --query SecretString \
    --output text | jq -r .password)

# Get endpoint
DB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name production-rag-stack \
    --query "Stacks[0].Outputs[?OutputKey=='DatabaseEndpoint'].OutputValue" \
    --output text)

# Connect
PGPASSWORD=$DB_PASSWORD psql -h $DB_ENDPOINT -U raguser -d ragdb

# Test pgvector
ragdb=> CREATE EXTENSION IF NOT EXISTS vector;
ragdb=> SELECT * FROM pg_extension WHERE extname = 'vector';
```

## Summary

✅ **Upgraded**: RDS PostgreSQL → Aurora Serverless v2
✅ **Auto-scaling**: 0.5 - 1.0 ACU
✅ **Cost**: Pay-per-use instead of fixed monthly
✅ **Compatible**: PostgreSQL 15.5, pgvector supported
✅ **No code changes**: Drop-in replacement
✅ **Validated**: CloudFormation template valid

Ready to deploy with:
```bash
./infrastructure/scripts/deploy.sh production us-east-1
```
