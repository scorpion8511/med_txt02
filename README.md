# BiomedCLIP Data Pipeline

[![Code License](https://img.shields.io/badge/Code%20License-MIT%20License-red)](LICENSE)

*A pipeline to construct millions of image-caption figures from PubMed.*

[[NEJM AI Article](https://ai.nejm.org/stoken/default+domain/9VPKUGJYJ5BPFXY83IBS/full?redirectUri=doi/full/10.1056/AIoa2400640)] 

**BiomedCLIP: a multimodal biomedical foundation model pretrained from fifteen million scientific image-text pairs** <br>

Sheng Zhang, Yanbo Xu, Naoto Usuyama, Hanwen Xu, Jaspreet Bagga, Robert Tinn, Sam Preston, Rajesh Rao, Mu Wei, Naveen Valluri, Cliff Wong, Andrea Tupini, Yu Wang, Matt Mazzola, Swadheen Shukla, Lars Liden, Jianfeng Gao, Angela Crabtree, Brian Piening, Carlo Bifulco, Matthew P. Lungren, Tristan Naumann, Sheng Wang, Hoifung Poon

<p align="center">
    <img src="images/pmc_15m_pipeline.jpg" width="80%"> <br>
</p>


This repository hosts the **BiomedCLIP Data Pipeline**, which automatically downloads and processes a set of articles from the PubMed Central Open Access dataset. The end result is a JSONL file containing figures and associated captions, which can be used to train the **BiomedCLIP** model.

For a hands-on demonstration, refer to the [example notebook](run_pmc15_pipeline.ipynb).


## Environment Setup 

```bash
# it is recmmended to use a virtual environment but not required
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

## Downloading and Decompressing Articles

```python
from pathlib import Path
from pmc15_pipeline.data import (
    download_pubmed_file_list,
    download_pubmed_files_from_list,
    decompress_pubmed_files,
)

download_pubmed_file_list()
download_pubmed_files_from_list(subset_size=100)  # streamed in chunks
# Or download only specific PMCIDs listed in a text file
# download_pubmed_files_from_list(pmcids_path=Path("pmc_ids.txt"))
# The PMCID file must exist and contain one ID per line; IDs are
# matched case-insensitively.
decompress_pubmed_files()  # skips archives already extracted and continues past errors
generate_pmc15_pipeline_outputs()  # streams captions to keep memory usage low
```

## Filtering Captions by Keyword

`generate_pmc15_pipeline_outputs` can restrict the dataset to figures whose
captions mention specific terms. By default it keeps only captions containing
keywords from these imaging domains:

- **pathology:** "pathology", "whole slide image", "H&E"
- **x-ray:** "x-ray"
- **endoscopy:** "endoscopy", "gastrology"
- **ultra:** "ultrasound"
- **mri:** "MRI"

Each figure written to `pubmed_parsed_data.json` includes a `domains` array, and
the enclosing article lists all domains found across its figures. The function
also writes `_results/data/domain_caption_pairs.jsonl`, containing one line per
figure-domain combination with the structure `{ "domain": "pathology", "text": "caption" }`.
Figures lacking any of the keywords are skipped entirely, so a small sample of
articles may yield an empty output file if none of their captions mention the
default terms. Captions containing common animal terms (for example “mouse” or
“rat”) are omitted to focus on human-related content. Set
`exclude_keywords=None` to include them.
You can also fetch domain keyword mappings from remote JSON glossaries by
providing a `glossary_urls` dictionary. Each key is a domain name and each value
is a URL returning a JSON array of keywords for that domain. Passing a single
URL is still supported for backward compatibility.

```python
from pmc15_pipeline.data import generate_pmc15_pipeline_outputs

generate_pmc15_pipeline_outputs()  # Use defaults shown above

# Or provide your own list of keywords
# generate_pmc15_pipeline_outputs(keywords=["custom term"])

# Include captions mentioning animals
# generate_pmc15_pipeline_outputs(exclude_keywords=None)

# Pull domain keywords from remote glossaries
# generate_pmc15_pipeline_outputs(
#     glossary_urls={
#         "pathology": "https://example.com/pathology_keywords.json",
#         "mri": "https://example.com/mri_keywords.json",
#     }
# )

# Run in 5k-file batches
# batch_size = 5000
# for batch in range(num_batches):
#     generate_pmc15_pipeline_outputs(
#         start_index=batch * batch_size,
#         max_files=batch_size,
#         append=batch > 0,
#     )
```

## Counting Articles by Domain

After generating `pubmed_parsed_data.json`, you can see how many articles
mention each domain in their figure captions:

```python
from pmc15_pipeline.data import count_articles_with_keywords

count_articles_with_keywords()

# Use the same remote glossaries as above
# count_articles_with_keywords(
#     glossary_urls={
#         "pathology": "https://example.com/pathology_keywords.json",
#         "mri": "https://example.com/mri_keywords.json",
#     }
# )
```

Provide your own list of terms with the `keywords` argument if you want to
search for different phrases instead of the preset domains.

## Exporting Domain-Caption Pairs

To create a lightweight dataset for domain classification, write one line per
figure with its domain and caption text:

`generate_pmc15_pipeline_outputs` writes this file automatically; if you need
to recreate it from an existing dataset, call:

```python
from pmc15_pipeline.data import export_domain_caption_pairs

export_domain_caption_pairs()
```

## Exporting Captions with Default Keywords

If you already have `pubmed_parsed_data.json` but only want the captions that
mention the default imaging-domain keywords, create a lightweight JSONL file:

```python
from pmc15_pipeline.data import export_keyword_caption_pairs

export_keyword_caption_pairs()
```

Each line in `_results/data/keyword_caption_pairs.jsonl` has the form
`{ "text": "caption" }`. Pass your own list of `keywords` to filter for
different terms.

## Reference
```bibtex
@article{zhang2024biomedclip,
  title={A Multimodal Biomedical Foundation Model Trained from Fifteen Million Image–Text Pairs},
  author={Sheng Zhang and Yanbo Xu and Naoto Usuyama and Hanwen Xu and Jaspreet Bagga and Robert Tinn and Sam Preston and Rajesh Rao and Mu Wei and Naveen Valluri and Cliff Wong and Andrea Tupini and Yu Wang and Matt Mazzola and Swadheen Shukla and Lars Liden and Jianfeng Gao and Angela Crabtree and Brian Piening and Carlo Bifulco and Matthew P. Lungren and Tristan Naumann and Sheng Wang and Hoifung Poon},
  journal={NEJM AI},
  year={2024},
  volume={2},
  number={1},
  doi={10.1056/AIoa2400640},
  url={https://ai.nejm.org/doi/full/10.1056/AIoa2400640}
}
```

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
