# RAG Pipeline with RAXE

Secure RAG pipeline with multi-stage security scanning.

## Features

- Query scanning before retrieval
- Context scanning after retrieval
- Response scanning before returning
- Security metadata in responses

## Security Checkpoints

1. **User Query**: Scan for prompt injection
2. **Retrieved Context**: Validate document content
3. **Generated Response**: Scan for data leakage

## Usage

```bash
pip install raxe
python rag_with_raxe.py
```

## Integration

```python
rag = SecureRAGPipeline(documents)
result = rag.query("Your question")

if not result.get('blocked'):
    print(result['response'])
    print(result['security'])  # Security scan details
```

## Learn More

[RAXE Documentation](https://docs.raxe.ai)
