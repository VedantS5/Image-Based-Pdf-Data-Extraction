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

## Installation

```bash
# Clone the repository
git clone https://github.com/VedantS5/analyst-report-vision.git
cd analyst-report-vision

# Install dependencies
pip install -r requirements.txt
```

## Project Structure

The repository contains these main components:

```
02_image.py                 # Main script for PDF processing
ollama_server_deployment.sh # Script to deploy Ollama instances
config.json                 # Configuration file
requirements.txt            # Required Python packages
setup.py                    # Package installation script
LICENSE                     # MIT License
```

> **Note:** The original development paths (`/N/project/fads_ng/analyst_reports_project/...`) referenced in code comments are specific to Indiana University's Quartz computing environment and should be adapted to your local environment.

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

### System Requirements

This tool is designed to work with GPU acceleration for optimal performance:

- **Recommended**: NVIDIA GPUs with CUDA support
- Python 3.8+
- [Ollama](https://github.com/jmorganca/ollama) for running LLMs locally
- At least 16GB RAM (32GB+ recommended for processing large PDFs)

### For HPC/Cluster Users (Indiana University-specific)

> **Note:** The following commands are specific to Indiana University's computing resources. If you're using a different system, refer to your system's documentation for equivalent commands.

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
```

### General Setup (All Systems)

1. Ensure you have Ollama installed
   ```bash
   # For Linux/macOS
   curl -fsSL https://ollama.com/install.sh | sh
   
   # For other systems, see: https://github.com/jmorganca/ollama
   ```

2. Clone this repository and install dependencies:
   ```bash
   git clone https://github.com/VedantS5/analyst-report-vision.git
   cd analyst-report-vision
   pip install -r requirements.txt
   ```

3. Make the deployment script executable:
   ```bash
   chmod +x ollama_server_deployment.sh
   ```

## Usage

### 1. Deploy Ollama Instances

First, deploy one or more Ollama instances using the deployment script:

```bash
# Deploy Ollama instances optimized for image processing (4 GPUs)
./ollama_server_deployment.sh image

# Or for specific GPU configurations (if running on IU Quartz H100 GPUs)
./ollama_server_deployment.sh h100

# For other GPU types (v100, a100, qwq)
./ollama_server_deployment.sh [GPU_TYPE]
```

> **Note for non-HPC users:** If running on a personal computer, you may need to modify the deployment script or simply run Ollama directly with `ollama serve` in a separate terminal.

### 2. Process PDFs

Process a single PDF or a directory of PDFs:

```bash
# Process a single PDF
python 02_image.py /path/to/your_file.pdf

# Process all PDFs in a directory
python 02_image.py /path/to/pdfs/directory

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

By default, the tool processes PDFs from the specified input path and outputs CSV results based on the configuration.

Input and output paths can be customized in the `config.json` file:

```json
{
  "output": {
    "csv_filename": "author_extraction_results.csv"
  },
  ...
}
```

The output CSV will be created in the current working directory unless a full path is specified in the configuration.

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

## Environment Setup

### GPU Configuration

The deployment script can be configured for different GPU setups:

- `image`: Optimized for image processing (recommended) - 1 Ollama instance per GPU
- `h100`: Optimized for H100 GPUs - 8 instances per GPU
- `a100`: Optimized for A100 GPUs - 4 instances per GPU
- `v100`: Optimized for V100 GPUs - 3 instances per GPU
- `qwq`: Generic configuration for other GPU types - 2 instances per GPU

### Local Environment Configuration

For local installations, you may need to modify these settings:

1. Edit `ollama_server_deployment.sh` to match your GPU configuration
2. Update the `config.json` file with appropriate paths for your system
3. If running without multiple GPUs, you can use a simpler setup with a single Ollama instance

### Using Your Own LLM Models

The system is configured to use the `gemma3:27b` model by default. If you want to use a different model:

1. Modify the model name in `config.json`
2. Make sure your model has multimodal capabilities (image understanding)
3. Update the `ollama_server_deployment.sh` script to pull your preferred model

## Troubleshooting

- **No Ollama instances detected**: Ensure the ollama_server_deployment.sh script has been run and check server logs for GPU availability
- **Slow processing**: Check that multiple Ollama instances are running and auto-detection is enabled
- **Poor extraction quality**: Try adjusting the prompts in config.json
- **GPU memory issues**: Reduce the number of Ollama instances if you encounter CUDA out-of-memory errors
- **Server-specific paths**: Make sure all path references match the server directory structure
- **Network connectivity**: If running from a client, ensure proper network access to the server instances

