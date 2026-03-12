import csv
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# 2025 MacBook product page
URL = "https://www.amazon.com/Apple-2025-MacBook-Laptop-10%E2%80%91core/dp/B0FWD6SKL6/ref=sr_1_1_sspa?crid=3W4GGXJ07KGCN&dib=eyJ2IjoiMSJ9.M6b7AFIaRTz0gbJgYWx_c5NhUlF3Ssf4dQFN6GcHCoyN5zf84PQiKSON_nI8XWl8b-r-WjvBMJkEEqmhSov7Dtr9D7imbBtiPb4_4maZppjk745EHzx5FcZXuJJx5XpbhGjfESunTJ9QfGbvKEdmiDBZ0Y9vIN9PLkEUzWq6tnbv8PL_YpsIA0DN2u3aGkD7SNQu1-v3QHFo4ZGkZXvDtmTRSEOeBd3Empa67SEpuZo.sqFxlqPR1yaalKZXdK_Kh_kekTLQrquCJAW7ST51OSk&dib_tag=se&keywords=macbook%2Bpro&qid=1773342816&sprefix=macbook%2Bpro%2Caps%2C160&sr=8-1-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9hdGY&th=1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

LOG_FILE = "macbook_price_log.csv"
TARGET_PRICE = 1365.00  # change this to whatever alert price you want


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
    # Common pattern: span with class "a-offscreen" holds price like "$2,499.00"
    price_tag = soup.find("span", class_="a-offscreen")
    if not price_tag:
        # Fallback: any element with data-a-color="price"
        price_tag = soup.find(attrs={"data-a-color": "price"})

    if not price_tag:
        print("Could not find product price on the page.")
        return None

    price_text = price_tag.get_text(strip=True)
    return _parse_price(price_text)


def _parse_price(price_text: str) -> float | None:
    # Remove currency symbols and commas, keep digits and dot
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


def log_price(timestamp: datetime, title: str, price: float) -> None:
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "title", "price"])
        writer.writerow([timestamp.isoformat(), title, price])


def notify_if_price_drops(price: float) -> None:
    if price < TARGET_PRICE:
        print(f"ALERT: Price dropped below target! Current price: {price}")
    else:
        print(f"Current price {price} is above target {TARGET_PRICE}.")


def main() -> None:
    html = fetch_page(URL)
    if not html:
        return

    soup = get_soup(html)
    title = get_product_title(soup)
    price = get_product_price(soup)

    if title is None or price is None:
        return

    now = datetime.now()
    log_price(now, title, price)
    print(f"Logged {title!r} at {price} on {now.isoformat()}")
    notify_if_price_drops(price)


if __name__ == "__main__":
    main()