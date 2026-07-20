"""
Quick CLI to query the CodeRAG API.

Usage:
    python scripts/query-rag.py "How does the pipeline work?" --url https://xxx.execute-api.us-east-1.amazonaws.com/dev
"""

import argparse
import json
import sys

import requests


def main():
    parser = argparse.ArgumentParser(description="Query CodeRAG API")
    parser.add_argument("question", help="Question to search for")
    parser.add_argument("--url", required=True, help="API Gateway base URL")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results")
    parser.add_argument("--filter", default="", help="File path filter")

    args = parser.parse_args()

    endpoint = args.url.rstrip("/") + "/query"
    payload = {
        "question": args.question,
        "top_k": args.top_k,
    }
    if args.filter:
        payload["file_filter"] = args.filter

    try:
        resp = requests.post(endpoint, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)

    data = resp.json()
    print(f"\nQuestion: {data['question']}")
    print(f"Results: {data['count']}\n")

    for i, result in enumerate(data["results"], 1):
        score = result.get("score", 0)
        print(f"--- [{i}] {result['file_path']}:{result['start_line']}-{result['end_line']} (distance: {score:.4f}) ---")
        # Show first 10 lines of chunk
        lines = result["text"].split("\n")[:10]
        for line in lines:
            print(f"  {line}")
        if len(result["text"].split("\n")) > 10:
            print("  ...")
        print()


if __name__ == "__main__":
    main()
