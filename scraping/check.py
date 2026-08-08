"""
Langkah 1 (FIXED): cek status semua domain sebelum audit axe-core.
Perubahan dari versi lama:
- verify=False -> banyak situs .go.id punya SSL chain nggak lengkap,
  browser toleran tapi requests strict. Ini AMAN dilakukan di sini karena
  domain sudah diketahui/official (bukan scraping sumber sembarangan).
- Error nggak lagi ditelan diam-diam -> disimpan ke kolom debug_error
  biar ketauan kalau ada penyebab lain selain SSL.

Jalankan: pip install requests --break-system-packages
          python check_fixed.py

Update kolom crawl_status di website_master_34provinsi.csv:
- OK        -> domain aktif, lanjut ke tahap discover_pages
- REDIRECT  -> domain redirect ke domain lain (cek manual, mungkin domain berubah)
- DEAD      -> tidak bisa diakses (timeout/error/4xx/5xx) -> cari domain pengganti
"""
import csv
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IN_FILE = "master.csv"
OUT_FILE = "website_master2.csv"
TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}


def try_one(url):
    try:
        r = requests.get(
            url, timeout=TIMEOUT, headers=HEADERS,
            allow_redirects=True, verify=False,
        )
        if r.status_code < 400:
            return r, None
        return None, f"HTTP {r.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"{type(e).__name__}: {e}"


def build_fallbacks(url):
    """Varian umum yang sering kepakai kalau domain resmi berubah/beda pola."""
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.netloc
    variants = [url]
    variants.append(url.replace("https://", "http://"))
    if host.startswith("dinsos."):
        base_host = host[len("dinsos."):]
        variants.append(f"https://{base_host}")
        variants.append(f"https://{base_host}/dinsos")
    variants.append(url.replace("https://dinsos.", "https://www.dinsos."))
    return variants


def check(url):
    errors = []
    for candidate in build_fallbacks(url):
        r, err = try_one(candidate)
        if r is not None:
            final_domain = r.url
            status = "OK" if final_domain.rstrip("/") == candidate.rstrip("/") else "REDIRECT"
            note = "" if candidate == url else f"(pakai varian: {candidate})"
            return status, f"{final_domain} {note}".strip(), r.status_code, ""
        errors.append(f"{candidate} -> {err}")
    return "DEAD", "semua varian gagal - cari domain pengganti manual", None, " | ".join(errors)


def main():
    with open(IN_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        status, final_url, code, debug_error = check(row["domain"])
        row["crawl_status"] = status
        row["final_url"] = final_url
        row["http_code"] = code
        row["debug_error"] = debug_error
        print(f"{row['website_id']:5} {row['province_name']:28} {status:8} {final_url}")

    fieldnames = list(rows[0].keys())
    if "debug_error" not in fieldnames:
        fieldnames.append("debug_error")

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    ok = sum(1 for r in rows if r["crawl_status"] == "OK")
    redirect = sum(1 for r in rows if r["crawl_status"] == "REDIRECT")
    dead = [r for r in rows if r["crawl_status"] == "DEAD"]
    pct_usable = (ok + redirect) / len(rows) * 100

    print(f"\nRingkasan: OK={ok}  REDIRECT={redirect}  DEAD={len(dead)}  (total {len(rows)})")
    print(f"Persentase usable: {pct_usable:.1f}%  ({'GO, aman diatas 80%' if pct_usable >= 80 else 'DI BAWAH 80% -> perlu cari pengganti dulu sebelum lanjut, sesuai gate section 11.1'})")
    print(f"Hasil disimpan ke {OUT_FILE}")

    if dead:
        print(f"\n{len(dead)} domain perlu dicari penggantinya manual. Query saran pencarian:")
        with open("domains_need_replacement.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["website_id", "province_name", "domain_lama", "query_pencarian_disarankan", "debug_error"])
            w.writeheader()
            for r in dead:
                query = f'website resmi dinas sosial provinsi {r["province_name"]} go.id'
                w.writerow({
                    "website_id": r["website_id"], "province_name": r["province_name"],
                    "domain_lama": r["domain"], "query_pencarian_disarankan": query,
                    "debug_error": r["debug_error"],
                })
                print(f'  - {r["website_id"]} {r["province_name"]}: cari "{query}"')
        print("-> Daftar ini disimpan ke domains_need_replacement.csv, tinggal search satu-satu & update CSV master.")


if __name__ == "__main__":
    main()