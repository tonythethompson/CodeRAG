"""
CodeRAG Query Lambda

Accepts a natural language question, embeds it via Mistral Codestral Embed,
searches LanceDB for relevant code chunks, returns top-k results.

Endpoint: POST /query
Body: {"question": "How does the pipeline stage work?", "top_k": 10}
"""

import json
import os
import logging
from typing import Any

import lancedb
from mistralai import Mistral

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration ---
MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]
LANCEDB_BUCKET = os.environ["LANCEDB_BUCKET"]
EMBED_MODEL = "codestral-embed-2505"
OUTPUT_DIMENSION = 1024  # Must match ingest Lambda
TABLE_NAME = "code_chunks"
DEFAULT_TOP_K = 10

# --- Clients ---
mistral_client = Mistral(api_key=MISTRAL_API_KEY)


def get_lancedb():
    """Connect to LanceDB with S3 storage."""
    storage_options = {
        "aws_default_region": os.environ.get("AWS_REGION", "us-east-1"),
    }
    db_uri = f"s3://{LANCEDB_BUCKET}/lancedb"
    return lancedb.connect(db_uri, storage_options=storage_options)


def embed_query(text: str) -> list[float]:
    """Embed a single query text via Mistral Codestral Embed."""
    response = mistral_client.embeddings.create(
        model=EMBED_MODEL,
        inputs=[text],
        output_dimension=OUTPUT_DIMENSION,
    )
    return response.data[0].embedding


def search(question: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Embed the question and search LanceDB for nearest code chunks."""
    query_vector = embed_query(question)

    db = get_lancedb()

    if TABLE_NAME not in db.table_names():
        logger.warning(f"Table '{TABLE_NAME}' not found - run ingestion first")
        return []

    table = db.open_table(TABLE_NAME)

    results = (
        table.search(query_vector)
        .limit(top_k)
        .to_list()
    )

    # Format results
    formatted = []
    for row in results:
        formatted.append({
            "file_path": row["file_path"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "text": row["text"],
            "score": float(row.get("_distance", 0.0)),
        })

    return formatted


def lambda_handler(event: dict[str, Any], context: Any) -> dict:
    """
    Handle POST /query requests.
    Body: {"question": "...", "top_k": 10, "file_filter": "optional/path/prefix"}
    """
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON body"}),
        }

    question = body.get("question", "").strip()
    if not question:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing 'question' field"}),
        }

    top_k = body.get("top_k", DEFAULT_TOP_K)
    top_k = min(max(int(top_k), 1), 50)  # clamp 1-50

    logger.info(f"Query: '{question}' (top_k={top_k})")

    results = search(question, top_k=top_k)

    # Optional file path filter
    file_filter = body.get("file_filter", "").strip()
    if file_filter:
        results = [r for r in results if file_filter in r["file_path"]]

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "question": question,
            "results": results,
            "count": len(results),
        }),
    }
