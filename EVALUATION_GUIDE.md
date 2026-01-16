# RAG System Evaluation Guide

This guide explains how to evaluate your RAG system using the RAGAS framework.

## Why RAGAS?

RAGAS (Retrieval-Augmented Generation Assessment) is a framework specifically designed for evaluating RAG systems. It provides:

- **Faithfulness**: Measures if the answer is factually consistent with the retrieved context
- **Answer Relevancy**: Measures how relevant the answer is to the question
- **Context Precision**: Measures if relevant contexts are ranked higher than irrelevant ones
- **Context Recall**: Measures if all relevant information needed to answer was retrieved
- **Answer Correctness**: Measures semantic similarity to ground truth answer

## Installation

```bash
# Install evaluation dependencies
python3 -m pip install -r requirements-eval.txt
```

## Quick Start

### 1. Evaluate with Sample Dataset

```bash
# Uses the included sample dataset
python evaluate_rag.py --endpoint http://localhost:8000
```

### 2. Evaluate with Custom Dataset

```bash
# Use your own test questions and ground truth answers
python evaluate_rag.py \
  --endpoint http://localhost:8000 \
  --test-set evaluation_dataset.json
```

### 3. Evaluate Deployed System

```bash
# Test your production deployment
python evaluate_rag.py \
  --endpoint https://your-alb-url.amazonaws.com \
  --test-set evaluation_dataset.json
```

## Creating Your Test Dataset

Create a JSON file with your test cases:

```json
[
  {
    "question": "What is the purpose of this system?",
    "ground_truth": "The expected answer that should be generated..."
  },
  {
    "question": "How does feature X work?",
    "ground_truth": "Feature X works by doing Y and Z..."
  }
]
```

**Tips for good test cases:**
- Cover different types of questions (factual, conceptual, procedural)
- Include questions that require multiple pieces of information
- Test edge cases and ambiguous queries
- Write clear, specific ground truth answers

## Understanding Results

### Score Interpretation

All metrics range from 0 to 1, where higher is better:

| Metric | Score | Interpretation |
|--------|-------|----------------|
| **Faithfulness** | > 0.8 | Excellent - Answers are factually accurate |
| | 0.6-0.8 | Good - Minor factual inconsistencies |
| | < 0.6 | Poor - Check retrieval and generation quality |
| **Answer Relevancy** | > 0.7 | Excellent - Answers directly address questions |
| | 0.5-0.7 | Good - Some irrelevant information |
| | < 0.5 | Poor - Answers often off-topic |
| **Context Precision** | > 0.7 | Excellent - Retrieval ranking is effective |
| | 0.5-0.7 | Good - Some noise in retrieved contexts |
| | < 0.5 | Poor - Improve retrieval or reranking |
| **Context Recall** | > 0.8 | Excellent - Retrieves all needed information |
| | 0.6-0.8 | Good - Misses some relevant context |
| | < 0.6 | Poor - Increase chunk size or top-k |
| **Answer Correctness** | > 0.7 | Excellent - Matches ground truth well |
| | 0.5-0.7 | Good - Semantically similar to ground truth |
| | < 0.5 | Poor - Check if knowledge base has right info |

### Example Output

```
======================================================================
RAG SYSTEM EVALUATION RESULTS
======================================================================
Timestamp: 2026-01-16 10:30:45
Endpoint: http://localhost:8000
----------------------------------------------------------------------
faithfulness............................................ 0.8523
answer_relevancy........................................ 0.7891
context_precision....................................... 0.7234
context_recall.......................................... 0.8012
answer_correctness...................................... 0.7456
======================================================================
```

## Common Issues and Solutions

### Low Faithfulness Score
**Problem**: Model generating information not in retrieved context

**Solutions**:
- Improve prompt to emphasize using only retrieved context
- Increase number of retrieved chunks (top-k)
- Check if knowledge base has accurate information

### Low Answer Relevancy
**Problem**: Answers contain irrelevant information

**Solutions**:
- Improve query rewriting to make queries more specific
- Fine-tune generation prompt to be more focused
- Check if retrieved contexts are relevant

### Low Context Precision
**Problem**: Irrelevant contexts ranked highly

**Solutions**:
- Improve embedding model quality
- Adjust chunk size and overlap
- Consider adding reranking step

### Low Context Recall
**Problem**: Not retrieving all needed information

**Solutions**:
- Increase top-k parameter (retrieve more chunks)
- Reduce chunk size to have more granular retrieval
- Improve document preprocessing

### Low Answer Correctness
**Problem**: Generated answers differ from expected answers

**Solutions**:
- Verify knowledge base contains the information
- Check if ground truth answers are too specific
- Adjust LLM model or temperature settings

## Advanced Usage

### Custom Metrics

```python
from ragas.metrics import faithfulness, answer_relevancy

# Use only specific metrics
python evaluate_rag.py \
  --endpoint http://localhost:8000 \
  --test-set evaluation_dataset.json \
  --metrics faithfulness answer_relevancy
```

### Batch Evaluation

For large test sets, the script automatically batches requests to avoid timeouts.

### Continuous Evaluation

Set up automated evaluation in CI/CD:

```bash
#!/bin/bash
# Run evaluation and fail if scores below threshold

python evaluate_rag.py \
  --endpoint $DEPLOYMENT_URL \
  --test-set evaluation_dataset.json \
  --output results.json

# Check if faithfulness > 0.7
FAITHFULNESS=$(jq -r '.metrics.faithfulness' results.json)
if (( $(echo "$FAITHFULNESS < 0.7" | bc -l) )); then
    echo "ERROR: Faithfulness score too low: $FAITHFULNESS"
    exit 1
fi
```

## Comparing Different Configurations

Run evaluations with different settings to find optimal configuration:

```bash
# Test different embedding models
python evaluate_rag.py --endpoint http://localhost:8000 --test-set eval.json --output openai-small.json
# (Switch embedding model in UI)
python evaluate_rag.py --endpoint http://localhost:8000 --test-set eval.json --output openai-large.json

# Compare results
jq -s '.' openai-small.json openai-large.json
```

## Best Practices

1. **Start Small**: Begin with 10-20 high-quality test cases
2. **Iterate**: Add test cases based on real user questions
3. **Regular Testing**: Run evaluations after changes to knowledge base or configuration
4. **Track Over Time**: Save results with timestamps to track improvements
5. **Multiple Perspectives**: Have different team members create test cases

## Resources

- **RAGAS Documentation**: https://docs.ragas.io/
- **Paper**: https://arxiv.org/abs/2309.15217
- **GitHub**: https://github.com/explodinggradients/ragas

## Troubleshooting

### OpenAI API Rate Limits
If you hit rate limits, add delays between requests or use a smaller test set.

### Memory Issues
For very large test sets, process in batches by splitting the JSON file.

### Network Timeouts
Increase timeout in the script if your RAG system takes longer to respond.

## Support

For issues with the evaluation script, check:
1. RAG system is running and accessible at the endpoint
2. OpenAI API key is set: `export OPENAI_API_KEY=your-key`
3. All dependencies installed: `pip install -r requirements-eval.txt`
