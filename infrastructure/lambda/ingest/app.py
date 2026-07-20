"""
CodeRAG Ingest Lambda

Reads code files from S3, chunks them intelligently by function/class boundaries,
embeds via Mistral Codestral Embed, stores vectors in LanceDB (S3 + DynamoDB backend).

Triggers:
  - S3 ObjectCreated events (prefix: source/)
  - POST /ingest API endpoint (body: {"bucket": "...", "prefix": "source/"})
"""

import json
import os
import re
import logging
from typing import Any

import boto3
import lancedb
import pyarrow as pa
from mistralai import Mistral

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration ---
MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]
LANCEDB_BUCKET = os.environ["LANCEDB_BUCKET"]
EMBED_MODEL = "codestral-embed-2505"
EMBED_DIMENSIONS = 1024
OUTPUT_DIMENSION = 1024  # Fixed output dimension for consistent vectors
TABLE_NAME = "code_chunks"
MAX_CHUNK_TOKENS = 512  # approximate max tokens per chunk
SUPPORTED_EXTENSIONS = {
    ".cs", ".md", ".yaml", ".yml", ".json", ".xml",
    ".csproj", ".sln", ".props", ".targets", ".axaml",
    ".py", ".ts", ".js", ".sh", ".ps1", ".toml",
}

# --- Clients ---
s3_client = boto3.client("s3")
mistral_client = Mistral(api_key=MISTRAL_API_KEY)


def get_lancedb():
    """Connect to LanceDB with S3 storage."""
    storage_options = {
        "aws_default_region": os.environ.get("AWS_REGION", "us-east-1"),
    }
    db_uri = f"s3://{LANCEDB_BUCKET}/lancedb"
    return lancedb.connect(db_uri, storage_options=storage_options)


def chunk_code(content: str, file_path: str, max_lines: int = 60) -> list[dict]:
    """
    Chunk code by logical boundaries (functions, classes, sections).
    Falls back to sliding window of max_lines with overlap.
    """
    lines = content.split("\n")
    chunks = []

    # For C# files, try to split on class/method boundaries
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".cs", ".py", ".ts", ".js"):
        chunks = _chunk_by_scope(lines, file_path, max_lines)
    elif ext == ".md":
        chunks = _chunk_markdown(lines, file_path, max_lines)
    else:
        chunks = _chunk_sliding_window(lines, file_path, max_lines)

    return chunks


def _chunk_by_scope(lines: list[str], file_path: str, max_lines: int) -> list[dict]:
    """Split source code at class/function boundaries."""
    # Patterns that indicate a new logical block
    boundary_pattern = re.compile(
        r"^\s*(public|private|protected|internal|static|sealed|abstract|async|partial|override|virtual|"
        r"def |class |interface |enum |record |struct |namespace |function |const |export )",
        re.IGNORECASE,
    )

    chunks = []
    current_chunk_lines: list[str] = []
    chunk_start_line = 1

    for i, line in enumerate(lines, start=1):
        if (
            boundary_pattern.match(line)
            and len(current_chunk_lines) >= 10
        ):
            # Save current chunk if it has content
            if current_chunk_lines:
                chunk_text = "\n".join(current_chunk_lines)
                if chunk_text.strip():
                    chunks.append({
                        "text": chunk_text,
                        "file_path": file_path,
                        "start_line": chunk_start_line,
                        "end_line": i - 1,
                    })
            current_chunk_lines = [line]
            chunk_start_line = i
        else:
            current_chunk_lines.append(line)

        # Force split if chunk too large
        if len(current_chunk_lines) >= max_lines:
            chunk_text = "\n".join(current_chunk_lines)
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "file_path": file_path,
                    "start_line": chunk_start_line,
                    "end_line": i,
                })
            current_chunk_lines = []
            chunk_start_line = i + 1

    # Final chunk
    if current_chunk_lines:
        chunk_text = "\n".join(current_chunk_lines)
        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "file_path": file_path,
                "start_line": chunk_start_line,
                "end_line": len(lines),
            })

    return chunks


