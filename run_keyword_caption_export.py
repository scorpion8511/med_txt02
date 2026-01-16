#!/usr/bin/env python
"""Export PubMed figure captions to CSV.

This script optionally decompresses PubMed Open Access archives, parses captions
with ``pubmed_parser``, and exports figure metadata to a CSV file.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from pmc15_pipeline import data


def _load_parsed_articles(parsed_jsonl: Path) -> list[dict]:
    articles: list[dict] = []
    with parsed_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            articles.append(json.loads(line))
    return articles


def _export_to_csv(
    articles: list[dict],
    output_csv: Path,
    append: bool,
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_header = True
    if append and output_csv.exists():
        write_header = False

    fieldnames = [
        "pmid",
        "pmc",
        "fig_id",
        "fig_label",
        "fig_caption",
        "graphic_ref",
        "pair_id",
    ]

    mode = "a" if append else "w"
    with output_csv.open(mode, newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()

        for article in articles:
            for figure in article.get("figures", []):
                writer.writerow(
                    {
                        "pmid": article.get("pmid", ""),
                        "pmc": article.get("pmc", ""),
                        "fig_id": figure.get("fig_id", ""),
                        "fig_label": figure.get("fig_label", ""),
                        "fig_caption": figure.get("fig_caption", ""),
                        "graphic_ref": figure.get("graphic_ref", ""),
                        "pair_id": figure.get("pair_id", ""),
                    }
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export PubMed figure captions to CSV."
    )
    parser.add_argument(
        "--decompressed-folder",
        type=Path,
        default=data.repo_root / "_results" / "data" / "pubmed_open_access_files",
        help="Folder containing decompressed PubMed Open Access files.",
    )
    parser.add_argument(
        "--compressed-folder",
        type=Path,
        default=data.repo_root
        / "_results"
        / "data"
        / "pubmed_open_access_files_compressed",
        help="Folder containing compressed PubMed Open Access archives.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=data.repo_root / "_results" / "data" / "pmc_captions.csv",
        help="Path to write the CSV output.",
    )
    parser.add_argument(
        "--parsed-jsonl",
        type=Path,
        default=data.repo_root / "_results" / "data" / "pubmed_parsed_data.json",
        help="Path to write/read parsed PubMed JSONL data.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the output CSV instead of overwriting.",
    )
    parser.add_argument(
        "--decompress",
        action="store_true",
        help="Decompress the PubMed Open Access archives before parsing.",
    )
    parser.add_argument(
        "--skip-pubmed-parser",
        action="store_true",
        help=(
            "Skip parsing with pubmed_parser and use the existing JSONL data "
            "instead."
        ),
    )

    args = parser.parse_args()

    if not args.skip_pubmed_parser:
        if args.decompress:
            data.decompress_pubmed_files(
                input_folder_path=args.compressed_folder,
                output_folder_path=args.decompressed_folder,
            )

        data.generate_pmc15_pipeline_outputs(
            decompressed_folder=args.decompressed_folder,
            output_file_path=args.parsed_jsonl,
        )
    elif not args.parsed_jsonl.exists():
        raise FileNotFoundError(
            "Parsed JSONL file not found. Either run without "
            "--skip-pubmed-parser or provide an existing --parsed-jsonl path."
        )

    articles = _load_parsed_articles(args.parsed_jsonl)
    _export_to_csv(articles, args.output_csv, args.append)


if __name__ == "__main__":
    main()
