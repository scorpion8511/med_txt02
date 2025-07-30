"""Utilities for curating pathology-related articles from PubMed Central."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Set

from Bio import Entrez
from tqdm import tqdm

import pubmed_parser


DEFAULT_EMAIL = "your.email@example.com"


def search_pmcids(
    terms: Iterable[str],
    *,
    email: str = DEFAULT_EMAIL,
    api_key: Optional[str] = None,
    start_year: int = 2000,
    end_year: int = 2023,
) -> Set[str]:
    """Search PubMed Central for a list of terms.

    Parameters
    ----------
    terms:
        Search terms to query. Each term is searched individually.
    email:
        Email address for NCBI Entrez registration.
    api_key:
        Optional NCBI API key for higher rate limits.
    start_year:
        Earliest publication year.
    end_year:
        Latest publication year.

    Returns
    -------
    Set[str]
        A set of unique PMCIDs returned by the search.
    """

    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key

    pmcids: Set[str] = set()

    for term in terms:
        query = f"{term} AND ({start_year}[PDAT] : {end_year}[PDAT])"
        handle = Entrez.esearch(db="pmc", term=query, retmax=0)
        record = Entrez.read(handle)
        handle.close()
        count = int(record["Count"])

        for start in range(0, count, 1000):
            handle = Entrez.esearch(
                db="pmc",
                term=query,
                retmax=1000,
                retstart=start,
            )
            batch = Entrez.read(handle)
            handle.close()
            pmcids.update(batch.get("IdList", []))

    return pmcids


def download_articles(
    pmcids: Iterable[str],
    output_dir: Path,
    *,
    email: str = DEFAULT_EMAIL,
    api_key: Optional[str] = None,
) -> None:
    """Download full articles from PubMed Central by PMCID.

    Parameters
    ----------
    pmcids:
        PMCIDs of articles to download.
    output_dir:
        Directory to store downloaded XML files.
    email:
        Email for Entrez.
    api_key:
        Optional API key.
    """

    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key

    output_dir.mkdir(parents=True, exist_ok=True)

    for pmcid in tqdm(list(pmcids)):
        file_path = output_dir / f"{pmcid}.nxml"
        if file_path.exists():
            continue
        handle = Entrez.efetch(db="pmc", id=pmcid, rettype="full", retmode="xml")
        data = handle.read()
        handle.close()
        with open(file_path, "w", encoding="utf8") as f:
            f.write(data)


def extract_article_text(
    article_dir: Path, output_file: Path
) -> None:
    """Parse downloaded articles and write JSONL of article texts.

    Parameters
    ----------
    article_dir:
        Folder containing downloaded ``.nxml`` files.
    output_file:
        Output JSONL file path.
    """

    with output_file.open("w", encoding="utf8") as out_f:
        for nxml_path in tqdm(sorted(article_dir.glob("*.nxml"))):
            parsed = pubmed_parser.parse_pubmed_xml(str(nxml_path), nxml=True)
            text_parts: List[str] = [
                parsed.get("full_title", ""),
                parsed.get("abstract", ""),
            ]
            article_text = "\n".join(part for part in text_parts if part)
            out = {
                "pmcid": parsed.get("pmc", nxml_path.stem),
                "pmid": parsed.get("pmid", ""),
                "text": article_text,
            }
            out_f.write(json.dumps(out) + "\n")

