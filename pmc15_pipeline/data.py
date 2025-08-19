import json
import tarfile
from pathlib import Path
from typing import Optional
import contextlib
import gc

import pubmed_parser
import requests
from lxml import etree
from tqdm import tqdm

from .constants import PUBMED_OPEN_ACCESS_BASE_URL, PUBMED_OPEN_ACCESS_FILE_LIST_URL
from .types import PubMedFile
from .utils import fs_utils

repo_root = fs_utils.get_repo_root_path()

# Default set of domain keywords; these act as a fallback if a glossary
# cannot be fetched from a remote source.
DEFAULT_DOMAIN_KEYWORDS = {
    "pathology": ["pathology", "whole slide image", "H&E"],
    "x-ray": ["x-ray"],
    "endoscopy": ["endoscopy", "gastrology"],
    "ultra": ["ultrasound"],
    "mri": ["MRI"],
}

# Only captions containing these keywords are retained by default. This list
# combines all domain keywords so the default dataset includes figures from any
# supported imaging modality.
DEFAULT_KEYWORDS = [
    kw for kws in DEFAULT_DOMAIN_KEYWORDS.values() for kw in kws
]

# Common animal-related terms that should be excluded to focus on human data
ANIMAL_KEYWORDS = [
    "mouse",
    "mice",
    "murine",
    "rat",
    "rats",
    "rabbit",
    "rabbits",
    "canine",
    "dog",
    "dogs",
    "cat",
    "cats",
    "feline",
    "porcine",
    "pig",
    "pigs",
    "swine",
    "bovine",
    "cow",
    "cattle",
    "sheep",
    "goat",
    "hamster",
    "monkey",
    "monkeys",
    "primate",
    "primates",
    "zebrafish",
    "drosophila",
    "fruit fly",
    "guinea pig",
    "ferret",
]


def load_domain_keywords(urls: dict[str, str] | str | None = None) -> dict[str, list[str]]:
    """Load domain keywords from remote ``urls`` or fall back to defaults.

    ``urls`` may be a single URL pointing to a JSON object mapping domain names
    to lists of keywords, or a dictionary mapping individual domain names to
    URLs returning a JSON array for that domain. Failed downloads leave the
    default keywords in place.
    """

    keywords = DEFAULT_DOMAIN_KEYWORDS.copy()

    if isinstance(urls, str) and urls:
        # Backwards compatibility: single URL hosting all domains
        try:
            response = requests.get(urls, timeout=10)
            response.raise_for_status()
            data = response.json()
            for domain in keywords:
                if isinstance(data.get(domain), list):
                    keywords[domain] = data[domain]
        except requests.RequestException as err:  # pragma: no cover - network
            print(f"Failed to fetch domain glossary from {urls}: {err}")
    elif isinstance(urls, dict):
        for domain, url in urls.items():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    keywords[domain] = data
                elif isinstance(data, dict) and isinstance(data.get(domain), list):
                    keywords[domain] = data[domain]
            except requests.RequestException as err:  # pragma: no cover - network
                print(
                    f"Failed to fetch domain glossary for '{domain}' from {url}: {err}"
                )

    return keywords


DOMAIN_KEYWORDS = load_domain_keywords()
DOMAIN_KEYWORDS_LOWER = {
    domain: [kw.lower() for kw in keywords]
    for domain, keywords in DOMAIN_KEYWORDS.items()
}


def _basic_caption_parse(nxml_path: Path) -> list[dict]:
    """Memory-friendly caption parser using ``iterparse``.

    ``pubmed_parser`` loads the entire XML tree into memory which can exceed
    the container limits for articles embedding large images.  This streaming
    parser walks the file incrementally and clears elements as soon as they
    are processed, keeping the memory footprint small.  Only minimal figure
    metadata is extracted.  Any errors result in an empty list.
    """

    figures: list[dict] = []
    pmid = ""
    pmc = ""
    current: dict | None = None

    try:
        # ``huge_tree`` allows lxml to handle base64 encoded images without
        # exhausting memory; ``iterparse`` ensures elements are discarded as we
        # progress through the document.
        context = etree.iterparse(
            str(nxml_path), events=("start", "end"), recover=True, huge_tree=True
        )
    except Exception as err:  # pragma: no cover - parse errors are rare
        print(f"Fallback parser failed for {nxml_path}: {err}")
        return []

    for event, elem in context:
        if event == "start" and elem.tag == "fig":
            current = {
                "fig_caption": "",
                "fig_id": elem.get("id", ""),
                "fig_label": "",
                "graphic_ref": "",
                "pmid": "",
                "pmc": "",
                "fig_refs": [],
            }
        elif event == "end":
            if elem.tag == "article-id":
                id_type = elem.get("pub-id-type")
                if id_type == "pmid":
                    pmid = elem.text or ""
                elif id_type == "pmcid":
                    pmc = elem.text or ""
            elif current is not None:
                if elem.tag == "label":
                    current["fig_label"] = elem.text or ""
                elif elem.tag == "caption":
                    current["fig_caption"] = "".join(elem.itertext()).strip()
                elif elem.tag == "graphic":
                    current["graphic_ref"] = elem.get(
                        "{http://www.w3.org/1999/xlink}href", ""
                    )
                elif elem.tag == "fig":
                    current["pmid"] = pmid
                    current["pmc"] = pmc
                    figures.append(current)
                    current = None
            # Release memory for processed elements
            if elem.getparent() is not None:
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
                elem.clear()

    return figures


