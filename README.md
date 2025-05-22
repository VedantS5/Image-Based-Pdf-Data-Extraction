# Analyst Report Vision

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Extract author metadata from PDF analyst reports using multimodal LLMs and image processing. Handles complex document layouts with parallel GPU acceleration.

This tool extracts author information from PDF research reports using Ollama and large language models with image processing capabilities. It's designed to handle a variety of research report formats and automatically identify authors, their titles, and contact information.

## Overview

This specialized tool extracts author information from financial analyst reports using multimodal LLMs with image processing capabilities. It processes PDF documents as images to identify authors, titles, contact information, and report metadata even when text extraction fails.

The system consists of three main components:

1. **02_image.py**: The main Python script that processes PDFs, extracts images, and uses Ollama to identify authors
2. **ollama_server_deployment.sh**: Shell script to deploy Ollama instances across available GPUs
3. **config.json**: Configuration file for customizing the behavior of the extraction tool

## Project Location

On the server, the project is located at:
```
/N/project/fads_ng/analyst_reports_project/codes/02/image_based/
```

The main components are:
```
/N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py
/N/project/fads_ng/analyst_reports_project/codes/02/image_based/ollama_server_deployment.sh
/N/project/fads_ng/analyst_reports_project/codes/02/image_based/config.json
```

## Features

- **Parallel Processing**: Distributes work across multiple Ollama instances for high throughput
- **Auto-detection**: Automatically detects running Ollama instances and distributes workload
- **Document Type Detection**: Identifies compilation reports, termination reports, etc.
- **Institution Detection**: Recognizes reports from specific financial institutions
- **Email Validation**: Corrects and validates extracted email addresses
- **First Page Prioritization**: Gives higher weight to authors found on the first page
- **Customizable Prompts**: All LLM prompts can be modified via the config file

## Prerequisites

- Python 3.8+
- PyMuPDF (fitz)
- Requests library
- Ollama with a compatible multimodal LLM (gemma3:27b recommended)
- H100 GPUs for optimal performance

## Setup

### Requesting Interactive Computing Resources

Before running the code, you need to request appropriate computing resources based on your needs:

#### V100 Quartz:
```bash
srun -p gpu-debug --cpus-per-task 20 --gpus 4 --mem 40GB -A r01352 --time 1:00:00 --pty bash
```

#### A100 Big Red 200:
```bash
srun -p gpu-debug --cpus-per-task 30 --gpus 4 --mem 60GB -A r01352 --time 1:00:00 --pty bash
```

#### H100 Quartz Hopper:
```bash
srun -p hopper --cpus-per-task 40 --gpus 4 --mem 120GB -A r01352 --time 1:00:00 --pty bash

Prerequisites:

1. Ensure you have Ollama installed
2. Clone this repository
3. Install Python dependencies:
   ```bash
   pip install pymupdf requests
   ```
4. Make the deployment script executable:
   ```bash
   chmod +x ollama_server_deployment.sh
   ```

## Usage

### 1. Deploy Ollama Instances

First, deploy one or more Ollama instances using the deployment script:

```bash
# Navigate to the directory where the deployment script is located
cd /N/project/fads_ng/analyst_reports_project/codes/02/image_based/

# For image processing with 4 GPUs (recommended)
./ollama_server_deployment.sh image

# Or for other configurations
./ollama_server_deployment.sh h100
```

### 2. Process PDFs

Process a single PDF or a directory of PDFs:

```bash
# Process a single PDF
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/your_file.pdf

# Process all PDFs in a directory
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /N/project/fads_ng/analyst_reports_project/data/pdfs/

# Process with a specific config file
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --config /path/to/custom_config.json

# Process only specific pages (pages 1-3 only)
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --page-mode range --page-range 1 3

# Process only the first 2 pages
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --page-mode first_n --first-n 2

# Process a range of pages but always include first page
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --page-mode range --page-range 5 10 --always-first

# Enable metadata filtering to skip termination reports
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --metadata-filtering

# Use a custom metadata CSV file
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --metadata-csv /path/to/custom_metadata.csv

