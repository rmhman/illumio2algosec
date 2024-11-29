# Export Illumio Traffic Flows to CSV

A Python script to export Illumio traffic flows to CSV format for AlgoSec integration.

**Author:** Ross Heilman  
**Version:** 1.0  
**Date:** Nov 04, 2024

## Overview

`export_illumio_csv.py` connects to an Illumio PCE (Policy Compute Engine), retrieves traffic flows based on configured criteria, and exports them to a CSV file format compatible with AlgoSec.
`export_illumio_apps.py` connects to Illumio and pulls all the app labels from the system and generates a file named IllumioApps.txt that can be used in other scripts

## Requirements

- Python 3.x
- Illumio SDK
- PyYAML
- urllib3

## Installation

1. Clone this repository or download the script
2. Install required dependencies:
```bash
pip install illumio-py pyyaml urllib3
```

## Configuration

### Environment Variables

The script supports the following environment variables:
- `PCE_FQDN`: PCE FQDN name
- `PCE_ORG`: PCE Organization ID
- `PCE_PORT`: PCE Port number
- `PCE_API_KEY`: PCE API Key
- `PCE_API_SECRET`: PCE API Secret

### Traffic Configuration

Create a YAML file (default: `traffic-config.yaml`) with your traffic query configuration:

```yaml
traffic_configs:
  default:
    start_date: "2023-01-01T00:00:00Z"
    end_date: "2023-12-31T23:59:59Z"
    include_sources:
      - "role=web"
    include_destinations:
      - "role=db"
    exclude_sources: []
    exclude_destinations: []
    policy_decisions:
      - potentially_blocked
      - blocked
```

## Usage

```bash
python export_illumio_csv.py [options]
```
```bash
python export_illumio_apps.py
```

### Command Line Options

Note: This is only for `export_illumio_csv.py`

```
--pce-fqdn        PCE FQDN name (default: from PCE_FQDN env var)
--pce-org         PCE Org Id (default: from PCE_ORG env var)
--pce-port        PCE Port (default: from PCE_PORT env var)
--pce-api-key     PCE API Key (default: from PCE_API_KEY env var)
--pce-api-secret  PCE API Secret (default: from PCE_API_SECRET env var)
--output-file     Output CSV file (default: illumio-algosec-export.csv)
--query-file      Query file skeleton (default: traffic-config.yaml)
--traffic-config  Name of traffic configuration to use (default: default)
--algosec-label   Illumio labels for AlgoSec app label (default: app)
--label-concat    String for concatenating labels (default: -)
--verbose, -v     Enable verbose output
```

## Output Format

The script generates a CSV file with the following columns:
- Source IP
- Source Name
- Destination IP
- Destination Name
- Service
- Service Name
- Application Name

## Filtering

The script applies the following filters to ensure data quality:
- Excludes rows with empty source or destination names
- Excludes rows with invalid service information (empty or port 0)
- Excludes rows with empty or "Unknown" application names
- Removes duplicate entries

## Example

```bash
python export_illumio_csv.py \
  --pce-fqdn pce.example.com \
  --pce-org 1 \
  --pce-port 8443 \
  --algosec-label "app,env" \
  --output-file export.csv
```

## Error Handling

- The script performs connection validation before attempting to retrieve data
- Logs errors and debug information based on verbosity level
- Returns non-zero exit code on failure

## Logging

- Use `--verbose` or `-v` flag for detailed logging
- Default logging level is INFO
- Debug logging includes detailed information about data processing and filtering