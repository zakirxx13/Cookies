import asyncio
import json
import re
import base64
from playwright.async_api import async_playwright
from datetime import datetime


class ToffeeSignedURLScraper:
    def __init__(self, watch_url):
        self.watch_url = watch_url
        self.signed_url_cookies = []
        self.all_cookies = []
        self.cdn_requests = []
        
    def parse_signed_url_cookie(self, cookie_string):
        """Signed URL Cookie পার্স করুন"""
        if not cookie_string:
            return None
            
        # URLPrefix=xxx:Expires=xxx:KeyName=xxx:Signature=xxx ফরম্যাট চেক করুন
        pattern = r'URLPrefix=([^:]+):Expires=(\d+):KeyName=([^:]+):Signature=([A-Za-z0-9_-]+)'
        match = re.search(pattern, cookie_string)
        
        if match:
            url_prefix_b64 = match.group(1)
            expires = match.group(2)
            key_name = match.group(3)
            signature = match.group(4)
            
            # Base64 ডিকোড করুন
            try:
                url_prefix = base64.b64decode(url_prefix_b64 + '=' * (4 - len(url_prefix_b64) % 4)).decode('utf-8')
            except:
                url_prefix = url_prefix_b64
                
            return {
                'raw_cookie': cookie_string,
                'parsed': {
                    'URLPrefix': url_prefix,
                    'URLPrefix_Base64': url_prefix_b64,
                    'Expires': int(expires),
                    'Expires_ISO': datetime.fromtimestamp(int(expires)).isoformat(),
                    'KeyName': key_name,
                    'Signature': signature
                }
            }
        return None
    
    async def intercept_response(self, response):
        """সব রেসপন্স ইন্টারসেপ্ট করুন"""
        try:
            url = response.url
            headers = await response.all_headers()
            
            # CDN ডোমেইন চেক করুন (toffeelive.com CDN)
            if 'cdn' in url or 'bldcm' in url or 'media' in url or 'stream' in url:
                set_cookie = headers.get('set-cookie', '')
                
                cdn_data = {
                    'url': url,
                    'status': response.status,
                    'set_cookie': set_cookie,
                    'timestamp': datetime.now().isoformat(),
                    'all_headers': dict(headers)
                }
                self.cdn_requests.append(cdn_data)
                
                # Signed URL Cookie খুঁজুন
                if 'URLPrefix' in set_cookie or 'Signature' in set_cookie:
                    parsed = self.parse_signed_url_cookie(set_cookie)
                    if parsed:
                        self.signed_url_cookies.append({
                            'source_url': url,
                            **parsed
                        })
                        print(f"✓ Signed URL Cookie পাওয়া গেছে: {url[:60]}...")
                
                # Edge Cache KeyName চেক করুন
                if 'KeyName=prod_linear' in set_cookie or 'prod_linear' in set_cookie:
                    print(f"✓ prod_linear Key পাওয়া গেছে!")
                    
        except Exception as e:
            print(f"Error: {e}")
    
    async def intercept_request(self, request):
        """রিকোয়েস্ট ইন্টারসেপ্ট করুন (কুকি দেখতে)"""
        try:
            headers = request.headers
            cookie = headers.get('cookie', '')
            
            # রিকোয়েস্ট হেডারে Signed URL Cookie আছে কিনা চেক করুন
            if 'URLPrefix' in cookie:
                parsed = self.parse_signed_url_cookie(cookie)
                if parsed:
                    self.signed_url_cookies.append({
                        'source_url': request.url,
                        'from_request': True,
                        **parsed
                    })
                    print(f"✓ Signed URL Cookie রিকোয়েস্টে পাওয়া গেছে!")
                    
        except Exception as e:
            pass
    
    async def scrape(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-size=1920,1080'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Origin': 'https://toffeelive.com',
                    'Referer': 'https://toffeelive.com/'
                }
            )
            
            page = await context.new_page()
            
            # ইভেন্ট লিসেনার সেটআপ
            page.on('response', lambda response: asyncio.create_task(self.intercept_response(response)))
            page.on('request', lambda request: asyncio.create_task(self.intercept_request(request)))
            
            print(f"লোড হচ্ছে: {self.watch_url}")
            await page.goto(self.watch_url, wait_until='networkidle', timeout=60000)
            
            # ভিডিও প্লেয়ার লোড হতে অপেক্ষা করুন
            await page.wait_for_timeout(8000)
            
            # প্লেই বাটনে ক্লিক করুন (যদি থাকে) - ভিডিও স্ট্রিম ট্রিগার করতে
            try:
                await page.click('button[aria-label*="Play"], .play-button, [data-testid="play-button"]', timeout=5000)
                print("প্লে বাটনে ক্লিক করা হয়েছে")
                await page.wait_for_timeout(5000)
            except:
                pass
            
            # আরো অপেক্ষা করুন CDN রিকোয়েস্টের জন্য
            await page.wait_for_timeout(10000)
            
            # সব কুকি সংগ্রহ করুন
            self.all_cookies = await context.cookies()
            
            # JavaScript দিয়ে document.cookie চেক করুন
            js_cookies = await page.evaluate('() => document.cookie')
            
            # Local/Session storage
            local_storage = await page.evaluate('() => JSON.stringify(localStorage)')
            session_storage = await page.evaluate('() => JSON.stringify(sessionStorage)')
            
            await browser.close()
            
            # document.cookie থেকে Signed URL খুঁজুন
            if 'URLPrefix' in js_cookies:
                for cookie_part in js_cookies.split(';'):
                    parsed = self.parse_signed_url_cookie(cookie_part.strip())
                    if parsed:
                        self.signed_url_cookies.append({
                            'source_url': 'document.cookie',
                            **parsed
                        })
            
            return {
                'watch_url': self.watch_url,
                'scraped_at': datetime.now().isoformat(),
                'signed_url_cookies': self.signed_url_cookies,
                'all_cookies': self.all_cookies,
                'document_cookie': js_cookies,
                'cdn_requests': self.cdn_requests,
                'local_storage': json.loads(local_storage),
                'session_storage': json.loads(session_storage)
            }
    
    def save_results(self, data):
        """ফলাফল সেভ করুন"""
        
        # Signed URL Cookies আলাদা ফাইলে
        if data['signed_url_cookies']:
            with open('signed_url_cookies.json', 'w', encoding='utf-8') as f:
                json.dump(data['signed_url_cookies'], f, indent=2, ensure_ascii=False)
            print(f"\n✓ Signed URL Cookies সেভ হয়েছে: signed_url_cookies.json")
            
            # শুধু Raw Cookie লিস্ট
            raw_list = [c['raw_cookie'] for c in data['signed_url_cookies']]
            with open('signed_url_cookies_raw.txt', 'w') as f:
                f.write('\n\n'.join(raw_list))
            print("✓ Raw cookies সেভ হয়েছে: signed_url_cookies_raw.txt")
        
        # পূর্ণ রিপোর্ট
        with open('full_scrape_report.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("✓ Full report সেভ হয়েছে: full_scrape_report.json")
        
        # সারাংশ দেখান
        print("\n" + "="*70)
        print("স্ক্রেপিং সারাংশ")
        print("="*70)
        print(f"মোট Signed URL Cookies: {len(data['signed_url_cookies'])}")
        print(f"মোট CDN রিকোয়েস্ট: {len(data['cdn_requests'])}")
        print(f"মোট ব্রাউজার কুকি: {len(data['all_cookies'])}")
        
        if data['signed_url_cookies']:
            print("\n" + "="*70)
            print("পাওয়া Signed URL Cookies:")
            print("="*70)
            for i, cookie in enumerate(data['signed_url_cookies'], 1):
                parsed = cookie.get('parsed', {})
                print(f"\n--- Cookie #{i} ---")
                print(f"Source: {cookie.get('source_url', 'Unknown')}")
                print(f"URL Prefix: {parsed.get('URLPrefix', 'N/A')}")
                print(f"Expires: {parsed.get('Expires_ISO', 'N/A')}")
                print(f"KeyName: {parsed.get('KeyName', 'N/A')}")
                print(f"Signature: {parsed.get('Signature', 'N/A')[:50]}...")


async def main():
    url = "https://toffeelive.com/en/watch/Xi_Ga5oBNnOkwJLWkhKP"
    
    scraper = ToffeeSignedURLScraper(url)
    
    try:
        data = await scraper.scrape()
        scraper.save_results(data)
    except Exception as e:
        print(f"ত্রুটি: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
