# DSS Prioritas Aksesibilitas Website Pemerintah

Decision Support System (DSS) untuk penelitian **GEMASTIK 2026 — Karya Tulis
Ilmiah / Data Mining / Sistem Cerdas Terapan**, berjudul *Model Keputusan
Prioritisasi Aksesibilitas Website Pemerintah Terintegrasi Audit WCAG dan
Prevalensi Kesulitan Fungsional*.

## Overview

Aplikasi ini adalah lapisan **presentasi & DSS interaktif** yang membaca
langsung hasil analisis dari `fixed_notebook_enriched.ipynb`. Dashboard
**tidak menghitung ulang** skor, ranking, sensitivity, baseline, maupun
explainability — seluruh angka bersumber dari artefak CSV/JSON/joblib yang
diekspor notebook.

## Research Problem

Sumber daya pemerintah untuk remediasi aksesibilitas digital terbatas,
sehingga diperlukan mekanisme prioritisasi objektif yang mempertimbangkan
baik kondisi teknis situs maupun konteks kebutuhan penyandang kesulitan
fungsional di wilayah layanannya.

## Research Objective

Membangun model keputusan yang mengintegrasikan hasil audit aksesibilitas
otomatis (WCAG 2.2, axe-core) dengan data prevalensi kesulitan fungsional
(data sekunder BPS) untuk menghasilkan **priority ranking** perbaikan
website Dinas Sosial Provinsi, lengkap dengan validasi kestabilan, baseline
comparison, dan explainability.

## Research Scope

| Scope | Value |
|---|---|
| Objek Penelitian | Website resmi Dinas Sosial tingkat provinsi di Indonesia |
| Jumlah Website | 30 website |
| Halaman Sampel | 150 halaman (maks. 5 tipe halaman representatif/website: Homepage, Profil, Layanan, Konten, Interaksi/Kontak) |
| Alat Audit | axe-core (automated accessibility testing) |
| Standar & Level | WCAG 2.2, Level A dan AA yang didukung rule engine axe-core |
| Sumber Data Demografis | BPS (data sekunder, prevalensi per wilayah) |
| Metode Keputusan | Simple Additive Weighting (SAW), 3 skenario bobot |

Kategori kesulitan fungsional yang dipetakan: **Melihat**, **Mendengar**,
**Tangan/Motorik**.

## Research Contribution

1. Integrated accessibility audit dataset (audit WCAG + demografi dalam satu pipeline).
2. Pemetaan WCAG Success Criterion ke kategori kesulitan fungsional (*functional difficulty mapping*).
3. Technical Score per website per kategori kesulitan fungsional.
4. Demographic Score berbasis prevalensi kesulitan fungsional wilayah.
5. Priority ranking berbasis SAW yang mengintegrasikan skor teknis dan demografis.
6. Analisis sensitivitas tiga skenario bobot untuk menguji kestabilan ranking.
7. Perbandingan terhadap tiga baseline (raw findings, technical-only, demographic-only).
8. Explainability tingkat website — penelusuran ranking kembali ke Success Criterion dan halaman sumber temuan.

> Novelty penelitian **bukan** pada metode SAW itu sendiri (bukan metode
> baru), melainkan pada integrasi temuan WCAG, kategori kesulitan
> fungsional, prevalensi wilayah, ranking per kategori, dan stability
> analysis dalam satu workflow yang terdokumentasi dan reproducible.

## Methodology

```
Data Collection → Data Integration → Data Cleaning → Hash Deduplication
→ Failure Rate → Technical Score → Demographic Score → Baseline Comparison
→ Normalization → SAW → Ranking → Sensitivity Analysis → Explainability
→ Dashboard DSS
```

Seluruh tahapan di atas diimplementasikan di `fixed_notebook_enriched.ipynb`
dan **tidak diubah** oleh `app.py`.

## Data Pipeline

```
website_master → page_sample → audit_findings → sc_function_mapping
→ bps_demography → Integrated Dataset → Scoring & Ranking
```

## SAW Scenarios

| Skenario | Bobot Technical | Bobot Demographic |
|---|---|---|
| S1 — Technical Dominant | 0.7 | 0.3 |
| S2 — Balanced | 0.5 | 0.5 |
| S3 — Demographic Sensitive | 0.3 | 0.7 |

## Baseline Comparison

- **Baseline A** — ranking berdasarkan jumlah temuan relevan mentah.
- **Baseline B** — ranking berdasarkan Technical Score saja.
- **Baseline C** — ranking berdasarkan Demographic Score saja.

## Sensitivity Analysis

Status kestabilan ranking (definisi *top-3 frequency* dari notebook):

- **Robust** — masuk Top-3 pada 3 dari 3 skenario.
- **Cukup stabil** — masuk Top-3 pada 2 dari 3 skenario.
- **Sensitif** — masuk Top-3 pada 0–1 dari 3 skenario.

## Priority Explainability

Dashboard menyediakan *analytical traceability* — penelusuran Success
Criterion (dan halaman terdampak) yang paling berkontribusi terhadap skor
teknis suatu website — bukan *Explainable AI* dalam pengertian model
machine learning.

## Dashboard Features

15 halaman navigasi: Executive Overview, Research Scope & Methodology,
Audit Landscape, WCAG & Functional Mapping, Technical & Demographic Score,
Normalization & SAW Model, Priority Ranking, Scenario & Sensitivity,
Baseline Comparison, Explainability, Website Explorer, Research Results
Tables, Research Figures, Data & Provenance, dan Downloads.

