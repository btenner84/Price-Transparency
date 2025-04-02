#!/usr/bin/env python3
import argparse
import asyncio
import os
import json
import logging
import sys
from typing import List
from datetime import datetime

from src.pipeline.orchestrator import PriceFinderPipeline
from src.utils.logger import setup_logging
from src.models.hospital import Hospital

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Hospital Price Transparency File Finder')
    
    # Main operation mode
    parser.add_argument('--mode', choices=['search', 'update', 'stats'], default='search',
                       help='Operation mode: search for files, update master dataset, or show stats')
    
    # Input data options
    input_group = parser.add_argument_group('Input Data Options')
    input_group.add_argument('--input-file', type=str,
                           help='Path to hospital data JSON file')
    input_group.add_argument('--state', type=str, nargs='+',
                           help='State code(s) to process (e.g., CA NY TX)')
    input_group.add_argument('--limit', type=int, default=100,
                           help='Maximum number of hospitals to process')
    input_group.add_argument('--use-pending', action='store_true',
                           help='Use hospitals with pending status from database')
    
    # API keys
    keys_group = parser.add_argument_group('API Keys')
    keys_group.add_argument('--serpapi-key', type=str,
                           help='SerpAPI API key (can also set SERPAPI_KEY env var)')
    keys_group.add_argument('--openai-key', type=str,
                           help='OpenAI API key (can also set OPENAI_API_KEY env var)')
    
    # Pipeline configuration
    config_group = parser.add_argument_group('Pipeline Configuration')
    config_group.add_argument('--llm-provider', choices=['openai', 'anthropic', 'mistral'], default='openai',
                            help='LLM provider to use')
    config_group.add_argument('--concurrency', type=int, default=5,
                            help='Number of concurrent searches')
    config_group.add_argument('--db-path', type=str, default='data/price_finder.db',
                            help='Path to SQLite database file')
    config_group.add_argument('--download-dir', type=str, default='downloads',
                            help='Directory to store downloaded files')
    config_group.add_argument('--config-file', type=str,
                            help='Path to configuration JSON file')
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('--output-file', type=str,
                             help='Path to output JSON file (defaults to timestamped filename)')
    output_group.add_argument('--log-file', type=str, default='logs/price_finder.log',
                             help='Path to log file')
    output_group.add_argument('--verbose', '-v', action='store_true',
                             help='Enable verbose logging')
    
    return parser.parse_args()

def load_config(config_file: str = None) -> dict:
    """Load configuration from a JSON file."""
    config = {
        "max_search_results": 10,
        "link_confidence_threshold": 0.6,
        "content_validation_threshold": 0.8,
        "hospital_match_threshold": 0.8,
        "min_price_columns": 1,
        "min_rows": 10
    }
    
    if config_file and os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
            print(f"Loaded configuration from {config_file}")
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
    
    return config

async def main():
    """Main entry point for the price transparency finder CLI."""
    args = parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging(
        log_dir=os.path.dirname(args.log_file) or "logs",
        log_file=os.path.basename(args.log_file),
        console_level=log_level,
        file_level=logging.DEBUG
    )
    
    # Load configuration
    config = load_config(args.config_file)
    
    # Override config with command-line args
    config["db_path"] = args.db_path
    
    # Initialize the pipeline
    logger.info("Initializing price finder pipeline...")
    pipeline = PriceFinderPipeline(
        config=config,
        serpapi_key=args.serpapi_key,
        openai_key=args.openai_key,
        download_dir=args.download_dir,
        llm_provider=args.llm_provider
    )
    
    # Determine output file if not specified
    output_file = args.output_file
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"results_{timestamp}.json"
    
    # Execute the requested mode
    if args.mode == 'search':
        logger.info("Starting search mode")
        
        # Get hospitals to process
        hospitals = []
        
        if args.input_file:
            # Load hospitals from file
            hospitals = pipeline.load_hospitals_from_file(args.input_file)
            
            # Apply filters if specified
            if args.state:
                hospitals = [h for h in hospitals if h.state in args.state]
            
            # Apply limit
            hospitals = hospitals[:args.limit]
            
        elif args.use_pending:
            # Get hospitals with pending status from database
            hospitals = pipeline.get_hospitals_to_process(
                limit=args.limit, 
                states=args.state
            )
        else:
            logger.error("No input source specified. Use --input-file or --use-pending.")
            return
        
        if not hospitals:
            logger.error("No hospitals to process!")
            return
        
        logger.info(f"Processing {len(hospitals)} hospitals with concurrency {args.concurrency}")
        
        # Run the batch process
        result = await pipeline.batch_process(
            hospitals=hospitals,
            concurrency=args.concurrency,
            save_results=True
        )
        
        logger.info(f"Search completed. Summary: {result}")
    
    elif args.mode == 'update':
        logger.info("Starting update mode")
        
        # Update the master dataset
        success = pipeline.update_master_dataset(output_file)
        
        if success:
            logger.info(f"Master dataset updated and saved to {output_file}")
        else:
            logger.error("Failed to update master dataset")
    
    elif args.mode == 'stats':
        logger.info("Starting stats mode")
        
        # Get statistics from the database
        stats = pipeline.status_tracker.get_statistics()
        
        # Print statistics
        print("\n===== PRICE TRANSPARENCY FINDER STATISTICS =====")
        print(f"Total hospitals: {stats.get('total_hospitals', 0)}")
        print("\nStatus breakdown:")
        
        status_counts = stats.get('status_counts', {})
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        
        print(f"\nTotal price files found: {stats.get('total_price_files', 0)}")
        print(f"Validated price files: {stats.get('validated_price_files', 0)}")
        
        print("\nRecent activity:")
        for activity in stats.get('recent_activity', [])[:5]:
            timestamp = activity.get('timestamp', '')
            if timestamp:
                try:
                    timestamp = datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            print(f"  {timestamp} - {activity.get('name')} ({activity.get('state')}): {activity.get('status')} - {activity.get('message')}")
        
        print("\nTop states by hospital count:")
        for state in stats.get('state_counts', [])[:10]:
            found_pct = (state.get('found_count', 0) / state.get('count', 1)) * 100
            print(f"  {state.get('state')}: {state.get('count')} hospitals, {found_pct:.1f}% with price files")
        
        print("=================================================\n")
        
        # Save stats to file
        with open(output_file, 'w') as f:
            json.dump(stats, f, indent=2)
            
        logger.info(f"Statistics saved to {output_file}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unhandled error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2) 