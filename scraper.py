import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_CONFIG_PATH = "config.json"


def load_config(path: str) -> list[dict]:
    """
    Load product list from JSON config.
    Supports:
      - {"products": [{"name", "url", "target_price", "log_file"}, ...]}
      - Legacy: {"url", "target_price", "log_file"} (single product)
    Returns a list of product dicts with keys: name, url, target_price, log_file.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "products" in data:
        products = list(data["products"])
    else:
        # Single-product legacy format
        products = [data]
    # Normalize: ensure name and float target_price
    result = []
    for i, p in enumerate(products):
        name = p.get("name") or p.get("title") or f"Product_{i + 1}"
        url = p.get(("url") or "").strip()
        try:
            target_price = float(p.get("target_price", 0))
        except (TypeError, ValueError):
            target_price = 0.0
        log_file = (p.get("log_file") or "price_log.csv").strip()
        if not url:
            print(f"Skipping product {name!r}: missing url")
            continue
        result.append({
            "name": name,
            "url": url,
            "target_price": target_price,
            "log_file": log_file,
        })
    return result


def fetch_page(url: str) -> str | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return None


def get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def get_product_title(soup: BeautifulSoup) -> str | None:
    title_tag = soup.find(id="productTitle")
    if not title_tag:
        print("Could not find product title on the page.")
        return None
    return title_tag.get_text(strip=True)


def get_product_price(soup: BeautifulSoup) -> float | None:
    """
    Try a few common Amazon price locations and return a numeric price.
    """
    price_tag = soup.find("span", class_="a-offscreen")
    if not price_tag:
        price_tag = soup.find(attrs={"data-a-color": "price"})

    if not price_tag:
        print("Could not find product price on the page.")
        return None

    price_text = price_tag.get_text(strip=True)
    return _parse_price(price_text)


def _parse_price(price_text: str) -> float | None:
    cleaned = []
    for ch in price_text:
        if ch.isdigit() or ch == ".":
            cleaned.append(ch)
    if not cleaned:
        print(f"Could not parse price from text: {price_text!r}")
        return None
    try:
        return float("".join(cleaned))
    except ValueError:
        print(f"Failed converting price to float: {price_text!r}")
        return None


def log_price(
    timestamp: datetime, title: str, price: float, log_file: str
) -> None:
    file_exists = os.path.exists(log_file)
    with open(log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "title", "price"])
        writer.writerow([timestamp.isoformat(), title, price])


def notify_if_price_drops(
    price: float, target_price: float, name: str = ""
) -> None:
    label = f" [{name}]" if name else ""
    if price < target_price:
        print(f"ALERT{label}: Price dropped below target! Current: {price} (target: {target_price})")
    else:
        print(f"Current price {price} is above target {target_price}.{label}")


def scrape_one(product: dict) -> None:
    """Fetch, parse, log, and notify for a single product."""
    name = product["name"]
    url = product["url"]
    target_price = product["target_price"]
    log_file = product["log_file"]

    html = fetch_page(url)
    if not html:
        return

    soup = get_soup(html)
    title = get_product_title(soup)
    price = get_product_price(soup)

    if title is None or price is None:
        return

    now = datetime.now()
    log_price(now, title, price, log_file)
    print(f"Logged {name!r} at {price} on {now.isoformat()} -> {log_file}")
    notify_if_price_drops(price, target_price, name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Amazon price scraper (multi-product, JSON config)"
    )
    parser.add_argument(
        "--config", "-c",
        default=os.environ.get("SCRAPER_CONFIG", DEFAULT_CONFIG_PATH),
        help="Path to config.json (default: config.json or SCRAPER_CONFIG)",
    )
    parser.add_argument(
        "--url", "-u",
        help="Override: scrape this URL only (ignores config products)",
    )
    parser.add_argument(
        "--target", "-t",
        type=float,
        help="Override: target price for --url",
    )
    parser.add_argument(
        "--log-file", "-l",
        help="Override: log file for --url",
    )
    args = parser.parse_args()

    if args.url:
        # Single-product CLI override
        target = args.target
        if target is None:
            try:
                target = float(os.environ.get("SCRAPER_TARGET_PRICE", "0"))
            except ValueError:
                target = 0.0
        log_file = args.log_file or os.environ.get("SCRAPER_LOG_FILE", "price_log.csv")
        products = [
            {
                "name": "CLI product",
                "url": args.url,
                "target_price": target,
                "log_file": log_file,
            }
        ]
    else:
        config_path = args.config
        if not Path(config_path).exists():
            print(f"Config not found: {config_path}")
            print("Copy config.json.example to config.json and edit, or use --url")
            return
        products = load_config(config_path)
        if not products:
            print("No products in config.")
            return
        # Env overrides for first product only (when not using --url)
        if os.environ.get("SCRAPER_TARGET_PRICE"):
            try:
                products[0]["target_price"] = float(os.environ["SCRAPER_TARGET_PRICE"])
            except ValueError:
                pass
        if os.environ.get("SCRAPER_LOG_FILE"):
            products[0]["log_file"] = os.environ["SCRAPER_LOG_FILE"]

    for product in products:
        scrape_one(product)


if __name__ == "__main__":
    main()