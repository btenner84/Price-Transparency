# Hospital Price Transparency File Finder

This tool automatically finds, validates, and tracks hospital price transparency files across the United States. It uses a combination of web search, web crawling, LLM-based analysis, and rule-based validation to locate and verify price transparency files for hospitals.

## Features

- **Automated Search**: Uses SerpAPI to search for hospital price transparency files
- **Intelligent Analysis**: Leverages AI to analyze search results and identify promising links
- **Web Crawling**: Crawls websites to find price transparency file links
- **File Validation**: Validates that files contain actual pricing data
- **Hospital Matching**: Ensures files match the correct hospital
- **Status Tracking**: Tracks the status of each hospital search in a SQLite database
- **Concurrent Processing**: Processes multiple hospitals in parallel
- **Detailed Logging**: Comprehensive logging of all operations
- **CLI Interface**: Easy-to-use command-line interface

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/price-finder.git
cd price-finder
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright dependencies:
```bash
python -m playwright install
```

4. Set up API keys:
```bash
export SERPAPI_KEY="your_serpapi_key"
export OPENAI_API_KEY="your_openai_key"
# or
export ANTHROPIC_API_KEY="your_anthropic_key"
```

## Usage

### Basic Usage

```bash
# Search for price transparency files for hospitals in a JSON file
python price_finder_cli.py --input-file hospital_data.json --limit 10

# Search for specific states
python price_finder_cli.py --input-file hospital_data.json --state CA NY TX --limit 20

# Get statistics
python price_finder_cli.py --mode stats

# Update master dataset with found price files
python price_finder_cli.py --mode update --output-file master_hospital_data.json
```

### Advanced Options

```bash
# Use a specific LLM provider
python price_finder_cli.py --input-file hospital_data.json --llm-provider anthropic

# Increase concurrency for faster processing
python price_finder_cli.py --input-file hospital_data.json --concurrency 10

# Process hospitals with pending status from the database
python price_finder_cli.py --use-pending --limit 50

# Use a custom configuration file
python price_finder_cli.py --input-file hospital_data.json --config-file config.json
```

### Configuration

You can customize the pipeline behavior by creating a JSON configuration file:

```json
{
  "max_search_results": 10,
  "link_confidence_threshold": 0.6,
  "content_validation_threshold": 0.8,
  "hospital_match_threshold": 0.8,
  "min_price_columns": 1,
  "min_rows": 10
}
```

## Input Data Format

The tool accepts hospital data in JSON format. The file can be either:

1. A dictionary with state codes as keys:
```json
{
  "CA": [
    {
      "NAME": "Hospital Name",
      "STATE": "CA",
      "CITY": "City Name",
      "health_sys_name": "Health System Name"
    }
  ]
}
```

2. A list of hospitals:
```json
[
  {
    "NAME": "Hospital Name",
    "STATE": "CA",
    "CITY": "City Name",
    "health_sys_name": "Health System Name"
  }
]
```

## Project Structure

- `price_finder_cli.py`: Command-line interface
- `src/`
  - `models/`: Data models
  - `searchers/`: Web search and crawling components
  - `llm/`: LLM integration for analysis
  - `validators/`: File and hospital validation
  - `pipeline/`: Main orchestration pipeline
  - `utils/`: Utility functions

## Requirements

- Python 3.8+
- SerpAPI account
- OpenAI or Anthropic API key
- Internet connection

## License

MIT License

## Notes

- The tool respects robots.txt when crawling websites
- Default concurrency is set to 5 to avoid overwhelming search APIs
- Files are downloaded to the `downloads` directory by default
- Results are stored in a SQLite database for persistence
- Tool uses both rule-based and LLM-based validation for better accuracy 