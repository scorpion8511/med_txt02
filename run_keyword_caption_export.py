from __future__ import annotations

import argparse
from pathlib import Path

from pmc15_pipeline.data import (
    decompress_pubmed_files,
    download_pubmed_file_list,
    download_pubmed_files_from_list,
    export_keyword_captions_from_archives_to_csv,
    export_keyword_captions_to_csv,
)

# Step 1: Download PubMed file list (optional if already downloaded)
# download_pubmed_file_list()

# Step 2: Download a subset of files (optional if already downloaded)
# download_pubmed_files_from_list(
#     file_list_path=Path("D:/dew_med/med_txt02/pm_ids/pmc_result_med00_sorted_part13.txt")
# )

# Step 3: Decompress the downloaded files (extract only .nxml to avoid images)
# decompress_pubmed_files(extract_nxml_only=True)

# Step 4: Export matching captions to CSV
keywords = [
    "pathology",
    "whole slide image",
    "H&E",
    "x-ray",
    "MRI",
    "endoscopy",
    "gastrology",
    "ultrasound",
    "histopathology",
    "Adenocarcinoma",
    "Anaplastic",
    "Acute Promyelocytic Leukemia",
    "Anaplastic Thyroid Cancer",
    "Breast Cancer",
    "Basal Cell Carcinoma",
    "Bone Marrow",
    "BRCA",
    "Biopsy",
    "carcinoma",
    "Carotid Body Tumor",
    "Carcinoembryonic Antigen",
    "Chronic Granulocytic Leukemia",
    "Chromosome",
    "Cervical Intraepithelial Neoplasia",
    "Carcinoma In Situ",
    "Choroid Plexus Carcinoma",
    "Colorectal Carninoma",
    "Circulating Tumor Cell",
    "Epstein-Barr Virus",
    "EBV",
    "Epidermal Growth",
    "Extraskeletal Myxoid Chondrosarcoma",
    "Formalin Fixed Paraffin Embedded",
    "FFPE",
    "Gastrointestinal Stromal Tumors",
    "GIST",
    "Hepatocellular carcinoma",
    "Human Epidermal Growth Factor",
    "Hematoxylin and Eosin",
    "Hereditary Nonpolyposis Colon Cancer",
    "Head and Neck Squamous Cell Carcinoma",
    "Immunohistochemistry",
    "Lentigo Maligna Melanoma",
    "Malignant",
    "Metastasis",
    "Malignant Melanoma",
    "Molecular Diagnostics",
    "Nevoid Basal Cell Carcinoma Syndrome",
    "Nodular Melanoma",
    "Non Melanoma Skin Cancer",
    "Non-Small Cell Lung Cancer",
    "Renal Cell Carcinoma",
    "Sarcoma",
    "Squamous Cell Carcinoma",
    "Small Cell Lung Cancer",
    "Transitional Cell Carcinoma",
    "ALARA",
    "ARRT",
    "ASRT",
    "mammography",
    "radiography",
    "angiography",
    "angioplasty",
    "arthrogram",
    "barium",
    "chemoembolization",
    "fluroscopy",
    "hysterosalpingography",
    "hysterosonography",
    "myelogram",
    "pancreatography",
    "pyelogram",
    "radiopaque",
    "urography",
    "vasography",
    "c-arm",
    "dosimetrists",
    "esophagram",
    "fluoroscopy",
    "gantry",
    "hypoattenuating",
    "irradiation",
    "intravenous pyelography",
    "lymphangiography",
    "low-dose computed tomography",
    "magnetic resonance angiography",
    "myelography",
    "neuroradiology",
    "positron emission tomography",
    "percutaneous transhepatic cholangiography",
    "radiation",
    "scintigraphy",
    "stereotactic biopsy",
    "venogram",
    "volumetric modulated arc therapy",
    "artifact",
    "conformal radiation therapy",
    "cyclotron",
    "double-contrast barium enema",
    "endoscopic retrograde cholangiopancreatography",
    "fluoroscope",
    "image recording plate",
    "magnetic resonance imaging",
    "monoclonal antibody therapy",
    "MR spectroscopy",
    "angiogram",
    "Abdomen",
    "Achalasia",
    "Aerophagia",
    "Antispasmodics",
    "Bile",
    "Biliary tract",
    "Borborygmi",
    "Brain-gut axis",
    "Capsule Endoscopy",
    "Celiac disease",
    "Colectomy",
    "Colitis",
    "Colonoscopy",
    "Colon",
    "Colostomy",
    "Constipation",
    "Crohn's disease",
    "Cytokines",
    "Diarrhea",
    "Duodenum",
    "Dysphagia",
    "Diverticula",
    "Endoscope",
    "Endoscopy",
    "Enteritis",
    "Enterocolitis",
    "Enteroscopy",
    "Enteric nervous system",
    "Eosinophilic gastroenteritis",
    "Epithelium",
    "Esophagus",
    "Esophagitis",
    "Fistula",
    "Gastric",
    "Gastric Juices",
    "Gastritis",
    "Gastroenteritis",
    "Gastroparesis",
    "Gastroscopy",
    "Ileum",
    "Ileostomy",
    "Ingestion",
    "Laparoscopy",
    "Lymphocyte",
    "Peptic ulcer",
    "Polyp",
    "Prokinetic",
    "Protease",
    "Rectum",
    "Reuptake",
    "Villi",
]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export PubMed figure captions that match keywords into a CSV file."
        )
    )
    parser.add_argument(
        "--decompressed-folder",
        action="append",
        type=Path,
        default=[],
        help=(
            "Folder containing decompressed PubMed files. "
            "Repeat the flag to process multiple folders."
        ),
    )
    parser.add_argument(
        "--compressed-folder",
        action="append",
        type=Path,
        default=[],
        help=(
            "Folder containing compressed .tar.gz PubMed files. "
            "Repeat the flag to process multiple folders."
        ),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("_results/data/pubmed_caption_keywords.csv"),
        help="CSV output path.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append captions to an existing CSV instead of creating a new one.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output CSV even if it already exists.",
    )
    parser.add_argument(
        "--decompress",
        action="store_true",
        help="Decompress downloaded files before exporting captions.",
    )
    parser.add_argument(
        "--skip-pubmed-parser",
        action="store_true",
        help="Skip pubmed_parser and use XML fallback parsing for captions.",
    )
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Allow duplicate captions in the output CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.decompress:
        decompress_pubmed_files(extract_nxml_only=True)

    compressed_folders = args.compressed_folder
    decompressed_folders = args.decompressed_folder

    if not compressed_folders and not decompressed_folders:
        decompressed_folders = [Path("_results/data/pubmed_open_access_files")]

    output_exists = args.output_csv.exists()
    if args.append and args.overwrite:
        raise SystemExit("Choose either --append or --overwrite, not both.")

    if output_exists and not args.append and not args.overwrite:
        print(
            f"Output CSV {args.output_csv} exists; appending new captions. "
            "Use --overwrite to start fresh."
        )
        append_next = True
    else:
        append_next = args.append

    dedupe = not args.no_dedupe

    for folder in compressed_folders:
        export_keyword_captions_from_archives_to_csv(
            keywords=keywords,
            compressed_folder=folder,
            output_csv_path=args.output_csv,
            append=append_next,
            skip_pubmed_parser=args.skip_pubmed_parser,
            dedupe=dedupe,
        )
        append_next = True

    for folder in decompressed_folders:
        export_keyword_captions_to_csv(
            keywords=keywords,
            decompressed_folder=folder,
            output_csv_path=args.output_csv,
            append=append_next,
            skip_pubmed_parser=args.skip_pubmed_parser,
            dedupe=dedupe,
        )
        append_next = True


if __name__ == "__main__":
    main()
