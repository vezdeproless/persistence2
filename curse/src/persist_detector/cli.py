from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .extract import iter_extraction_jobs, run_extraction
from .normalize import normalize_directory
from .opensearch import DEFAULT_BATCH_SIZE, DEFAULT_INDEX_NAME, DEFAULT_RETRIES, index_registry_file
from .targets import TARGET_BRANCHES


def read_host_name(input_root: Path) -> str | None:
    manifest = input_root / "manifest.json"
    if not manifest.is_file():
        return None

    try:
        with manifest.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    host_name = data.get("host_name")
    return str(host_name) if host_name else None


def command_extract(args: argparse.Namespace) -> int:
    count = run_extraction(args.input, args.output, args.recmd)
    print(f"Created extraction jobs: {count}")
    return 0


def command_normalize(args: argparse.Namespace) -> int:
    host_name = args.host or read_host_name(args.source_root or args.input)
    count = normalize_directory(args.input, args.output, host_name=host_name)
    print(f"Wrote normalized registry records: {count}")
    return 0


def command_index(args: argparse.Namespace) -> int:
    indexed = run_opensearch_indexing(args.input, args)
    print(f"Indexed OpenSearch documents: {indexed}")
    print(f"OpenSearch index: {args.opensearch_index}")
    return 0


def command_process(args: argparse.Namespace) -> int:
    output = args.output or (args.input / "processed" / "Registry.json")
    extracted_dir = args.extracted_dir or (output.parent / "extracted")
    host_name = args.host or read_host_name(args.input)

    count_jobs = run_extraction(args.input, extracted_dir, args.recmd)
    count_records = normalize_directory(extracted_dir, output, host_name=host_name)

    if count_records == 0:
        print(f"Warning: no normalized records were written. Kept extracted JSON for inspection: {extracted_dir}")
    elif not args.keep_extracted and extracted_dir.exists():
        shutil.rmtree(extracted_dir)

    print(f"Created extraction jobs: {count_jobs}")
    print(f"Wrote normalized registry records: {count_records}")
    print(f"Output: {output}")

    if args.skip_index:
        print("OpenSearch indexing skipped.")
    else:
        indexed = run_opensearch_indexing(output, args)
        print(f"Indexed OpenSearch documents: {indexed}")
        print(f"OpenSearch index: {args.opensearch_index}")

    return 0


def run_opensearch_indexing(input_file: Path, args: argparse.Namespace) -> int:
    if args.opensearch_batch_size < 1:
        raise SystemExit("--opensearch-batch-size must be greater than zero")

    if args.opensearch_retries < 0:
        raise SystemExit("--opensearch-retries must be zero or greater")

    return index_registry_file(
        input_file,
        opensearch_url=args.opensearch_url,
        index_name=args.opensearch_index,
        username=args.opensearch_username,
        password=args.opensearch_password,
        verify_tls=not args.opensearch_insecure,
        batch_size=args.opensearch_batch_size,
        retries=args.opensearch_retries,
    )


def command_print_targets(_: argparse.Namespace) -> int:
    for hive_kind, branches in TARGET_BRANCHES.items():
        print(f"[{hive_kind}]")
        for branch in branches:
            print(branch)
        print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="persist-detector",
        description="Process Windows persistence registry artifacts for OpenSearch.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Run RECmd targeted extraction against uploaded hives.")
    extract.add_argument("--input", type=Path, required=True, help="Uploaded host directory.")
    extract.add_argument("--output", type=Path, required=True, help="Directory for RECmd JSON output.")
    extract.add_argument("--recmd", type=Path, required=True, help="Path to RECmd.exe or RECmd wrapper.")
    extract.set_defaults(func=command_extract)

    normalize = subparsers.add_parser("normalize", help="Normalize RECmd JSON into Registry.json NDJSON.")
    normalize.add_argument("--input", type=Path, required=True, help="Directory containing RECmd JSON files.")
    normalize.add_argument("--output", type=Path, required=True, help="Output NDJSON file.")
    normalize.add_argument("--source-root", type=Path, help="Uploaded host directory containing manifest.json.")
    normalize.add_argument("--host", help="Host name to add to normalized records.")
    normalize.set_defaults(func=command_normalize)

    index = subparsers.add_parser("index", help="Index an existing Registry.json file into OpenSearch.")
    index.add_argument("--input", type=Path, required=True, help="Registry.json NDJSON file.")
    add_opensearch_arguments(index)
    index.set_defaults(func=command_index)

    process = subparsers.add_parser("process", help="Run extraction, normalization, and OpenSearch indexing.")
    process.add_argument("--input", type=Path, required=True, help="Uploaded host directory.")
    process.add_argument("--output", type=Path, help="Output NDJSON file. Defaults to <input>/processed/Registry.json.")
    process.add_argument("--recmd", type=Path, required=True, help="Path to RECmd.exe or RECmd wrapper.")
    process.add_argument("--extracted-dir", type=Path, help="Directory for intermediate RECmd JSON.")
    process.add_argument("--host", help="Host name to add to normalized records.")
    process.add_argument("--keep-extracted", action="store_true", help="Keep intermediate RECmd JSON files.")
    process.add_argument("--skip-index", action="store_true", help="Write Registry.json without indexing it.")
    add_opensearch_arguments(process)
    process.set_defaults(func=command_process)

    print_targets = subparsers.add_parser("print-targets", help="Print configured registry extraction branches.")
    print_targets.set_defaults(func=command_print_targets)

    jobs = subparsers.add_parser("list-jobs", help="List RECmd extraction jobs for an uploaded host directory.")
    jobs.add_argument("--input", type=Path, required=True, help="Uploaded host directory.")
    jobs.set_defaults(func=command_list_jobs)

    return parser


def add_opensearch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--opensearch-url",
        default=os.environ.get("OPENSEARCH_URL", "https://localhost:9200"),
        help="OpenSearch base URL. Default: OPENSEARCH_URL or https://localhost:9200.",
    )
    parser.add_argument(
        "--opensearch-index",
        default=os.environ.get("OPENSEARCH_INDEX", DEFAULT_INDEX_NAME),
        help=f"OpenSearch index name. Default: {DEFAULT_INDEX_NAME}.",
    )
    parser.add_argument(
        "--opensearch-username",
        default=os.environ.get("OPENSEARCH_USERNAME"),
        help="OpenSearch username. Defaults to OPENSEARCH_USERNAME.",
    )
    parser.add_argument(
        "--opensearch-password",
        default=os.environ.get("OPENSEARCH_PASSWORD"),
        help="OpenSearch password. Defaults to OPENSEARCH_PASSWORD.",
    )
    parser.add_argument(
        "--opensearch-insecure",
        action="store_true",
        help="Disable TLS certificate verification for lab clusters with self-signed certificates.",
    )
    parser.add_argument(
        "--opensearch-batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Documents per bulk request. Default: {DEFAULT_BATCH_SIZE}.",
    )
    parser.add_argument(
        "--opensearch-retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retries for transient OpenSearch HTTP or network errors. Default: {DEFAULT_RETRIES}.",
    )


def command_list_jobs(args: argparse.Namespace) -> int:
    for job in iter_extraction_jobs(args.input):
        print(f"{job.hive_kind}\t{job.hive_path}\t{job.branch}\t{job.output_name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
