---
name: "coderag"
displayName: "CodeRAG"
description: "Semantic code search over your project codebase using Mistral Codestral Embed and LanceDB. Query code with natural language via MCP tools."
keywords: ["code search", "rag", "codebase", "semantic search", "embeddings", "code context", "project knowledge"]
author: "Tony Thompson"
---

# CodeRAG

Serverless semantic code search. Upload your codebase, query it in natural language from any AI agent.

## Overview

CodeRAG exposes two MCP tools that let any LLM agent search your project's source code semantically:

- **search_code** - Natural language search across the entire codebase
- **search_code_in_file** - Scoped search within a specific file or directory

Backed by:
- Mistral Codestral Embed (code-optimized 1024-dim embeddings)
- LanceDB on S3 (serverless vector store)
- AWS Lambda + API Gateway (free tier eligible)

## Onboarding

### Prerequisites

1. Python 3.13+
2. A deployed CodeRAG API (see [infrastructure setup](#infrastructure-setup))
3. Your API endpoint URL (e.g. `https://xxx.execute-api.us-east-1.amazonaws.com/dev`)

### Installation

Install MCP server dependencies:

```bash
pip install "mcp[cli]>=1.9" httpx>=0.28
```

### Configuration

Set your API URL as an environment variable in the MCP config:

```json
{
  "env": {
    "CODERAG_API_URL": "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/dev"
  }
}
```

## Available MCP Tools

### search_code

Search the entire codebase for code relevant to a natural language question.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| question | string | yes | - | Natural language query |
| top_k | integer | no | 10 | Number of results (1-50) |
| file_filter | string | no | "" | Path filter (e.g. "Domain/") |

**Example:**
```
search_code(question="How does speech recognition work?", top_k=5)
search_code(question="pipeline stage execution", file_filter="Application/")
```

### search_code_in_file

Search within a specific file or directory path.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| file_path | string | yes | - | Path prefix to search within |
| question | string | yes | - | What to search for |
| top_k | integer | no | 5 | Number of results |

**Example:**
```
search_code_in_file(file_path="Trackdub.Inference/", question="ONNX session management")
```

## Common Workflows

### Query codebase for context

When an agent needs to understand how something works:
1. Call `search_code` with a natural language question
2. Results include file path, line numbers, and code text
3. Use the code context to answer the user's question

### Scoped investigation

When debugging or understanding a specific area:
1. Call `search_code_in_file` with the directory/file prefix
2. Get results only from that area of the codebase

### Multi-query research

For complex questions, make multiple searches:
1. `search_code("How does X get initialized?")`
2. `search_code("Where is X consumed?", file_filter="Application/")`
3. Synthesize results

## Available Steering Files

- **infrastructure-setup** - Deploy the CodeRAG backend (Lambda + S3 + LanceDB)

## Troubleshooting

### "No results found"
- Codebase may not be ingested yet. Run ingestion first.
- Try broader question or remove file_filter.

### Timeout on first query
- Cold start for Lambda container (~10s). Retry immediately, second call is warm.

### Results seem irrelevant
- Try more specific questions with code terminology.
- Use file_filter to narrow scope.
