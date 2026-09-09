import asyncio
import json
import time
from playwright.async_api import async_playwright
from datetime import datetime


class ToffeeEdgeCacheScraper:
    def __init__(self, url):
        self.url = url
        self.cookies = []
        self.network_data = []
        self.edge_cache_cookies = {}
        
    async def intercept_response(self, response):
        """নেটওয়ার্ক রেসপন্স ইন্টারসেপ্ট করুন"""
        try:
            headers = await response.all_headers()
            cookies = await response.header_value('set-cookie')
            
            # Edge Cache সম্পর্কিত হেডার চেক করুন
            edge_headers = {
                'cf-ray': headers.get('cf-ray'),  # Cloudflare Ray ID
                'cf-cache-status': headers.get('cf-cache-status'),
                'age': headers.get('age'),
                'cache-control': headers.get('cache-control'),
                'cdn-cache': headers.get('cdn-cache'),
                'x-cache': headers.get('x-cache'),
                'x-edge-cache': headers.get('x-edge-cache'),
                'x-edge-cache-key': headers.get('x-edge-cache-key'),
                'x-edge-cache-tag': headers.get('x-edge-cache-tag'),
                'x-edge-cache-ttl': headers.get('x-edge-cache-ttl'),
                'x-served-by': headers.get('x-served-by'),
                'x-cache-hits': headers.get('x-cache-hits'),
            }
            
            # কুকি সংগ্রহ করুন
            set_cookie = headers.get('set-cookie', '')
            
            request_info = {
                'url': response.url,
                'status': response.status,
                'timestamp': datetime.now().isoformat(),
                'edge_headers': {k: v for k, v in edge_headers.items() if v},
                'set_cookie': set_cookie if set_cookie else None
            }
            
            self.network_data.append(request_info)
            
            # Edge Cache কুকি আলাদা করুন
            if 'edge' in set_cookie.lower() or any(edge_headers.values()):
                self.edge_cache_cookies[response.url] = {
                    'headers': edge_headers,
                    'cookies': set_cookie
                }
                
        except Exception as e:
            print(f"Error intercepting response: {e}")
    
    async def scrape(self):
        """মূল স্ক্রেপিং ফাংশন"""
        async with async_playwright() as p:
            # ব্রাউজার লঞ্চ করুন
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            )
            
            page = await context.new_page()
            
            # রেসপন্স ইন্টারসেপ্ট সেটআপ করুন
            page.on('response', lambda response: asyncio.create_task(self.intercept_response(response)))
            
            print(f"লোড হচ্ছে: {self.url}")
            
            # পেজ লোড করুন
            await page.goto(self.url, wait_until='networkidle', timeout=60000)
            
            # অতিরিক্ত সময় দিন কন্টেন্ট লোড হতে
            await page.wait_for_timeout(5000)
            
            # সব কুকি সংগ্রহ করুন
            self.cookies = await context.cookies()
            
            # স্টোরেজ থেকে ডেটা নিন
            local_storage = await page.evaluate('() => JSON.stringify(localStorage)')
            session_storage = await page.evaluate('() => JSON.stringify(sessionStorage)')
            
            # ব্রাউজার বন্ধ করুন
            await browser.close()
            
            return {
                'url': self.url,
                'scraped_at': datetime.now().isoformat(),
                'cookies': self.cookies,
                'edge_cache_data': self.edge_cache_cookies,
                'network_requests': self.network_data,
                'local_storage': json.loads(local_storage),
                'session_storage': json.loads(session_storage)
            }
    
    def save_results(self, data, filename='edge_cache_data.json'):
        """ফলাফল JSON ফাইলে সেভ করুন"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"ডেটা সেভ হয়েছে: {filename}")
        
        # Edge Cache কুকি আলাদা ফাইলে
        if data['edge_cache_data']:
            edge_file = 'edge_cache_cookies.json'
            with open(edge_file, 'w', encoding='utf-8') as f:
                json.dump(data['edge_cache_data'], f, indent=2, ensure_ascii=False)
            print(f"Edge Cache কুকি সেভ হয়েছে: {edge_file}")


async def main():
    url = "https://toffeelive.com/en/watch/Xi_Ga5oBNnOkwJLWkhKP"
    
    scraper = ToffeeEdgeCacheScraper(url)
    
    try:
        data = await scraper.scrape()
        scraper.save_results(data)
        
        # সারাংশ দেখান
        print("\n" + "="*60)
        print("স্ক্রেপিং সারাংশ")
        print("="*60)
        print(f"মোট কুকি: {len(data['cookies'])}")
        print(f"Edge Cache এন্ট্রি: {len(data['edge_cache_data'])}")
        print(f"নেটওয়ার্ক রিকোয়েস্ট: {len(data['network_requests'])}")
        
        # Edge Cache হেডার দেখান
        if data['edge_cache_data']:
            print("\nEdge Cache ডেটা:")
            for url, info in list(data['edge_cache_data'].items())[:3]:
                print(f"\nURL: {url[:80]}...")
                if info['headers']:
                    for key, value in info['headers'].items():
                        if value:
                            print(f"  {key}: {value}")
                            
    except Exception as e:
        print(f"ত্রুটি: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
