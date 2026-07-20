"""
Upload source code files to S3 for CodeRAG ingestion.

Usage:
    python scripts/upload-source.py <source_dir> <bucket_name> [--prefix source/]

Example:
    python scripts/upload-source.py D:\Dev\Trackdub\src coderag-bucket-12345
    python scripts/upload-source.py D:\Dev\Trackdub\docs coderag-bucket-12345 --prefix source/docs/

Files are uploaded under s3://<bucket>/source/<relative_path>
which triggers the Ingest Lambda automatically via S3 event.
"""

import argparse
import os
import sys
from pathlib import Path

import boto3

SUPPORTED_EXTENSIONS = {
    ".cs", ".md", ".yaml", ".yml", ".json", ".xml",
    ".csproj", ".sln", ".props", ".targets", ".axaml",
    ".py", ".ts", ".js", ".sh", ".ps1", ".toml",
}

SKIP_DIRS = {
    "bin", "obj", ".git", ".vs", ".idea", "node_modules",
    ".aws-sam", "__pycache__", ".venv", "packages",
}


def should_include(path: Path) -> bool:
    """Check if file should be uploaded."""
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False
    # Skip if any parent dir is in SKIP_DIRS
    for part in path.parts:
        if part in SKIP_DIRS:
            return False
    return True


def upload_directory(source_dir: str, bucket: str, prefix: str = "source/"):
    """Upload all supported files from source_dir to S3."""
    s3 = boto3.client("s3")
    source_path = Path(source_dir).resolve()

    if not source_path.exists():
        print(f"Error: {source_path} does not exist")
        sys.exit(1)

    files_uploaded = 0
    files_skipped = 0

    for file_path in source_path.rglob("*"):
        if not file_path.is_file():
            continue

        rel_path = file_path.relative_to(source_path)

        if not should_include(rel_path):
            files_skipped += 1
            continue

        # S3 key: source/<relative_path> (forward slashes)
        s3_key = prefix + str(rel_path).replace("\\", "/")

        try:
            s3.upload_file(
                str(file_path),
                bucket,
                s3_key,
                ExtraArgs={"ContentType": "text/plain"},
            )
            files_uploaded += 1
            print(f"  Uploaded: {s3_key}")
        except Exception as e:
            print(f"  FAILED: {s3_key} - {e}")

    print(f"\nDone. Uploaded: {files_uploaded}, Skipped: {files_skipped}")
    print(f"Files are at s3://{bucket}/{prefix}")
    print("Ingest Lambda will trigger automatically for each upload.")


def main():
    parser = argparse.ArgumentParser(
        description="Upload source code to S3 for CodeRAG ingestion"
    )
    parser.add_argument("source_dir", help="Local directory containing source code")
    parser.add_argument("bucket", help="S3 bucket name (from SAM stack output)")
    parser.add_argument(
        "--prefix",
        default="source/",
        help="S3 key prefix (default: source/)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile to use",
    )

    args = parser.parse_args()

    if args.profile:
        boto3.setup_default_session(profile_name=args.profile)

    upload_directory(args.source_dir, args.bucket, args.prefix)


if __name__ == "__main__":
    main()
