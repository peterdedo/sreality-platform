"""Browser-automation fallback path, used only when the JSON API becomes
unavailable/blocked for several consecutive requests (see SrealityClient's
`should_fall_back_to_browser`).

This replaces eternalvision/Sreality.cz-Parser's Puppeteer+Cheerio approach:
same idea (render with a real browser, parse the DOM), but rebuilt with
Playwright against the current React/MUI markup, since that repo's AngularJS
`ng-binding` selectors already target a defunct version of the site. Kept as a
last-resort path -- HTML/DOM scraping is the most fragile method found in the
audit and should not be the default.
"""

import logging

from playwright.async_api import async_playwright

from app.core.config import settings

logger = logging.getLogger(__name__)


async def fetch_listing_urls_via_browser(property_type_path: str, page_number: int) -> list[str]:
    """Fallback: render a search results page and collect listing detail URLs.

    property_type_path examples: "prodej/byty", "pronajem/domy".
    """
    url = f"{settings.sreality_base_url}/hledani/{property_type_path}?strana={page_number}"
    listing_urls: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            anchors = await page.locator("a[href*='/detail/']").all()
            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if href:
                    full_url = href if href.startswith("http") else f"{settings.sreality_base_url}{href}"
                    if full_url not in listing_urls:
                        listing_urls.append(full_url)
        except Exception:
            logger.exception("Browser fallback failed for %s page %d", property_type_path, page_number)
        finally:
            await browser.close()

    return listing_urls