## Generated Artifacts

File yang dikonsumsi dashboard bila tersedia pada `artifacts/`:

```
audit_findings_integrated.csv
baseline_comparison_stats.csv
dashboard_stabilitas_ranking.png
dashboard_top10_per_kategori.png
dataset_manifest_v1_0.json
explainability_drilldown_log.csv
fig_*.png (19 figure)
model_saw_v1_0.joblib
page_sample_updated.csv
priority_results.csv
sc_function_mapping.csv
top_issue_affected_pages.csv
```

Dua dataset wajib pada `data/`:

```
data/audit_findings.csv
data/priority_results.csv
```

## Project Structure

```
gemastik-2026/
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── audit_findings.csv
│   └── priority_results.csv
├── data_awal/
│   ├── audit_findings.csv
│   ├── bps_demography.csv
│   ├── page_sample.csv
│   └── website_master.csv
└── artifacts/
    ├── audit_findings_integrated.csv
    ├── baseline_comparison_stats.csv 
    ├── dataset_manifest_v1_0.json 
    ├── explainability_drilldown_log.csv 
    ├── model_saw_v1_0.joblib 
    ├── page_sample_updated.csv
    ├── priority_results.csv
    ├── sc_function_mapping.csv
    ├── top_issue_affected_pages.csv
    └── (fig_*.png, dashboard_*.png)
```

## Installation

```bash
cd gemastik-2026
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Application

```bash
cd gemastik-2026
streamlit run app.py
```

Aplikasi menggunakan path relatif (`Path(__file__).resolve().parent`)
sehingga tetap berjalan selama dijalankan dari dalam folder proyek.

## Data Provenance

Hierarki sumber kebenaran:

1. **Level 1 — Dokumen penelitian / logbook**: menentukan konteks, ruang
   lingkup, dan batas klaim.
2. **Level 2 — `fixed_notebook_enriched.ipynb`**: sumber kebenaran
   analitis (implementasi & hasil).
3. **Level 3 — Dataset final**: nilai aktual (CSV/JSON/joblib).
4. **Level 4 — `app.py`**: lapisan presentasi/DSS, mengonsumsi Level 2–3.

Dashboard secara otomatis memprioritaskan artefak notebook
(`artifacts/priority_results.csv`,
`artifacts/audit_findings_integrated.csv`) di atas dataset baseline
(`data/priority_results.csv`, `data/audit_findings.csv`) bila keduanya
tersedia, dan mendokumentasikan sumber aktif pada halaman **Data &
Provenance** serta sidebar.

## Reproducibility

```
fixed_notebook_enriched.ipynb
        ↓
Generated Artifacts (CSV/PNG/JSON/joblib)
        ↓
dataset_manifest_v1_0.json  +  model_saw_v1_0.joblib
        ↓
Streamlit DSS (app.py)
```

`dataset_manifest_v1_0.json` menyimpan checksum SHA-256 setiap artefak.
Halaman **Data & Provenance** memverifikasi checksum file lokal terhadap
manifest tersebut untuk memastikan artefak yang dimuat dashboard identik
dengan output notebook.

## Limitations

- Audit otomatis axe-core **bukan** audit kepatuhan WCAG penuh — hanya
  mencakup barrier yang dapat dideteksi otomatis.
- Kategori **Mendengar** bernilai `technical_score = 0` pada seluruh
  website karena axe-core tidak menguji elemen audio/video — keterbatasan
  cakupan deteksi otomatis, bukan bukti tiadanya hambatan.
- Data demografi BPS adalah **data sekunder** prevalensi wilayah, bukan
  jumlah pengguna aktual masing-masing website.
- Tidak ada responden atau panel ahli eksternal yang dilibatkan.
- Ranking bersifat **decision-support**, bukan keputusan final pemerintah.
- Sensitivity analysis dibatasi pada tiga skenario bobot yang ditentukan
  penelitian (S1/S2/S3).
- Explainability yang disediakan bersifat *analytical traceability*, bukan
  *Explainable AI*.

## Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| "Required dataset unavailable" | `data/audit_findings.csv` atau `data/priority_results.csv` belum ada | Salin kedua file ke folder `data/` |
| Sebagian visualisasi/download nonaktif | Artefak opsional pada `artifacts/` belum ada | Jalankan notebook hingga selesai, salin seluruh artefak ke `artifacts/` |
| Nama institusi/provinsi tidak muncul | `artifacts/audit_findings_integrated.csv` tidak tersedia | Salin file tersebut ke `artifacts/` |
| Checksum "tidak cocok" pada halaman Data & Provenance | File lokal berbeda dari saat manifest dibuat | Regenerasi artefak dari notebook agar konsisten dengan manifest |

## Academic Use

Aplikasi ini disiapkan sebagai prototipe DSS pendukung naskah Karya Tulis
Ilmiah GEMASTIK 2026. Seluruh angka, tabel, dan figur pada dashboard dapat
dikutip langsung pada Bab Hasil dan Pembahasan karena identik dengan
output `fixed_notebook_enriched.ipynb`. Istilah yang digunakan pada
dashboard mengikuti batas klaim penelitian (lihat halaman **Research
Scope & Methodology**) — hindari mengutip dashboard dengan istilah yang
melampaui klaim tersebut (mis. "WCAG compliance checker", "Explainable
AI").