# Disable metadata filtering (if enabled in config)
python /N/project/fads_ng/analyst_reports_project/codes/02/image_based/02_image.py /path/to/pdfs --no-metadata-filtering
```

### 3. Expected Input/Output

By default, the tool processes PDFs from:
```
/N/project/fads_ng/analyst_reports_project/data/pdfs/
```

And outputs CSV results to:
```
/N/project/fads_ng/analyst_reports_project/results/author_extraction_results.csv
```

You can customize these paths in the configuration file.

### 4. Configuration

The system uses a JSON-based configuration system, replacing the previous config.py approach. You can customize the behavior by editing the `config.json` file in the project directory. The configuration has a nested structure with the following main sections:

- **ollama**: Settings for the Ollama API
  - `fallback_api_url`: Fallback URL used when auto-detection is disabled
  - `model`: Default model to use (gemma3:27b recommended)
  - `timeout`: API timeout in seconds
  - `auto_detect`: Whether to automatically detect Ollama instances

- **pdf_processing**: Settings for PDF processing
  - `pages_to_process`: Configuration for which pages to process
    - `mode`: Page selection mode (`all`, `range`, or `first_n`)
    - `first_n`: When mode is "first_n", process this many pages (0 means all)
    - `range`: When mode is "range", process pages in this range (e.g., [1, 3] for pages 1-3, inclusive)
    - `always_include_first`: Whether to always include the first page regardless of other settings
  - `support_pages`: Number of additional pages to extract text from for context
  - `image_scale`: Scale factor for PDF image conversion

- **output**: Output file configuration
  - `csv_filename`: Path to the output CSV file

- **features**: Toggle specific features on/off
  - `document_type_detection`: Enable detection of document types
  - `institution_detection`: Enable detection of publishing institution
  - `email_validation`: Enable email domain correction
  - `prioritize_first_page`: Give higher weight to authors on first page
  - `metadata_filtering`: Skip processing documents based on metadata CSV

- **metadata**: Configuration for metadata-based filtering
  - `csv_path`: Path to the metadata CSV file
  - `skip_terms`: List of terms to search for in headlines to skip processing
  - `id_extraction_pattern`: Regex pattern to extract document ID from filenames

- **debug**: Debug settings
  - `enabled`: Enable debug mode for verbose output

- **prompts**: Customize the LLM prompts
  - `compilation_report`: Template for compilation reports
  - `standard_report`: Template for standard reports
  - `credit_suisse_specific`: Special formatting for Credit Suisse reports

Example configuration:

```json
{
  "ollama": {
    "fallback_api_url": "http://localhost:11434/api/generate",
    "model": "gemma3:27b",
    "timeout": 180,
    "auto_detect": true
  },
  "pdf_processing": {
    "pages_to_process": {
      "mode": "all",
      "first_n": 0,
      "range": [1, 1],
      "always_include_first": true
    },
    "support_pages": 3,
    "image_scale": 2.0
  },
  "output": {
    "csv_filename": "author_extraction_results.csv"
  },
  "metadata": {
    "csv_path": "/N/project/fads_ng/analyst_reports_project/data/reports_metadata.csv",
    "skip_terms": ["termination", "dropping", "terminate", "drop coverage"],
    "id_extraction_pattern": "key_(\\d+)"
  },
  "features": {
    "document_type_detection": true,
    "institution_detection": true,
    "email_validation": true,
    "prioritize_first_page": true
  },
  "debug": {
    "enabled": false
  }
}
```

You can also specify a custom config file when running the script:

```bash
python 02_image.py path/to/pdfs --config custom_config.json
```

## How It Works

1. **ollama_server_deployment.sh**: 
   - Deploys multiple Ollama instances across available GPUs
   - Each instance listens on a different port (11434-11437)
   - Loads the appropriate model (gemma3:27b for image mode)

2. **02_image.py**:
   - Loads configuration from config.json
   - Auto-detects running Ollama instances
   - Processes PDFs by converting pages to images
   - Sends images to Ollama instances with structured prompts
   - Parses returned JSON to extract author information
   - Writes results to a CSV file

## Output Format

The script generates a CSV file with the following columns:
- PDF Filename
- Author Name
- Author Title
- Author Email
- Page Found

## Performance Optimization

For optimal performance:
- Use the "image" mode with multiple GPUs
- Process large batches of PDFs at once
- Adjust the number of pages to process if only first few pages contain author information

## Server Environment Setup

This tool is configured for the specific computing environment at:
`/N/project/fads_ng/`

### GPU Configuration

The deployment script is optimized for the H100 GPU setup on the server. The system has 4 H100 GPUs that can run multiple Ollama instances concurrently for parallel processing.

### Model Storage

LLM models are stored in:
```
/N/project/fads_ng/ollama_setup/ollama_models
```

### Data Paths

Default data directories:
- Input PDFs: `/N/project/fads_ng/analyst_reports_project/data/pdfs/`
- Results: `/N/project/fads_ng/analyst_reports_project/results/`

## Troubleshooting

- **No Ollama instances detected**: Ensure the ollama_server_deployment.sh script has been run and check server logs for GPU availability
- **Slow processing**: Check that multiple Ollama instances are running and auto-detection is enabled
- **Poor extraction quality**: Try adjusting the prompts in config.json
- **GPU memory issues**: Reduce the number of Ollama instances if you encounter CUDA out-of-memory errors
- **Server-specific paths**: Make sure all path references match the server directory structure
- **Network connectivity**: If running from a client, ensure proper network access to the server instances

