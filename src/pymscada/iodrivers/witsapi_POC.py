import aiohttp
import asyncio
import datetime

class WitsAPIClient:
    def __init__(self, url, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = url
        self.session = None
        
    async def __aenter__(self):
        """Create session and get token on entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session on exit"""
        if self.session:
            await self.session.close()
    
    async def get_token(self):
        """Get a new OAuth token"""
        auth_url = f"{self.base_url}/login/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            async with self.session.post(auth_url, data=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self.session.headers.update({
                        "Authorization": f"Bearer {result['access_token']}"
                    })
                    return result["access_token"]
                else:
                    error_text = await response.text()
                    return None
        except Exception as e:
            return None

    async def get(self, endpoint):
        """Make a GET request to the WITS API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error_text = await response.text()
                    return None
        except Exception as e:
            return None

    async def get_schedules(self):
        """Get list of schedules for which pricing data is available"""
        endpoint = "api/market-prices/v1/schedules"
        return await self.get(endpoint)

    async def get_nodes(self):
        """Get list of GXP/GIP nodes supported by this API"""
        endpoint = "api/market-prices/v1/nodes"
        return await self.get(endpoint)

    async def get_schedule_prices(self, schedule='RTD', market_type='E', nodes=None, 
                                back=None, forward=None, from_date=None, to_date=None, 
                                island=None, offset=0):
        """Get prices for a single schedule
        Args:
            schedule: Schedule type (e.g. 'RTD' for Real Time Dispatch)
            market_type: 'E' for energy prices, 'R' for reserve prices
            nodes: List of node IDs to filter by
            back: Number of trading periods to look back (1-48)
            forward: Number of trading periods to look ahead (1-48)
            from_date: Start datetime (RFC3339 format)
            to_date: End datetime (RFC3339 format)
            island: Filter by island ('NI' or 'SI')
            offset: Pagination offset
        """
        endpoint = f"api/market-prices/v1/schedules/{schedule}/prices"
        params = {
            'marketType': market_type,
            'offset': offset
        }
        if nodes:
            params['nodes'] = ','.join(nodes) if isinstance(nodes, list) else nodes
        if back:
            params['back'] = min(back, 48)
        if forward:
            params['forward'] = min(forward, 48)
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if island:
            params['island'] = island
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return await self.get(f"{endpoint}?{query}")

    async def get_multi_schedule_prices(self, schedules, market_type='E', nodes=None,
                                      back=None, forward=None, from_date=None, 
                                      to_date=None, island=None, offset=0):
        """Get prices across multiple schedules
        Args:
            schedules: List of schedule types
            market_type: 'E' for energy prices, 'R' for reserve prices
            nodes: List of node IDs to filter by
            back: Number of trading periods to look back (1-48)
            forward: Number of trading periods to look ahead (1-48)
            from_date: Start datetime (RFC3339 format)
            to_date: End datetime (RFC3339 format)
            island: Filter by island ('NI' or 'SI')
            offset: Pagination offset
        """
        endpoint = "api/market-prices/v1/prices"
        params = {
            'schedules': ','.join(schedules) if isinstance(schedules, list) else schedules,
            'marketType': market_type,
            'offset': offset
        }
        if nodes:
            params['nodes'] = ','.join(nodes) if isinstance(nodes, list) else nodes
        if back:
            params['back'] = min(back, 48)
        if forward:
            params['forward'] = min(forward, 48)
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if island:
            params['island'] = island
        query = '&'.join(f"{k}={v}" for k, v in params.items())
        return await self.get(f"{endpoint}?{query}")

    def parse_prices(self, response):
        """Parse API response into structured price dictionary
        Returns dict in format:
            {node: {trading_time_utc: {schedule: [price, last_run_utc]}}}
        """
        if not response:
            return {}
        prices = {}
        for schedule_data in response:
            schedule = schedule_data['schedule']
            if 'prices' not in schedule_data:
                continue
            for price in schedule_data['prices']:
                node = price['node']
                trading_time = int(datetime.datetime.fromisoformat(
                    price['tradingDateTime'].replace('Z', '+00:00')
                ).timestamp())
                last_run = int(datetime.datetime.fromisoformat(
                    price['lastRunTime'].replace('Z', '+00:00')
                ).timestamp())
                
                if node not in prices:
                    prices[node] = {}
                if trading_time not in prices[node]:
                    prices[node][trading_time] = {}
                prices[node][trading_time][schedule] = [price['price'], last_run]
        
        # Create RTD_forecast schedule
        for node in prices:
            for trading_time in prices[node]:
                if 'RTD' in prices[node][trading_time]:
                    prices[node][trading_time]['RTD_forecast'] = prices[node][trading_time]['RTD']
                else:
                    # Find most recent schedule by last run time
                    latest_schedule = None
                    latest_last_run = 0
                    for schedule in prices[node][trading_time]:
                        if prices[node][trading_time][schedule][1] > latest_last_run:
                            latest_last_run = prices[node][trading_time][schedule][1]
                            latest_schedule = schedule
                    if latest_schedule:
                        prices[node][trading_time]['RTD_forecast'] = \
                            prices[node][trading_time][latest_schedule]
        
        return prices
    
    def print_prices(self, prices):
        """Print prices in structured format with time information"""
        now = datetime.datetime.now(datetime.timezone.utc)
        now_ts = now.timestamp()
        for node in sorted(prices.keys()):
            print(f" - {node}:")
            for trading_time in sorted(prices[node].keys()):
                time_diff = trading_time - now_ts
                # For future times on 30 minute boundaries, show half-hour intervals
                if time_diff > 0 and trading_time % 1800 == 0:
                    half_hours = int(time_diff / 1800)
                    time_str = f"(+{half_hours})"
                else:
                    # For past times or non-30min intervals, show actual time
                    dt = datetime.datetime.fromtimestamp(trading_time, 
                                                       datetime.timezone.utc)
                    time_str = f"({dt.strftime('%Y-%m-%d %H:%M:%S')})"
                
                print(f"   - Trading Time UTC: {trading_time} {time_str}")
                for schedule in sorted(prices[node][trading_time].keys()):
                    if schedule in ['RTD', 'PRSS', 'PRSL', 'RTD_forecast']:
                        price, last_run = prices[node][trading_time][schedule]
                        last_run_dt = datetime.datetime.fromtimestamp(
                            last_run, datetime.timezone.utc)
                        print(f"        {schedule:12} Price: {price:8.2f}, "
                              f"Last Run: {last_run_dt.strftime('%H:%M:%S')}")


async def main(config):
    async with WitsAPIClient(url=config['url'],client_id=config['client_id'],
                             client_secret=config['client_secret']) as client:
        token = await client.get_token()
        if token:
            multi_prices = await client.get_multi_schedule_prices(
                schedules=config['schedules'],
                nodes=config['gxp_list'],
                back=config['back'],
                forward=config['forward']
            )
            if multi_prices:
                prices_dict = client.parse_prices(multi_prices)
                client.print_prices(prices_dict)
        await asyncio.sleep(1)


CONFIG = {
    'url': 'https://api.electricityinfo.co.nz',
    'gxp_list': ['MAT1101', 'CYD2201', 'BEN2201'],
    'schedules': ['RTD', 'PRSS', 'PRSL'],
    'back': 2,
    'forward': 72,
    'client_id': 'xx',
    'client_secret': 'xx'
}

if __name__ == "__main__":
    asyncio.run(main(CONFIG))
