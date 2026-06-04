import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def scrape_core_content(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            
            # Wait for network idle to ensure JS-rendered content is fully loaded
            await page.goto(url, wait_until="networkidle", timeout=60000)
            html_content = await page.content()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            unwanted_tags = ["nav", "footer", "header", "aside", "script", "style", "noscript", "iframe"]
            for element in soup(unwanted_tags):
                element.decompose()
                
            main_content = soup.find('main') or soup.find('article')
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
            else:
                body = soup.find('body')
                text = body.get_text(separator='\n', strip=True) if body else soup.get_text(separator='\n', strip=True)
                    
            return text
            
        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout scraping {url}: {str(e)}")
            raise TimeoutError(f"Scraper timed out for URL: {url}")
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            raise e
        finally:
            # This ensures the browser process terminates safely regardless of where a failure occurs
            await browser.close()