def _chunk_markdown(lines: list[str], file_path: str, max_lines: int) -> list[dict]:
    """Split markdown at heading boundaries."""
    chunks = []
    current_chunk_lines: list[str] = []
    chunk_start_line = 1

    for i, line in enumerate(lines, start=1):
        if line.startswith("#") and current_chunk_lines:
            chunk_text = "\n".join(current_chunk_lines)
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "file_path": file_path,
                    "start_line": chunk_start_line,
                    "end_line": i - 1,
                })
            current_chunk_lines = [line]
            chunk_start_line = i
        else:
            current_chunk_lines.append(line)

        if len(current_chunk_lines) >= max_lines:
            chunk_text = "\n".join(current_chunk_lines)
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "file_path": file_path,
                    "start_line": chunk_start_line,
                    "end_line": i,
                })
            current_chunk_lines = []
            chunk_start_line = i + 1

    if current_chunk_lines:
        chunk_text = "\n".join(current_chunk_lines)
        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "file_path": file_path,
                "start_line": chunk_start_line,
                "end_line": len(lines),
            })

    return chunks


def _chunk_sliding_window(
    lines: list[str], file_path: str, max_lines: int, overlap: int = 10
) -> list[dict]:
    """Simple sliding window chunking with overlap."""
    chunks = []
    i = 0
    while i < len(lines):
        end = min(i + max_lines, len(lines))
        chunk_text = "\n".join(lines[i:end])
        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "file_path": file_path,
                "start_line": i + 1,
                "end_line": end,
            })
        i += max_lines - overlap
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Mistral Codestral Embed."""
    all_embeddings = []
    batch_size = 32

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = mistral_client.embeddings.create(
            model=EMBED_MODEL,
            inputs=batch,
            output_dimension=OUTPUT_DIMENSION,
        )
        for item in response.data:
            all_embeddings.append(item.embedding)

    return all_embeddings


def process_s3_file(bucket: str, key: str) -> list[dict]:
    """Download a file from S3 and return its chunks."""
    ext = os.path.splitext(key)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        logger.info(f"Skipping unsupported file type: {key}")
        return []

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Failed to read s3://{bucket}/{key}: {e}")
        return []

    # Strip the source/ prefix for display path
    display_path = key.removeprefix("source/")
    chunks = chunk_code(content, display_path)
    logger.info(f"Chunked {key} into {len(chunks)} chunks")
    return chunks


def ingest_chunks(chunks: list[dict]) -> int:
    """Embed chunks and store in LanceDB. Returns count stored."""
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    embeddings = embed_texts(texts)

    # Build records
    records = []
    for chunk, embedding in zip(chunks, embeddings):
        records.append({
            "vector": embedding,
            "text": chunk["text"],
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
        })

    # Write to LanceDB
    db = get_lancedb()

    schema = pa.schema([
        pa.field("vector", pa.list_(pa.float32(), EMBED_DIMENSIONS)),
        pa.field("text", pa.utf8()),
        pa.field("file_path", pa.utf8()),
        pa.field("start_line", pa.int32()),
        pa.field("end_line", pa.int32()),
    ])

    if TABLE_NAME in db.table_names():
        table = db.open_table(TABLE_NAME)
        table.add(records)
    else:
        table = db.create_table(TABLE_NAME, data=records, schema=schema)

    logger.info(f"Stored {len(records)} chunks in LanceDB table '{TABLE_NAME}'")
    return len(records)


def lambda_handler(event: dict[str, Any], context: Any) -> dict:
    """
    Handle both S3 event triggers and API Gateway POST /ingest requests.
    """
    # Determine if this is an S3 event or API request
    if "Records" in event:
        # S3 trigger
        total_chunks = 0
        for record in event["Records"]:
            bucket = record["s3"]["bucket"]["name"]
            key = record["s3"]["object"]["key"]
            logger.info(f"Processing S3 event: s3://{bucket}/{key}")
            chunks = process_s3_file(bucket, key)
            total_chunks += ingest_chunks(chunks)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": f"Ingested {total_chunks} chunks"}),
        }

    elif "body" in event:
        # API Gateway trigger
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid JSON body"}),
            }

        bucket = body.get("bucket", LANCEDB_BUCKET)
        prefix = body.get("prefix", "source/")

        # List all objects under prefix
        paginator = s3_client.get_paginator("list_objects_v2")
        total_chunks = 0

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                chunks = process_s3_file(bucket, key)
                total_chunks += ingest_chunks(chunks)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "message": f"Ingested {total_chunks} chunks from s3://{bucket}/{prefix}",
                "chunks_stored": total_chunks,
            }),
        }

    else:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Unsupported event type"}),
        }
