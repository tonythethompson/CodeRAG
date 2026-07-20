"""
CodeRAG MCP Server

Exposes a `search_code` tool over stdio that any MCP client
(Kiro, Claude, Cursor, etc.) can call to search the Trackdub codebase.

Usage:
    python server.py

Requires env var:
    CODERAG_API_URL - e.g. https://0aj8ta5994.execute-api.us-east-1.amazonaws.com/dev
"""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

# --- Config ---
API_URL = os.environ.get(
    "CODERAG_API_URL",
    "https://0aj8ta5994.execute-api.us-east-1.amazonaws.com/dev",
)

mcp = FastMCP("CodeRAG", description="Search project codebase via semantic code search")


@mcp.tool()
async def search_code(question: str, top_k: int = 10, file_filter: str = "") -> str:
    """Search the codebase for code relevant to a natural language question.

    Args:
        question: Natural language query about the code (e.g. "How does ASR work?")
        top_k: Number of results to return (1-50, default 10)
        file_filter: Optional path filter to narrow results (e.g. "Inference/" or "Domain/")

    Returns:
        Relevant code chunks with file paths, line numbers, and content.
    """
    payload = {
        "question": question,
        "top_k": min(max(top_k, 1), 50),
    }
    if file_filter:
        payload["file_filter"] = file_filter

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{API_URL}/query",
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    results = data.get("results", [])

    if not results:
        return f"No results found for: {question}"

    # Format results for the LLM
    output_parts = [f"Found {len(results)} relevant code chunks:\n"]

    for i, result in enumerate(results, 1):
        file_path = result["file_path"]
        start = result["start_line"]
        end = result["end_line"]
        text = result["text"]
        score = result.get("score", 0)

        output_parts.append(
            f"--- [{i}] {file_path}:{start}-{end} (distance: {score:.4f}) ---\n"
            f"{text}\n"
        )

    return "\n".join(output_parts)


@mcp.tool()
async def search_code_in_file(file_path: str, question: str, top_k: int = 5) -> str:
    """Search for relevant code within a specific file or directory.

    Args:
        file_path: File or directory path to search within (e.g. "Trackdub.Domain/" or "Trackdub.Inference/Asr/")
        question: What to search for in that file/directory
        top_k: Number of results (default 5)

    Returns:
        Relevant code chunks from the specified path.
    """
    return await search_code(question=question, top_k=top_k, file_filter=file_path)


if __name__ == "__main__":
    mcp.run(transport="stdio")
