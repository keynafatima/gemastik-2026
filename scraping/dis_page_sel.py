"""
Versi Selenium dari discover_pages.py -- buat nangkep menu navigasi yang
di-render JavaScript (nggak kebaca kalau cuma requests + BeautifulSoup biasa).

Install dulu:
    pip install selenium beautifulsoup4 --break-system-packages

Selenium butuh Chrome + chromedriver yang versinya cocok. Cara paling gampang:
    pip install webdriver-manager --break-system-packages
(script ini otomatis pakai webdriver-manager buat download driver yang cocok)

Jalankan: python discover_pages_selenium.py

Input : website_master_34provinsi_checked.csv (kolom final_url)
Output: page_candidates_selenium.csv (kandidat baru, khusus buat nutupin
        yang kemarin kosong -- gabungin manual sama page_candidates.csv lama)
"""
import csv
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

IN_FILE = "website_master2.csv"
OUT_FILE = "master_page_candidates_selenium.csv"
PAGE_LOAD_TIMEOUT = 25
WAIT_AFTER_LOAD = 3  # detik, kasih waktu JS nyelesain render menu

KEYWORDS = {
    "Profil": ["profil", "tentang", "visi", "misi", "struktur", "organisasi",
               "sejarah", "tugas dan fungsi", "tupoksi"],
    "Layanan": ["layanan", "pelayanan", "persyaratan", "bantuan", "program",
                "prosedur", "syarat", "permohonan"],
    "Konten": ["berita", "artikel", "pengumuman", "informasi", "news",
               "publikasi", "kegiatan", "agenda"],
    "Interaksi/Kontak": ["kontak", "pengaduan", "hubungi", "contact",
                          "layanan pengaduan", "formulir", "pertanyaan"],
}


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--ignore-certificate-errors")  # sama kayak verify=False di requests
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1366,768")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


def find_candidates(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    results = {cat: [] for cat in KEYWORDS}
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        if urlparse(full_url).netloc != urlparse(base_url).netloc:
            continue
        if full_url in seen:
            continue

        text = a.get_text(strip=True).lower()
        href_lower = href.lower()

        for cat, keywords in KEYWORDS.items():
            for kw in keywords:
                if kw in text or kw in href_lower:
                    results[cat].append({
                        "url": full_url,
                        "link_text": a.get_text(strip=True)[:80],
                        "matched_keyword": kw,
                    })
                    seen.add(full_url)
                    break
    return results


def main():
    with open(IN_FILE, newline="", encoding="utf-8") as f:
        sites = list(csv.DictReader(f))

    driver = make_driver()
    rows_out = []

    try:
        for site in sites:
            website_id = site["website_id"]
            base_url = (site.get("final_url") or site["domain"]).split(" ")[0]
            print(f"{website_id} {site['province_name']} -> {base_url}")

            try:
                driver.get(base_url)
                time.sleep(WAIT_AFTER_LOAD)  # kasih waktu JS render menu/dropdown
                html = driver.page_source
            except (WebDriverException, TimeoutException) as e:
                print(f"  GAGAL load: {type(e).__name__}: {e}")
                rows_out.append({
                    "website_id": website_id, "page_type": "ALL",
                    "candidate_url": "", "link_text": f"GAGAL LOAD SELENIUM: {e}",
                    "matched_keyword": "",
                })
                continue

            candidates = find_candidates(base_url, html)

            for cat, items in candidates.items():
                if not items:
                    rows_out.append({
                        "website_id": website_id, "page_type": cat,
                        "candidate_url": "", "link_text": "TIDAK KETEMU (Selenium juga) - cek manual",
                        "matched_keyword": "",
                    })
                    continue
                for item in items[:3]:
                    rows_out.append({
                        "website_id": website_id, "page_type": cat,
                        "candidate_url": item["url"], "link_text": item["link_text"],
                        "matched_keyword": item["matched_keyword"],
                    })
    finally:
        driver.quit()

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["website_id", "page_type", "candidate_url",
                                           "link_text", "matched_keyword"])
        w.writeheader()
        w.writerows(rows_out)

    print(f"\nSelesai. Disimpan ke {OUT_FILE}")
    print("Gabungin hasil ini sama page_candidates.csv lama buat nutupin yang tadinya kosong.")


if __name__ == "__main__":
    main()