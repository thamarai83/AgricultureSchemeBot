import json
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from services.storage import SCRAPED_DOCUMENTS_DIR, ensure_storage_directories


@dataclass(frozen=True)
class ApprovedSource:
    url: str
    department: str


APPROVED_SOURCES = {
    source.url: source
    for source in (
        ApprovedSource(
            url="https://aed.tn.gov.in/en/individual-based-subsidy-schemes/",
            department="Agricultural Engineering Department, Tamil Nadu",
        ),
        ApprovedSource(
            url="https://www.landreforms.tn.gov.in/UPT.html",
            department="Land Reforms Department, Tamil Nadu",
        ),
    )
}
MAX_PAGE_TEXT_CHARACTERS = 1_000_000
USER_AGENT = "UzhavanRAGBot/1.0 (government scheme information; respectful crawler)"


def validate_approved_source(url: str) -> ApprovedSource:
    source = APPROVED_SOURCES.get(url)
    if source is None:
        raise ValueError("Only the configured Tamil Nadu government pages can be scraped.")
    return source


def normalize_page_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _check_robots_policy(url: str) -> None:
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
    response = None
    for _ in range(4):
        robots_parts = urlparse(robots_url)
        if (
            robots_parts.scheme != "https"
            or robots_parts.hostname != parsed_url.hostname
            or robots_parts.port not in (None, 443)
        ):
            raise RuntimeError("The robots policy redirected outside the approved website.")
        try:
            response = requests.get(
                robots_url,
                headers={"User-Agent": USER_AGENT},
                timeout=10,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not check the site's robots policy: {exc}") from exc

        if response.status_code == 404:
            return
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                raise RuntimeError("The robots policy redirected without a target URL.")
            robots_url = urljoin(robots_url, location)
            continue
        if response.status_code >= 400:
            raise RuntimeError(
                f"The site's robots policy could not be read (HTTP {response.status_code})."
            )
        break
    else:
        raise RuntimeError("The site's robots policy redirected too many times.")

    parser = RobotFileParser()
    parser.set_url(robots_url)
    assert response is not None
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise PermissionError("The site's robots policy disallows scraping this page.")


def _extract_page_text(url: str, approved_host: str) -> tuple[str, str]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        if exc.name == "playwright":
            raise RuntimeError(
                "Playwright is not installed. Install the project requirements and "
                "the Playwright Chromium browser."
            ) from exc
        raise

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            raise RuntimeError(
                "Playwright could not launch Chromium. Run "
                "'python -m playwright install chromium' after installing dependencies."
            ) from exc

        try:
            page = browser.new_page()

            def restrict_requests(route) -> None:
                request_url = urlparse(route.request.url)
                try:
                    allowed = (
                        request_url.scheme == "https"
                        and request_url.hostname == approved_host
                        and request_url.port in (None, 443)
                    )
                except ValueError:
                    allowed = False
                if allowed:
                    route.continue_()
                else:
                    route.abort()

            page.route("**/*", restrict_requests)
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if response is None:
                raise RuntimeError("The website did not return a page response.")
            if response.status >= 400:
                raise RuntimeError(f"The website returned HTTP {response.status}.")

            current_url = urlparse(page.url)
            if current_url.scheme != "https" or current_url.hostname != approved_host:
                raise RuntimeError("The page redirected outside the approved website.")

            try:
                text = page.locator("body").evaluate(
                    """body => {
                        const content = body.cloneNode(true);
                        content.querySelectorAll(
                            "script, style, noscript, nav, header, footer, aside, form"
                        ).forEach(element => element.remove());
                        return content.innerText || content.textContent || "";
                    }"""
                )
                title = page.title()
            except PlaywrightTimeoutError as exc:
                raise RuntimeError("Timed out while extracting page text.") from exc
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Timed out while loading the government page.") from exc
        except PlaywrightError as exc:
            raise RuntimeError(f"Playwright could not extract the page: {exc}") from exc
        finally:
            browser.close()

    cleaned_text = normalize_page_text(text)
    if not cleaned_text:
        raise ValueError("No readable text was found on the government page.")
    if len(cleaned_text) > MAX_PAGE_TEXT_CHARACTERS:
        raise ValueError("The extracted page text exceeds the 1 MB safety limit.")

    return title.strip(), cleaned_text


def scrape_approved_website(url: str) -> dict[str, str | int]:
    source = validate_approved_source(url)
    _check_robots_policy(source.url)
    approved_host = urlparse(source.url).hostname
    if approved_host is None:
        raise ValueError("The approved website URL is invalid.")

    title, text = _extract_page_text(source.url, approved_host)
    document_name = title or approved_host
    payload = {
        "document_name": document_name,
        "source_url": source.url,
        "scheme_name": None,
        "department": source.department,
        "document_type": "website",
        "text": text,
    }

    ensure_storage_directories()
    stored_filename = f"{uuid.uuid4().hex}.json"
    destination = SCRAPED_DOCUMENTS_DIR / stored_filename
    try:
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise RuntimeError(f"Could not save scraped page text: {exc}") from exc

    return {
        "status": "queued",
        "document_name": document_name,
        "source_url": source.url,
        "characters_extracted": len(text),
    }
