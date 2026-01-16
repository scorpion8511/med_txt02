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
from typing import Iterable

import pubmed_parser
from lxml import etree
from tqdm import tqdm

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
    articles: Iterable[dict],
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


def _iter_parsed_articles_from_nxml(decompressed_folder: Path) -> list[dict]:
    def parse_single_pubmed_file(nxml_path: Path) -> list[dict]:
        if nxml_path is None or not nxml_path.exists():
            return []

        try:
            output = pubmed_parser.parse_pubmed_caption(str(nxml_path.absolute()))
        except AttributeError:
            return []
        except etree.XMLSyntaxError:
            return []
        except Exception:
            return []

        if not output:
            return []

        figures = []
        pmid = output[0].get("pmid", "")
        pmc = output[0].get("pmc", "")
        location = Path(nxml_path).parent

        for figure_dict in output:
            figure_object = {
                "fig_caption": str(figure_dict.get("fig_caption", "")),
                "fig_id": str(figure_dict.get("fig_id", "")),
                "fig_label": str(figure_dict.get("fig_label", "")),
                "graphic_ref": (
                    str(location / (figure_dict["graphic_ref"] + ".jpg"))
                    if "graphic_ref" in figure_dict
                    else ""
                ),
                "pair_id": str(pmid) + "_" + str(figure_dict.get("fig_id", "")),
            }
            figures.append(figure_object)

        article = {
            "pmid": pmid,
            "pmc": pmc,
            "location": str(location),
            "figures": figures,
        }

        return [article]

    articles: list[dict] = []
    for nxml_file in tqdm(decompressed_folder.rglob("*.nxml")):
        articles.extend(parse_single_pubmed_file(nxml_file))
    return articles


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
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Skip writing the intermediate JSONL file and parse directly to CSV.",
    )

    args = parser.parse_args()

    if args.no_json and args.skip_pubmed_parser:
        raise ValueError(
            "--no-json cannot be combined with --skip-pubmed-parser."
        )

    if not args.skip_pubmed_parser and not args.no_json:
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

    if args.no_json:
        if args.decompress:
            data.decompress_pubmed_files(
                input_folder_path=args.compressed_folder,
                output_folder_path=args.decompressed_folder,
            )
        if not args.decompressed_folder.exists():
            raise FileNotFoundError(
                "Decompressed folder not found. Provide --decompressed-folder "
                "or pass --decompress to extract archives."
            )
        articles = _iter_parsed_articles_from_nxml(args.decompressed_folder)
    else:
        articles = _load_parsed_articles(args.parsed_jsonl)

    _export_to_csv(articles, args.output_csv, args.append)


if __name__ == "__main__":
    main()