def download_pubmed_file_list(
    url=PUBMED_OPEN_ACCESS_FILE_LIST_URL,
    output_file_path: Path = (
        repo_root / "_results" / "data" / "pubmed_open_access_file_list.txt"
    ),
):
    # Ensure output directory exists
    Path(output_file_path).parent.mkdir(parents=True, exist_ok=True)

    # Download file
    print(f"Downloading OpenAccess file list from: {url} to {output_file_path}")

    if Path(output_file_path).exists():
        print(f"File already exists: {output_file_path}")
        return

    response = requests.get(url)

    with open(output_file_path, "wb") as file:
        file.write(response.content)

    print(f"Saved to: {output_file_path}")


def download_pubmed_files_from_list(
    file_list_path: Path = (
        repo_root / "_results/data/pubmed_open_access_file_list.txt"
    ),
    output_folder_path: Path = (
        repo_root / "_results" / "data" / "pubmed_open_access_files_compressed"
    ),
    subset_size: Optional[int] = None,
    file_extension=".tar.gz",
):
    """Download files from PubMed Open Access file list

    Args:
        file_list_path (Path, optional): Path to PubMed Open Access Files list. Defaults to "_results/data/pubmed_open_access_file_list_top_100.txt".
        output_folder_path (Path, optional): Path to save directory. Defaults to repo_root/"_results"/"data"/"pubmed_open_access_files_compressed".
        subset_size (int, optional): Number of files to download. Defaults to None (download all files).

    Example:

        python3 -m data.download_pubmed_files
    """

    output_folder_path.mkdir(parents=True, exist_ok=True)
    skipped_files = []

    def _get_file_size(url: str) -> int | None:
        response = requests.head(url)
        if "Content-Length" in response.headers:
            return int(response.headers["Content-Length"])
        return None

    with open(file_list_path, "r") as file:
        next(file)  # skip header line
        for line_idx, line in enumerate(file):
            if subset_size and line_idx >= subset_size:
                break

            path, title, pmcid, pmid, code = line.strip().split("\t")
            pubmed_file: PubMedFile = {
                "path": path,
                "title": title,
                "pmcid": pmcid,
                "pmid": pmid,
                "code": code,
            }

            file_name = pmcid + file_extension
            file_path = output_folder_path / file_name

            if file_path.exists():
                tqdm.write(
                    f"File: {file_name} already exists. Not downloading again."
                )
                continue

            article_url = PUBMED_OPEN_ACCESS_BASE_URL + path
            file_size = _get_file_size(article_url)
            if file_size is None:
                tqdm.write(
                    f"File: {file_name} Skipped! Could not get file size!"
                )
                skipped_files.append(pubmed_file)
                continue

            tqdm.write(f"File: {file_name} size: {file_size} bytes")
            try:
                with requests.get(article_url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(file_path, "wb") as f_out:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f_out.write(chunk)
            except requests.RequestException as e:
                tqdm.write(
                    f"File: {file_name} Skipped! Error occurred: {e}"
                )
                skipped_files.append(pubmed_file)

    print(f"Skipped {len(skipped_files)} files.")


def decompress_pubmed_files(
    input_folder_path: Path = (
        repo_root / "_results" / "data" / "pubmed_open_access_files_compressed"
    ),
    output_folder_path: Path = (
        repo_root / "_results" / "data" / "pubmed_open_access_files"
    ),
    file_extension="*.tar.gz",
):
    """Decompress article files from PubMed Open Access folder

    Args:
        input_folder_path (Path, optional): _description_. Defaults to repo_root/"_results"/"data"/"pubmed_open_access_files_compressed".
        output_folder_path (Path, optional): _description_. Defaults to repo_root/"_results"/"data"/"pubmed_open_access_files".
        file_extension (str, optional): _description_. Defaults to ".tar.gz".

    Example:

        python3 -m data.decompress_pubmed_files
    """

    # Ensure output directory exists
    output_folder_path.mkdir(parents=True, exist_ok=True)

    file_paths = list(input_folder_path.glob(file_extension))

    print(
        f"Found {len(file_paths)} files that match {file_extension} in {input_folder_path}"
    )

    for file_path in tqdm(file_paths):
        dest_dir = output_folder_path / file_path.name.replace(".tar.gz", "")

        if dest_dir.exists():
            tqdm.write(
                f"Archive {file_path.name} already extracted. Skipping.")
            continue

        try:
            with tarfile.open(file_path, "r:gz") as tar_file:
                tar_file.extractall(output_folder_path)
        except (tarfile.TarError, OSError) as err:
            tqdm.write(f"Failed to extract {file_path.name}: {err}")

    print(f"Finished extracting {len(file_paths)} files")


def generate_pmc15_pipeline_outputs(
    decompressed_folder: Path = (
        repo_root / "_results" / "data" / "pubmed_open_access_files"
    ),
    output_file_path: Path = (
        repo_root / "_results" / "data" / "pubmed_parsed_data.json"
    ),
    keywords: list[str] | None = None,
    glossary_urls: dict[str, str] | str | None = None,
    exclude_keywords: list[str] | None = ANIMAL_KEYWORDS,
    domain_caption_output: Path | None = (
        repo_root / "_results" / "data" / "domain_caption_pairs.jsonl"
    ),
):

    # input - path to .nxml file for each article in the article package
    # output - json object with pmid, pmc id, location (path to article package in storage blobs), figures - list of figure objects which include inline references (mentions of figure throughout the article), caption for the figure, id, label, graphic_ref (filepath to figure jpg in storage blobs), pair_id (a unique id to identify each figure in the article, using pmid + figure_id)
    # Ensure destination directories exist before any processing occurs
    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    if domain_caption_output:
        Path(domain_caption_output).parent.mkdir(parents=True, exist_ok=True)

    domain_keywords = load_domain_keywords(glossary_urls)
    keywords_lower = {kw.lower() for kw in (keywords or DEFAULT_KEYWORDS)}
    exclude_lower = [kw.lower() for kw in (exclude_keywords or [])]
    domain_keywords_lower = {
        domain: [kw.lower() for kw in kws]
        for domain, kws in domain_keywords.items()
    }

    def parse_single_pubmed_file(nxml_path: Path):
        print(nxml_path)

        if nxml_path is None or not nxml_path.exists():
            print("error")
            return []

        print("starting...")
        output: list[dict] = []
        try:
            if nxml_path.stat().st_size > 5_000_000:
                # Large XML files often embed images and may exhaust memory
                output = _basic_caption_parse(nxml_path)
            else:
                output = pubmed_parser.parse_pubmed_caption(
                    str(nxml_path.absolute())
                )
            if not output:
                output = _basic_caption_parse(nxml_path)
        except MemoryError:
            # OOM while using pubmed_parser; retry with streaming parser
            print("MemoryError: falling back to lightweight parser")
            output = _basic_caption_parse(nxml_path)
        except UnboundLocalError as err:
            # Some articles trigger a bug in pubmed_parser referencing an
            # undefined 'caption' variable.  Fall back to the lightweight parser
            # without treating it as a fatal error.
            print(f"Parser bug in pubmed_parser for {nxml_path}: {err}")
            output = _basic_caption_parse(nxml_path)
        except Exception as err:  # pragma: no cover - unexpected parse errors
            print(f"Error parsing {nxml_path}: {err}")
            output = _basic_caption_parse(nxml_path)

        if not output:
            print("no output")
            return []

        print("parsed", nxml_path)

        figures = []
        pmid = output[0]["pmid"]  # same for all figures in the article
        pmc = output[0]["pmc"]  # same for all figures in the article
        location = Path(nxml_path).parent

        # for all figures in the article, create a figure object with inline references (text, section, reference_id), and caption, id, label, graphic_ref, pair_id
        for figure_dict in output:
            inline_references = figure_dict.get(
                "fig_refs", {}
            )  # from pubmed parser
            ir_objects = []
            for inline_reference in inline_references:
                inline_reference_object = {
                    "text": str(inline_reference.get("text", "")),
                    "section": str(inline_reference.get("section", "")),
                    "reference_id": str(inline_reference.get("reference_id", "")),
                }

                ir_objects.append(inline_reference_object)

            if len(ir_objects) > 0:
                raise NotImplementedError("Inline references not implemented")

            caption = str(figure_dict.get("fig_caption", ""))
            caption_lower = caption.lower()
            if exclude_lower and any(kw in caption_lower for kw in exclude_lower):
                continue
            if not any(kw in caption_lower for kw in keywords_lower):
                continue

            domains = [
                domain
                for domain, kws in domain_keywords_lower.items()
                if any(kw in caption_lower for kw in kws)
            ]
            if not domains:
                continue

            figure_object = {
                "fig_caption": caption,
                "fig_id": str(figure_dict.get("fig_id", "")),
                "fig_label": str(figure_dict.get("fig_label", "")),
                "graphic_ref": (
                    str(location / (figure_dict["graphic_ref"] + ".jpg"))
                    if "graphic_ref" in figure_dict
                    else ""
                ),  # set this to the path of the jpg image in storage blobs
                "pair_id": str(pmid) + "_" + str(figure_dict.get("fig_id", "")),
                "inline_references": ir_objects,  # add inline references
                "domains": domains,
            }

            figures.append(figure_object)

        if not figures:
            return []

        article = {
            "pmid": pmid,
            "pmc": pmc,
            "location": str(location),
            "figures": figures,
            "domains": sorted({d for fig in figures for d in fig["domains"]}),
        }

        return [article]

    with output_file_path.open("w+") as f, (
        domain_caption_output.open("w") if domain_caption_output else contextlib.nullcontext()
    ) as cap_f:
        processed_files = 0
        for nxml_file in decompressed_folder.rglob("*.nxml"):
            parsed = parse_single_pubmed_file(nxml_file)
            processed_files += 1

            for article in parsed:
                for figure in article["figures"]:
                    # remove inline references since we're not using them
                    figure.pop("inline_references")
                    if cap_f:
                        caption = figure.get("fig_caption", "")
                        for domain in figure.get("domains", []):
                            cap_f.write(
                                json.dumps({"domain": domain, "text": caption})
                                + "\n"
                            )

                f.write(json.dumps(article) + "\n")
            gc.collect()
    print(f"Processed {processed_files} files")


def count_articles_with_keywords(
    dataset_path: Path = repo_root / "_results" / "data" / "pubmed_parsed_data.json",
    keywords: list[str] | None = None,
    domain_keywords: dict[str, list[str]] | None = None,
    glossary_urls: dict[str, str] | str | None = None,
) -> dict[str, int]:
    """Count articles whose figure captions mention given keywords or domains."""

    if keywords is not None:
        keyword_counts = {kw.lower(): 0 for kw in keywords}
    else:
        domain_keywords = domain_keywords or load_domain_keywords(glossary_urls)
        domain_keywords_lower = {
            domain: [kw.lower() for kw in kws]
            for domain, kws in domain_keywords.items()
        }
        keyword_counts = {domain: 0 for domain in domain_keywords}

    with dataset_path.open("r") as f:
        for line in f:
            if not line.strip():
                continue
            article = json.loads(line)
            captions = " ".join(
                fig.get("fig_caption", "") for fig in article.get("figures", [])
            ).lower()
            if keywords is not None:
                for kw in keyword_counts:
                    if kw in captions:
                        keyword_counts[kw] += 1
            else:
                for domain, kws in domain_keywords_lower.items():
                    if any(kw in captions for kw in kws):
                        keyword_counts[domain] += 1

    print("Article counts:", keyword_counts)
    return keyword_counts


def export_domain_caption_pairs(
    dataset_path: Path = repo_root / "_results" / "data" / "pubmed_parsed_data.json",
    output_path: Path = repo_root
    / "_results"
    / "data"
    / "domain_caption_pairs.jsonl",
) -> None:
    """Write ``{"domain": d, "text": caption}`` pairs for each figure.

    One line is written for every domain assigned to a figure in
    ``dataset_path``. Figures with multiple domains will produce multiple
    entries with the same caption.
    """

    with dataset_path.open("r") as src, output_path.open("w") as dest:
        for line in src:
            if not line.strip():
                continue
            article = json.loads(line)
            for figure in article.get("figures", []):
                caption = figure.get("fig_caption", "")
                for domain in figure.get("domains", []):
                    dest.write(
                        json.dumps({"domain": domain, "text": caption}) + "\n"
                    )


def export_keyword_caption_pairs(
    dataset_path: Path = repo_root / "_results" / "data" / "pubmed_parsed_data.json",
    output_path: Path = repo_root
    / "_results"
    / "data"
    / "keyword_caption_pairs.jsonl",
    keywords: list[str] | None = None,
) -> None:
    """Write captions containing ``keywords`` to ``output_path``.

    Each line of the resulting JSONL file has the structure
    ``{"text": "caption"}``. ``keywords`` defaults to ``DEFAULT_KEYWORDS``.
    """

    keywords_lower = [kw.lower() for kw in (keywords or DEFAULT_KEYWORDS)]

    with dataset_path.open("r") as src, output_path.open("w") as dest:
        for line in src:
            if not line.strip():
                continue
            article = json.loads(line)
            for figure in article.get("figures", []):
                caption = figure.get("fig_caption", "")
                if any(kw in caption.lower() for kw in keywords_lower):
                    dest.write(json.dumps({"text": caption}) + "\n")
