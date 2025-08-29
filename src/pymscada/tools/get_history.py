"""Extract history data to CSV files.

This tool lists available history tags and extracts their values to CSV files.
It handles repeating time values as shown in the test_history.py script.
"""
import argparse
import csv
import logging
import sys
from pathlib import Path
from struct import unpack_from
from typing import Any, Optional

from pymscada.config import Config
from pymscada.history import TagHistory, ITEM_SIZE


def list_history_tags(config_path: str) -> list[str]:
    """List all available history tags from the config path."""
    config = Config(config_path)
    history_path = Path(config['path'])
    if not history_path.exists():
        logging.error(f'History path {history_path} does not exist')
        return []
    tag_names = set()
    for file_path in history_path.glob('*_*.dat'):
        parts = file_path.stem.split('_')
        if len(parts) >= 2 and parts[-1].isdigit():
            tag_name = '_'.join(parts[:-1])
            tag_names.add(tag_name)
    return list(tag_names)


def get_tag_type(tag_name: str, tags_config_path: str) -> Optional[type]:
    """Get the type of a tag from the tags configuration."""
    try:
        tags_config = Config(tags_config_path)
        if tag_name in tags_config:
            tag_info = tags_config[tag_name]
            if 'type' in tag_info:
                tag_type = tag_info['type']
                if tag_type == 'int':
                    return int
                elif tag_type == 'float':
                    return float
                else:
                    return str
            else:
                return float  # Default to float
    except Exception as e:
        logging.warning(f'Could not determine type for {tag_name}: {e}')


def extract_tag_history(
        tag_name: str,
        config_path: str,
        tags_config_path: str,
        output_file: Optional[str] = None
    ) -> list[tuple[int, Any]]:
    """Extract history data for a specific tag."""
    config = Config(config_path)
    history_path = Path(config['path'])
    if not history_path.exists():
        logging.error(f'History path {history_path} does not exist')
        return []
    tag_type = get_tag_type(tag_name, tags_config_path)
    if tag_type is None:
        logging.error(f'Could not determine type for tag {tag_name}')
        return []
    tag_history = TagHistory(tag_name, tag_type, str(history_path))
    data_bytes = tag_history.read_bytes()
    records = []
    for i in range(0, len(data_bytes), ITEM_SIZE):
        if i + ITEM_SIZE <= len(data_bytes):
            time_us, value = unpack_from(tag_history.packstr, data_bytes, offset=i)
            records.append((time_us // 1000000, value))
    if output_file:
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['timestamp_us', 'value'])
            prev_time = 0
            buffer = []
            last_buffer = []
            for time_us, value in records:
                if time_us < prev_time:
                    if buffer != last_buffer:
                        writer.writerow(buffer)
                    last_buffer = buffer.copy()
                    buffer = [time_us, value]
                else:
                    buffer.extend((time_us, value))
                prev_time = time_us
            if buffer:
                writer.writerow(buffer)
            logging.info(f'Extracted {len(records)} records to {output_file}')
    return records


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Extract history data to CSV files',
        epilog='Example: python get_history.py --config history.yaml --tags tags.yaml --list'
    )
    parser.add_argument('--config', required=True,
                        help='History configuration file')
    parser.add_argument('--tags', required=True,
                        help='Tags configuration file')
    parser.add_argument('--list', action='store_true',
                        help='List available history tags')
    parser.add_argument('--tag',
                        help='Extract specific tag to CSV')
    parser.add_argument('--output',
                        help='Output CSV file (default: <tag>.csv)')
    parser.add_argument('--verbose', action='store_true',
                        help='Verbose logging')
    args = parser.parse_args()
    level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format='%(levelname)s: %(message)s')
    if args.list:
        tags = list_history_tags(args.config)
        if tags:
            print('Available history tags:')
            for tag in tags:
                print(f'  {tag}')
        else:
            print('No history tags found')
            sys.exit(1)
    elif args.tag:
        if not args.output:
            args.output = f'{args.tag}.csv'
        records = extract_tag_history(args.tag, args.config, args.tags,
                                      args.output)
        if records:
            print(f'Extracted {len(records)} records for tag "{args.tag}"')
            print(f'Times: {records[0][0]} to {records[-1][0]}')
            print(f'Output file: {args.output}')
        else:
            print(f'No data found for tag "{args.tag}"')
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
