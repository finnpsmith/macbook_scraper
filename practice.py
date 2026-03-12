import requests
from bs4 import BeautifulSoup

URL = 'https://www.amazon.com/Apple-2024-MacBook-Laptop-10%E2%80%91core/dp/B0DLHBYRPS/ref=sr_1_6?crid=36NYRQ43EPY7L&dib=eyJ2IjoiMSJ9.g-RiYkT6xiQ5tgpw21X-wl8Vedpie57dsssxV1_NRfH2Nhi1S-Zg5gS81E4Nlb3ApFix5ss555U_HfI8cXc2gdcfS39UllDxAm-JGrqNqEq8hdZaIIKxalsaLAz97G5Jshb5fKSEW4rDf3fW4ERJWChuRUfkECf3RyhcMuQhVK7W3jNRxXaNesx49U-mxyeFfLGatUTm_5d_J0CsVMLdrH3AV1iZGg082z3xVlA1QcU.2LaWFdwL5v1aSgrXf-WTOQLdbHKeS0ujY0VvWS1UR-Y&dib_tag=se&keywords=macbook&qid=1759022911&sprefix=macbook%2Caps%2C163&sr=8-6&th=1'

headers = {"User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
        }

page = requests.get(URL, headers=headers)

soup = BeautifulSoup(page.content, 'html.parser')

title = soup.find(id = 'productTitle')
print(title.strip())
