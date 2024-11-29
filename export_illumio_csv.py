#!/usr/bin/env python3
# Author: Ross Heilman
# Version: 1.0
# Date: Nov 03, 2024
# Usage: python3 illumio_export.py [--pce-fqdn FQDN] [--output-file FILE] [-v]
# Description: Exports Illumio traffic flows to CSV format for AlgoSec integration.
import sys
import os
import argparse
import logging
import csv
import yaml
import urllib3
from illumio import *
from typing import List, Dict, Set, Tuple, Optional

class IllumioExporter:
    def __init__(self, args):
        self.args = args
        self.pce = None
        self.label_href_map = {}
        self.value_href_map = {}
        self.label_cache = {}
        
        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Setup logging
        log_level = logging.DEBUG if args.verbose else logging.INFO
        logging.basicConfig(stream=sys.stdout, level=log_level)

    def setup_pce_connection(self) -> bool:
        """Setup connection to PCE and initialize label caches"""
        self.pce = PolicyComputeEngine(
            self.args.pce_fqdn,
            port=self.args.pce_port,
            org_id=self.args.pce_org
        )
        self.pce.set_credentials(self.args.pce_api_key, self.args.pce_api_secret)
        self.pce.labels.get(verify=False)
        
        if not self.pce.check_connection():
            logging.error("Connection to PCE failed.")
            return False
            
        logging.info("Connection to PCE successful.")
        return True

    def build_label_maps(self):
        """Build label mapping dictionaries"""
        for label in self.pce.labels.get():
            self.label_cache[label.href] = label
            self.label_href_map[label.href] = {"key": label.key, "value": label.value}
            self.value_href_map[f"{label.key}={label.value}"] = label.href

    def load_query_config(self) -> Dict:
        """Load and parse query configuration from YAML"""
        with open(self.args.query_file, 'r') as queryfile:
            config = yaml.safe_load(queryfile)
        
        traffic_config = config['traffic_configs'][self.args.traffic_config]
        return traffic_config

    def build_traffic_query(self, query_config: Dict) -> TrafficQuery:
        """Build traffic query from configuration"""
        query_start = query_config.pop('start_date')
        query_end = query_config.pop('end_date')

        include_sources = [self.value_href_map[s] for s in query_config.pop('include_sources', [])]
        include_destinations = [self.value_href_map[s] for s in query_config.pop('include_destinations', [])]
        exclude_sources = [self.value_href_map[s] for s in query_config.pop('exclude_sources', [])]
        exclude_destinations = [self.value_href_map[s] for s in query_config.pop('exclude_destinations', [])]

        return TrafficQuery.build(
            query_start,
            query_end,
            include_sources=include_sources,
            include_destinations=include_destinations,
            exclude_sources=exclude_sources,
            exclude_destinations=exclude_destinations,
            policy_decisions=query_config['policy_decisions']
        )

    def process_flow(self, flow) -> Optional[Tuple]:
        """Process individual traffic flow and return formatted row if valid"""
        src = flow.src.ip
        dst = flow.dst.ip
        service_name = ''
        
        src_name = flow.src.workload.hostname if flow.src.workload else src
        dst_name = flow.dst.workload.hostname if flow.dst.workload else dst

        # Get service information
        service = self._get_service_info(flow.service)
        if not service:  # Skip if no valid service info
            return None

        # Get application name
        app = self._get_app_name(flow.dst.workload)
        if not app or app == "Unknown":  # Skip if no valid app name
            return None

        # Skip if source or destination names are empty
        if not src_name or not dst_name:
            return None

        return (src, src_name, dst, dst_name, service, service_name, app)

    def _get_app_name(self, workload) -> str:
        """Extract application name from workload labels"""
        if not workload or not workload.labels:
            return ''

        parsed_labels = self.args.algosec_label.split(",")
        labels = [self.label_cache[x.href] for x in workload.labels if x.href in self.label_cache]
        label_dict = dict(map(lambda x: (x.key, x.value), labels))
        
        applist = []
        for label in parsed_labels:
            applist.append(label_dict.get(label, "Unknown"))
        
        return self.args.label_concat.join(applist)

    def _get_service_info(self, service) -> str:
        """Format service information"""
        if not service or not hasattr(service, 'port') or service.port == 0:
            return ''

        proto_map = {6: 'tcp', 17: 'udp', 1: 'icmp'}
        proto = proto_map.get(service.proto, service.proto)
        return f"{proto}/{service.port}"

    def export_data(self) -> bool:
        """Main export function"""
        if not self.setup_pce_connection():
            return False

        self.build_label_maps()
        query_config = self.load_query_config()
        traffic_query = self.build_traffic_query(query_config)

        result = self.pce.get_traffic_flows_async(
            query_name='daily_traffic',
            traffic_query=traffic_query
        )

        logging.info(f"Number of records retrieved from PCE: {len(result)}")

        # Process flows and collect unique valid rows
        data = set()
        for flow in result:
            row = self.process_flow(flow)
            if row:  # Only add valid rows
                data.add(row)

        # Write to CSV
        header = ["Source IP", "Source Name", "Destination IP", "Destination Name", 
                 "Service", "Service Name", "Application Name"]
        
        with open(self.args.output_file, 'w', newline='') as output_file:
            writer = csv.writer(output_file)
            writer.writerow(header)
            writer.writerows(data)

        logging.info(f"Final record count after filtering and deduplication: {len(data)}")
        return True

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--pce-fqdn', help='PCE FQDN name', 
                       default=os.environ.get('PCE_FQDN'))
    parser.add_argument('--pce-org', help='PCE Org Id', 
                       default=os.environ.get('PCE_ORG', '1'), type=int)
    parser.add_argument('--pce-port', help='PCE Port', 
                       default=os.environ.get('PCE_PORT', '9443'), type=int)
    parser.add_argument('--pce-api-key', help='PCE API Key', 
                       default=os.environ.get('PCE_API_KEY', ''))
    parser.add_argument('--pce-api-secret', help='PCE API secret', 
                       default=os.environ.get('PCE_API_SECRET', ''))
    parser.add_argument('--output-file', help='Output CSV file', 
                       default='illumio-algosec-export.csv')
    parser.add_argument('--query-file', help='Query file skeleton', 
                       default='traffic-config.yaml')
    parser.add_argument('--traffic-config', help='Traffic configuration name', 
                       default='default')
    parser.add_argument('--algosec-label', '-a', 
                       help='Illumio labels for AlgoSec app label, comma separated, e.g. "app", "app,env"', 
                       default="app")
    parser.add_argument('--label-concat', '-c', 
                       help='String for concatening labels', 
                       default="-")
    parser.add_argument('--verbose', '-v', help='Verbose output', 
                       action='store_true')
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    exporter = IllumioExporter(args)
    success = exporter.export_data()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
