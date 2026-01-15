# Deployment Updates - Document Management UI

## Summary

The system has been updated with a dedicated document management interface, separating document operations from the main chat page for better UX and organization.

## What's New

### 1. **New Route: `/manage`**
- Dedicated document management page
- Backend route added in `app/main.py:50-52`

### 2. **New Template: `manage.html`**
- Full-featured document management interface
- Located at `templates/manage.html` (40KB)
- Automatically included in Docker builds

### 3. **Updated Main Page: `index.html`**
- Simplified sidebar with "Manage Documents" button
- Shows document count badge
- Clean, focused chat interface

### 4. **New API Endpoints**
All endpoints added to `app/main.py`:
- `GET /documents/{doc_id}/details` - View document chunks (line 290)
- `GET /documents/{doc_id}/download` - Download original file (line 315)
- `POST /documents/batch-delete` - Delete multiple documents (line 339)
- `POST /upload-batch` - Upload multiple files (line 365)

## Infrastructure Changes

### Files Modified ✅
1. **Backend**:
   - `app/main.py` - Added `/manage` route and new endpoints

2. **Frontend**:
   - `templates/index.html` - Simplified with manage button
   - `templates/manage.html` - New document management page

3. **Documentation**:
   - `README.md` - Updated features and usage
   - `infrastructure/DEPLOYMENT.md` - Added UI section

4. **Scripts**:
   - `infrastructure/scripts/validate-deployment.sh` - New validation script

### Files That Don't Need Changes ✅
1. **Docker**:
   - `infrastructure/docker/Dockerfile` - Already copies `templates/` directory

2. **CloudFormation**:
   - `infrastructure/cloudformation/main.yaml` - No changes needed

3. **Deploy Script**:
   - `infrastructure/scripts/deploy.sh` - No changes needed

4. **Dependencies**:
   - `requirements.txt` - All dependencies already present

## Deployment

### Local Development
```bash
# No changes needed - just run as before
python run.py

# Access the application
Main Chat: http://localhost:8000
Document Management: http://localhost:8000/manage
```

### Docker Build (Local Test)
```bash
# Build the Docker image
cd infrastructure/docker
docker build -t rag-test:latest -f Dockerfile ../../

# Run the container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  rag-test:latest

# Test the endpoints
curl http://localhost:8000/
curl http://localhost:8000/manage
curl http://localhost:8000/health
```

### AWS Deployment
```bash
# Deploy using existing script (no changes needed)
./infrastructure/scripts/deploy.sh production us-east-1

# Validate deployment
./infrastructure/scripts/validate-deployment.sh production us-east-1
```

The deployment script automatically:
1. Builds Docker image with both templates
2. Pushes to ECR
3. Deploys CloudFormation stack
4. Updates ECS service

## Validation

### Automated Validation
```bash
# Run validation script
./infrastructure/scripts/validate-deployment.sh production us-east-1
```

Checks:
- ✓ Main page (`/`) is accessible
- ✓ Document management page (`/manage`) is accessible
- ✓ Health endpoint returns healthy status
- ✓ Documents API is working
- ✓ ECS service has desired task count

### Manual Testing
1. **Main Chat Page** (`http://ALB-ENDPOINT/`)
   - Should show "Manage Documents" button with count
   - Chat interface should work
   - Settings modal should open

2. **Document Management** (`http://ALB-ENDPOINT/manage`)
   - Should show upload area
   - Drag-and-drop should work
   - Search/filter/sort should work
   - Upload should process files
   - View/download/delete should work

## Features Available on `/manage` Page

### Upload
- ✅ Drag-and-drop files
- ✅ Select multiple files
- ✅ Batch upload
- ✅ Progress bar
- ✅ File preview before upload

### Management
- ✅ Search documents by name
- ✅ Sort by name (A-Z, Z-A) or chunks (Low-High, High-Low)
- ✅ Select all / individual selection
- ✅ Bulk delete
- ✅ View document details (all chunks)
- ✅ Download original files
- ✅ Individual document delete

### Dashboard
- ✅ Total documents count
- ✅ Total chunks count
- ✅ Selected documents count

## API Compatibility

All existing API endpoints remain unchanged:
- ✅ `POST /chat` - Chat functionality
- ✅ `POST /upload` - Single upload
- ✅ `GET /documents` - List documents
- ✅ `DELETE /documents/{id}` - Delete document
- ✅ `POST /reset` - Reset knowledge base
- ✅ `GET /health` - Health check

New endpoints are additive and don't break existing functionality.

## Rollback

If needed, rollback is simple:
```bash
# Redeploy previous CloudFormation stack version
aws cloudformation deploy \
    --template-file infrastructure/cloudformation/main.yaml \
    --stack-name production-rag-stack \
    --capabilities CAPABILITY_IAM

# Or update ECS task with previous image
aws ecs update-service \
    --cluster production-rag-cluster \
    --service production-rag-service \
    --force-new-deployment
```

## Security Considerations

- ✅ No new security groups or IAM permissions needed
- ✅ All routes use same authentication/authorization as before
- ✅ File uploads use same validation (txt, md, pdf only)
- ✅ No new external dependencies
- ✅ CORS and CSP policies unchanged

## Performance Impact

- **Minimal**: New page is similar weight to existing page
- **Bundle Size**:
  - `index.html`: ~82KB (simplified from previous)
  - `manage.html`: ~41KB (new)
  - Total: ~123KB (similar to before)
- **No Backend Changes**: Same API performance
- **No Database Changes**: Same queries and operations

## Cost Impact

**No additional costs** - uses existing infrastructure:
- Same ECS tasks
- Same Lambda functions
- Same OpenSearch cluster
- Same S3 bucket
- Same DynamoDB table

## Support

For issues or questions:
1. Check logs: `aws logs tail /ecs/production-rag --follow`
2. Run validation: `./infrastructure/scripts/validate-deployment.sh`
3. Check health: `curl http://ALB-ENDPOINT/health`

## Next Steps

1. **Deploy to staging** (if available):
   ```bash
   ./infrastructure/scripts/deploy.sh staging us-east-1
   ```

2. **Validate staging**:
   ```bash
   ./infrastructure/scripts/validate-deployment.sh staging us-east-1
   ```

3. **Deploy to production**:
   ```bash
   ./infrastructure/scripts/deploy.sh production us-east-1
   ```

4. **Monitor**:
   ```bash
   aws logs tail /ecs/production-rag --follow
   ```

5. **Notify users** of new `/manage` page for better document management
