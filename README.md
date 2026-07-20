# CodeRAG

Serverless RAG server for querying project code via natural language. Built on AWS Free Tier.

## Architecture

```
[Source Code] --> [S3 upload] --> [Ingest Lambda] --> [Mistral Codestral Embed] --> [LanceDB on S3]
                                                                                         |
[Agent/Model] --> [POST /query] --> [Query Lambda] --> [Mistral Embed] --> [LanceDB search] --> [Top-K chunks]
```

**Stack**: Lambda + S3 + DynamoDB + API Gateway (all Free Tier eligible)
**Embeddings**: Mistral Codestral Embed (code-optimized, 1024 dimensions)
**Vector Store**: LanceDB with S3 storage backend

## Prerequisites

1. [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
2. [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with credentials
3. Python 3.13+
4. [Mistral API key](https://console.mistral.ai/) (Codestral Embed access required)

## Deploy

```bash
# First time - guided deployment
sam build
sam deploy --guided

# Subsequent deploys
sam build && sam deploy
```

During guided deploy, provide:
- **Stack name**: `coderag`
- **Region**: `us-east-1` (or your preferred)
- **MistralApiKey**: your Mistral API key
- **Stage**: `dev`

Note the `ApiUrl` and `CodeSourceBucketName` from stack outputs.

## Ingest Code

Upload source files to S3 (triggers ingestion automatically):

```bash
# Install script dependencies
pip install boto3

# Upload Trackdub source
python scripts/upload-source.py D:\Dev\Trackdub\src <BUCKET_NAME>

# Upload docs too
python scripts/upload-source.py D:\Dev\Trackdub\docs <BUCKET_NAME> --prefix source/docs/
```

Or trigger bulk re-ingestion via API:

```bash
curl -X POST https://<API_URL>/ingest \
  -H "Content-Type: application/json" \
  -d '{"prefix": "source/"}'
```

## Query

```bash
# Install query script dependencies
pip install requests

# Search for relevant code
python scripts/query-rag.py "How does the dubbing pipeline work?" \
  --url https://<API_URL> \
  --top-k 5

# Filter to specific paths
python scripts/query-rag.py "AudioNormalization" \
  --url https://<API_URL> \
  --filter "Media/"
```

### API Reference

**POST /query**

```json
{
  "question": "How does speech recognition work?",
  "top_k": 10,
  "file_filter": "Inference/"
}
```

Response:

```json
{
  "question": "How does speech recognition work?",
  "count": 10,
  "results": [
    {
      "file_path": "Trackdub.Inference/Asr/WhisperSession.cs",
      "start_line": 45,
      "end_line": 102,
      "text": "public sealed class WhisperSession...",
      "score": 0.234
    }
  ]
}
```

## Costs (Free Tier)

| Service | Free Tier | This Project |
|---------|-----------|-------------|
| Lambda | 1M requests/mo | Well under |
| S3 | 5GB storage | ~50MB for typical codebase |
| DynamoDB | 25GB + 25 WCU/RCU | Minimal (LanceDB metadata) |
| API Gateway | 1M calls/mo (12 months) | Well under |
| **Mistral API** | Included in subscription | Codestral Embed calls |

Only cost: Mistral API usage (covered by your subscription).

## Project Structure

```
CodeRAG/
  template.yaml                    # SAM template (infra as code)
  samconfig.toml                   # Deploy config
  infrastructure/
    lambda/
      ingest/
        app.py                     # Ingest Lambda handler
        requirements.txt
      query/
        app.py                     # Query Lambda handler
        requirements.txt
  scripts/
    upload-source.py               # Upload code to S3
    query-rag.py                   # CLI query tool
```

## Using with AI Agents

Point any model/agent at the `/query` endpoint. Example for Claude/Kiro MCP config:

```json
{
  "mcpServers": {
    "coderag": {
      "url": "https://<API_URL>/query",
      "description": "Search Trackdub codebase via semantic code search"
    }
  }
}
```

Or call directly from agent prompts / function calling.
