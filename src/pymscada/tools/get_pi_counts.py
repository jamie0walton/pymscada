"""Get PI counts for a given date."""
import argparse
import asyncio
import re
import time
from pathlib import Path
from pymscada.iodrivers.piapi import PIWebAPI


async def main():
    """Test getting tag web IDs from PI WebAPI."""
    parser = argparse.ArgumentParser(description='Get PI counts for given dates')
    parser.add_argument('dates', nargs='+', metavar='YYYY-MM-DD',
                        help='One or more dates in YYYY-MM-DD format')
    args = parser.parse_args()
    
    # Validate date format
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    for date in args.dates:
        if not date_pattern.match(date):
            parser.error(f"Invalid date format: {date}. Expected YYYY-MM-DD")
    
    api_config = {
        'url': 'https://192.168.15.1/',
        'webid': 'F1Em9DA80Xftdkec1gdWFtX7NAm1eiSAyV8BG1mAAMKQIjRQUEdQSVxQSU9ORUVSXFdFQkFQSVxNT0JJTEVTQ0FEQQ',
        'averaging': 300,
        'points_id': 'F1DSiiISXjUSX0eXU1yhlT-iHgUEdQSQ'
    }
    client = PIWebAPI(bus_ip=None, api=api_config)
    await client.get_pi_points_ids()
    await client.get_pi_points_attributes()
    counts = {}
    for day in args.dates:
        sec = int(time.mktime(time.strptime(day, '%Y-%m-%d')))
        await client.get_pi_points_count(sec)
        for point in client.points:
            if point not in counts:
                counts[point] = []
            counts[point].append(client.points[point].count)
    print('PI Tag, compdev, compmax, excdev, excmax, engunits, description, instrumenttag,'
          f'{",".join(args.dates)}')
    for point in counts:
        compdev = client.points[point].compdev
        compmax = client.points[point].compmax
        excdev = client.points[point].excdev
        excmax = client.points[point].excmax
        engunits = client.points[point].engunits
        description = client.points[point].descriptor
        instrumenttag = client.points[point].instrumenttag
        print(f'{point},{compdev},{compmax},{excdev},{excmax},"{engunits}","{description}",'
              f'"{instrumenttag}",{",".join(str(c) for c in counts[point])}')


if __name__ == '__main__':
    asyncio.run(main())
