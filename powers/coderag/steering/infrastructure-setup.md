# Infrastructure Setup

Deploy the CodeRAG backend on AWS Free Tier.

## Architecture

```
[Source Code] --> [S3] --> [Ingest Lambda] --> [Codestral Embed] --> [LanceDB on S3]
                                                                          |
[MCP Tool] --> [API Gateway] --> [Query Lambda] --> [Codestral Embed] --> [LanceDB] --> [Results]
```

## Prerequisites

1. AWS account with credentials configured (`aws configure`)
2. [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
3. [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for container image builds)
4. Python 3.13+
5. Mistral API key with Codestral Embed access

## Deploy

```bash
cd D:\Dev\CodeRAG  # or wherever you cloned the repo
sam build
sam deploy --guided
```

Provide:
- **MistralApiKey**: your Mistral API key
- **Stage**: `dev`

Note outputs: `ApiUrl` and `CodeSourceBucketName`.

## Ingest Code

Upload source files to S3:

```bash
python scripts/upload-source.py <SOURCE_DIR> <BUCKET_NAME>
```

Then trigger ingestion per subfolder (async, avoids Lambda timeout):

```powershell
'{"body": "{\"prefix\": \"source/YourProject.Domain/\"}"}' | Out-File -Encoding ascii payload.json
aws lambda invoke --function-name <INGEST_FUNCTION_NAME> --invocation-type Event --payload fileb://payload.json result.json
```

Repeat for each major subfolder.

## Verify

```powershell
Invoke-RestMethod -Method POST -Uri "<API_URL>/query" -ContentType "application/json" -Body '{"question": "How does X work?", "top_k": 5}'
```

## Costs

| Service | Free Tier |
|---------|-----------|
| Lambda | 1M requests/mo |
| S3 | 5GB |
| DynamoDB | 25GB |
| API Gateway | 1M calls/mo (12 months) |
| Mistral API | Per your subscription |
