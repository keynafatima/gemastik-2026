"""
Langkah 2: discover kandidat halaman per kategori, buat bahan page_sample.csv
Jalankan: pip install requests beautifulsoup4 --break-system-packages
          python discover_pages.py

Input : website_master_34provinsi_checked.csv (pakai kolom final_url)
Output: page_candidates.csv -> tiap baris = 1 kandidat link yang match keyword
        Kamu review manual, pilih yang paling representatif per (website, tipe halaman),
        baru pindahin ke page_sample.csv final.
"""
import csv
import re
import time
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IN_FILE = "website_master_34provinsi_checked.csv"
OUT_FILE = "page_candidates.csv"
TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

# Keyword per kategori -- disesuaikan sama istilah umum situs pemerintah Indonesia.
# Dicek di teks link DAN di url-nya.
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


def fetch(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS, verify=False)
        if r.status_code < 400:
            return r
    except requests.exceptions.RequestException as e:
        print(f"  gagal fetch {url}: {type(e).__name__}: {e}")
    return None


def find_candidates(base_url, soup):
    """Cari link yang teks/href-nya cocok sama keyword tiap kategori."""
    results = {cat: [] for cat in KEYWORDS}
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        # skip link ke domain lain (misal sosmed)
        if urlparse(full_url).netloc != urlparse(base_url).netloc:
            continue
        if full_url in seen_urls:
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
                    seen_urls.add(full_url)
                    break
    return results


def main():
    with open(IN_FILE, newline="", encoding="utf-8") as f:
        sites = list(csv.DictReader(f))

    rows_out = []

    for site in sites:
        website_id = site["website_id"]
        base_url = site.get("final_url") or site["domain"]
        base_url = base_url.split(" ")[0]  # buang catatan "(pakai varian: ...)" kalau ada
        print(f"{website_id} {site['province_name']} -> {base_url}")

        # Homepage selalu masuk otomatis
        rows_out.append({
            "website_id": website_id, "page_type": "Homepage",
            "candidate_url": base_url, "link_text": "(homepage)",
            "matched_keyword": "",
        })

        r = fetch(base_url)
        if r is None:
            rows_out.append({
                "website_id": website_id, "page_type": "ALL",
                "candidate_url": "", "link_text": "GAGAL FETCH - cek manual",
                "matched_keyword": "",
            })
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        candidates = find_candidates(base_url, soup)

        for cat, items in candidates.items():
            if not items:
                rows_out.append({
                    "website_id": website_id, "page_type": cat,
                    "candidate_url": "", "link_text": "TIDAK KETEMU - cek manual",
                    "matched_keyword": "",
                })
                continue
            for item in items[:3]:  # ambil maks 3 kandidat teratas per kategori
                rows_out.append({
                    "website_id": website_id, "page_type": cat,
                    "candidate_url": item["url"], "link_text": item["link_text"],
                    "matched_keyword": item["matched_keyword"],
                })

        time.sleep(1)  # sopan santun ke server, jangan spam request

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["website_id", "page_type", "candidate_url",
                                           "link_text", "matched_keyword"])
        w.writeheader()
        w.writerows(rows_out)

    print(f"\nSelesai. Kandidat disimpan ke {OUT_FILE}")
    print("Buka file itu, review tiap website, pilih 1 kandidat terbaik per page_type,")
    print("baru pindahin ke page_sample.csv final (lihat page_sample_template.csv).")


if __name__ == "__main__":
    main()