import json
import tarfile
from pathlib import Path
from typing import Optional

import pubmed_parser
import requests
from lxml import etree
from tqdm import tqdm

from .constants import PUBMED_OPEN_ACCESS_BASE_URL, PUBMED_OPEN_ACCESS_FILE_LIST_URL
from .types import PubMedFile
from .utils import fs_utils

repo_root = fs_utils.get_repo_root_path()


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

    # Get dicts from files list
    pubmed_files: list[PubMedFile] = []

    with open(file_list_path, "r") as file:
        lines = file.readlines()

        # Skip header
        lines = lines[1:]

        for line_idx, line in enumerate(lines):
            if subset_size and line_idx + 1 > subset_size:
                break

            [path, title, pmcid, pmid, code] = line.strip().split("\t")
            pubmed_file: PubMedFile = {
                "path": path,
                "title": title,
                "pmcid": pmcid,
                "pmid": pmid,
                "code": code,
            }
            pubmed_files.append(pubmed_file)

    # Create output folder
    output_folder_path.mkdir(parents=True, exist_ok=True)
    skipped_files = []

    def _get_file_size(url):
        response = requests.head(url)
        if "Content-Length" in response.headers:
            return int(response.headers["Content-Length"])
        else:
            return None

    for pubmed_file in tqdm(pubmed_files):
        file_name = pubmed_file["pmcid"] + file_extension
        file_path = output_folder_path / file_name

        # Check if the file already exists
        if file_path.exists():
            tqdm.write(f"File: {file_name} already exists. Not downloading again.")
            continue

        article_url = PUBMED_OPEN_ACCESS_BASE_URL + pubmed_file["path"]
        file_size = _get_file_size(article_url)

        if file_size is not None:
            tqdm.write(f"File: {file_name} size: {file_size} bytes")
            try:
                response = requests.get(article_url)
                response.raise_for_status()  # Raise an HTTPError for bad responses

                with open(file_path, "wb") as file:
                    file.write(response.content)

            except requests.exceptions.RequestException as e:
                tqdm.write(f"File: {file_name} Skipped! Error occurred: {e}")
                skipped_files.append(pubmed_file)

            with open(file_path, "wb") as file:
                file.write(response.content)

        else:
            tqdm.write(f"File: {file_name} Skipped! Could not get file size!")
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

    # Get dicts from files list
    file_paths = list(input_folder_path.glob(file_extension))

    print(
        f"Found {len(file_paths)} files that match {file_extension} in {input_folder_path}"
    )

    for file_path in tqdm(file_paths):
        with tarfile.open(file_path, "r:gz") as tar_file:
            # TODO: Use article folder path instead of output folder path?
            # Causes duplicate folder names since tar file contains folder
            tar_file.extractall(output_folder_path)

    print(f"Finished extracting {len(file_paths)} files")


def generate_pmc15_pipeline_outputs(
    decompressed_folder: Path = (
        repo_root / "_results" / "data" / "pubmed_open_access_files"
    ),
    output_file_path: Path = (
        repo_root / "_results" / "data" / "pubmed_parsed_data.json"
    ),
):
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    # input - path to .nxml file for each article in the article package
    # output - json object with pmid, pmc id, location (path to article package in storage blobs), figures - list of figure objects which include inline references (mentions of figure throughout the article), caption for the figure, id, label, graphic_ref (filepath to figure jpg in storage blobs), pair_id (a unique id to identify each figure in the article, using pmid + figure_id)
    def parse_single_pubmed_file(nxml_path: Path):
        print(nxml_path)

        if nxml_path is None or not nxml_path.exists():
            print("error")
            return []

        try:
            print("starting...")
            output = pubmed_parser.parse_pubmed_caption(str(nxml_path.absolute()))
            print("parsed", nxml_path)
        except AttributeError as ae:
            print("Attribute Error: " + str(ae) + " path: " + str(nxml_path))
            return []
        except etree.XMLSyntaxError as xmle:
            print("XML Syntax Error: " + str(xmle) + " path: " + str(nxml_path))
            return []
        except Exception as e:
            print("Exception: " + str(e) + " path: " + str(nxml_path))
            return []

        if not output:
            print("no output")
            return []

        else:
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

                figure_object = {
                    "fig_caption": str(figure_dict.get("fig_caption", "")),
                    "fig_id": str(figure_dict.get("fig_id", "")),
                    "fig_label": str(figure_dict.get("fig_label", "")),
                    "graphic_ref": (
                        str(location / (figure_dict["graphic_ref"] + ".jpg"))
                        if "graphic_ref" in figure_dict
                        else ""
                    ),  # set this to the path of the jpg image in storage blobs
                    "pair_id": str(pmid) + "_" + str(figure_dict.get("fig_id", "")),
                    "inline_references": ir_objects,  # add inline references
                }

                figures.append(figure_object)

            article = {
                "pmid": pmid,
                "pmc": pmc,
                "location": str(location),
                "figures": figures,
            }

            return [article]

    with output_file_path.open("w+") as f:
        for idx, nxml_file in enumerate(decompressed_folder.rglob("*.nxml")):
            parsed = parse_single_pubmed_file(nxml_file)

            for article in parsed:
                for figure in article["figures"]:
                    # remove inline references since we're not using them
                    figure.pop("inline_references")

                f.write(json.dumps(article) + "\n")

    print(f"Processed {idx+1} files")
