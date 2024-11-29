# Author: Ross Heilman
# Version: 1.0
# Date: Nov 03, 2024
# Usage:
'''
1. Set the required environment variables:
   - `PCE_FQDN`: Fully Qualified Domain Name of the Illumio PCE. Defaults to illumio-pce.corp.internal.citizensbank.com
   - `PCE_ORG`: Defaults to 1
   - `PCE_PORT`: Port number for the API. Defaults to 9443
   - `PCE_API_KEY`: API key for authentication.
   - `PCE_API_SECRET`: API secret for authentication.

2. Run the script:
 python(3) export_illumio_apps.py OR if you do not have environment variables set - python(3) export_illumio_apps.py -k your_api_key -s your_api_secret
'''
# Description: This script interacts with the Illumio API to initiate a job for retrieving application labels,
#              which are then written to a specified file.

import os
import requests
import time
import urllib3
import argparse
from typing import Dict, List, Optional, Tuple

# Disable insecure request warnings
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

class IllumioClient:
    def __init__(self, fqdn: str, org: str, port: str, api_key: str, api_secret: str):
        self.base_url = f"https://{fqdn}:{port}/api/v2"
        self.org = org
        self.auth = (api_key, api_secret)
        self.headers = {
            'Accept': 'application/json',
            'Prefer': 'respond-async'
        }

    def get_async_job_url(self) -> str:
        """Construct the async job URL for label retrieval"""
        return f"{self.base_url}/orgs/{self.org}/labels?key=app"

    def initiate_async_job(self) -> Tuple[bool, Optional[str]]:
        """Initiate an async job to retrieve labels"""
        try:
            response = requests.get(
                self.get_async_job_url(),
                auth=self.auth,
                headers=self.headers,
                verify=False
            )
            
            if response.status_code == 202:
                job_location = response.headers.get('Location')
                return True, job_location
            else:
                print(f"Failed to initiate async job: {response.status_code} - {response.text}")
                return False, None
                
        except requests.exceptions.RequestException as e:
            print(f"Error initiating async job: {str(e)}")
            return False, None

    def check_job_status(self, job_location: str) -> Tuple[bool, Optional[Dict]]:
        """Check the status of an async job"""
        try:
            full_job_location = f"{self.base_url}{job_location}"
            response = requests.get(
                full_job_location,
                auth=self.auth,
                headers=self.headers,
                verify=False
            )
            
            if response.status_code == 200:
                return True, response.json()
            else:
                print(f"Failed to check job status: {response.status_code} - {response.text}")
                return False, None
                
        except requests.exceptions.RequestException as e:
            print(f"Error checking job status: {str(e)}")
            return False, None

    def get_job_results(self, results_url: str) -> Tuple[bool, Optional[List[str]]]:
        """Retrieve and process job results"""
        try:
            full_results_url = f"{self.base_url}{results_url}"
            response = requests.get(
                full_results_url,
                auth=self.auth,
                headers=self.headers,
                verify=False
            )
            
            if response.status_code == 200:
                json_data = response.json()
                app_names = sorted([item['value'] for item in json_data if 'value' in item])
                return True, app_names
            else:
                print(f"Failed to download results: {response.status_code} - {response.text}")
                return False, None
                
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving results: {str(e)}")
            return False, None

def load_environment() -> Tuple[bool, Optional[IllumioClient]]:
    """Load environment variables and create IllumioClient instance"""
    required_vars = {
        'PCE_FQDN': os.getenv('PCE_FQDN', 'illumio-pce.corp.internal.citizensbank.com'),
        'PCE_ORG': os.getenv('PCE_ORG', 1),
        'PCE_PORT': os.getenv('PCE_PORT', 9443),
        'PCE_API_KEY': os.getenv('PCE_API_KEY'),
        'PCE_API_SECRET': os.getenv('PCE_API_SECRET')
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False, None
        
    return True, IllumioClient(
        required_vars['PCE_FQDN'],
        required_vars['PCE_ORG'],
        required_vars['PCE_PORT'],
        required_vars['PCE_API_KEY'],
        required_vars['PCE_API_SECRET']
    )

def write_apps_to_file(app_names: List[str], filename: str = 'IllumioApps.txt') -> bool:
    """Write application names to a file"""
    try:
        with open(filename, 'w') as file:
            for name in app_names:
                file.write(f"{name}\n")
        print(f"Application names have been written to {filename}")
        return True
    except IOError as e:
        print(f"Error writing to file: {str(e)}")
        return False

def main():
    # Load environment and initialize client
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Interact with Illumio API')
    parser.add_argument('-k', '--api-key', help='API key for authentication')
    parser.add_argument('-s', '--api-secret', help='API secret for authentication')
    
    # Parse the command line arguments
    args = parser.parse_args()

    # Load environment and initialize client
    success, client = load_environment()
    if not success:
        return

    # Override API key and secret with command line arguments if provided
    if args.api_key:
        client.auth = (args.api_key, client.auth[1])  # Update API key
    if args.api_secret:
        client.auth = (client.auth[0], args.api_secret)  # Update API secret
    
    # Initiate async job
    success, job_location = client.initiate_async_job()
    if not success or not job_location:
        return
    
    print(f"Async job initiated. Job location: {job_location}")
    
    # Poll for job completion
    while True:
        success, job_status = client.check_job_status(job_location)
        if not success:
            return
            
        if job_status['status'] == 'done':
            print("Job completed successfully.")
            break
        elif job_status['status'] == 'failed':
            print("Job failed.")
            return
        else:
            print("Job is still processing...")
            time.sleep(5)
    
    # Get and process results
    success, app_names = client.get_job_results(job_status['result']['href'])
    if not success or not app_names:
        return
    
    # Write results to file
    write_apps_to_file(app_names)

if __name__ == "__main__":
    main()