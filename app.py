"""
DSS Prioritas Aksesibilitas Website Pemerintah
================================================
Decision Support System (DSS) untuk penelitian GEMASTIK 2026 mengenai
prioritisasi perbaikan aksesibilitas website Dinas Sosial Provinsi,
berbasis integrasi audit WCAG (axe-core) dan prevalensi kesulitan
fungsional (data sekunder BPS).

PENTING — batas peran file ini:
- File ini adalah lapisan PRESENTASI/DSS. Seluruh skor, ranking, hasil
  sensitivity, baseline, dan explainability TIDAK dihitung ulang di sini.
  Semua angka dibaca langsung dari artefak yang dihasilkan
  `fixed_notebook_enriched.ipynb` (lihat README.md untuk detail rantai
  provenance & source of truth).
- Jika artefak notebook tidak tersedia, dashboard otomatis mundur
  (fallback) ke dataset baseline pada folder data/, dan menonaktifkan
  fitur yang bergantung pada artefak tersebut secara eksplisit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    import joblib
    HAS_JOBLIB = True
except ImportError:  # pragma: no cover
    HAS_JOBLIB = False


# =====================================================================
# 0. KONFIGURASI & KONSTANTA PENELITIAN
#    (Nilai di bawah ini merepresentasikan definisi metodologi yang
#     TIDAK diubah oleh dashboard — lihat model_saw_v1_0.joblib untuk
#     salinan resmi yang diekspor notebook.)
# =====================================================================

APP_VERSION = "v2.0"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTIFACT_DIR = BASE_DIR / "artifacts"

CATEGORIES = ["melihat", "mendengar", "tangan"]
CATEGORY_LABELS = {
    "melihat": "Kesulitan Melihat",
    "mendengar": "Kesulitan Mendengar",
    "tangan": "Kesulitan Tangan / Motorik",
}
CATEGORY_COLORS = {"melihat": "#2b6cb0", "mendengar": "#805ad5", "tangan": "#2f855a"}

SCENARIOS = {"S1": (0.7, 0.3), "S2": (0.5, 0.5), "S3": (0.3, 0.7)}
SCENARIO_LABELS = {
    "S1": "S1 — Technical Dominant (Teknis 70% / Demografis 30%)",
    "S2": "S2 — Balanced (Teknis 50% / Demografis 50%)",
    "S3": "S3 — Demographic Sensitive (Teknis 30% / Demografis 70%)",
}

STABILITY_ORDER = ["Robust", "Cukup stabil", "Sensitif"]
STABILITY_COLORS = {"Robust": "#2f855a", "Cukup stabil": "#d69e2e", "Sensitif": "#c53030"}
STABILITY_DEFINITION = {
    "Robust": "Masuk Top-3 pada 3 dari 3 skenario bobot.",
    "Cukup stabil": "Masuk Top-3 pada 2 dari 3 skenario bobot.",
    "Sensitif": "Masuk Top-3 pada 0–1 dari 3 skenario bobot.",
}

IMPACT_ORDER = ["minor", "moderate", "serious", "critical"]
IMPACT_COLORS = {"minor": "#68a4e2", "moderate": "#d69e2e", "serious": "#dd6b20", "critical": "#c53030"}
IMPACT_WEIGHT_REFERENCE = {"minor": 0.25, "moderate": 0.5, "serious": 0.75, "critical": 1.0}

BASELINE_DEFINITIONS = {
    "Baseline A": "Ranking berdasarkan jumlah temuan relevan mentah (raw relevant findings) — tanpa pembobotan severity maupun mapping fungsional.",
    "Baseline B": "Ranking berdasarkan Technical Score saja — audit WCAG tanpa memperhitungkan prevalensi kesulitan fungsional wilayah.",
    "Baseline C": "Ranking berdasarkan Demographic Score saja — prevalensi kesulitan fungsional wilayah tanpa memperhitungkan kondisi teknis situs.",
}

RESEARCH_SCOPE = {
    "Objek Penelitian": "Website resmi Dinas Sosial tingkat provinsi di Indonesia",
    "Jumlah Website": "30 website",
    "Halaman Sampel": "150 halaman (maksimum 5 tipe halaman representatif per website)",
    "Tipe Halaman": "Homepage, Profil, Layanan, Konten, Interaksi/Kontak",
    "Alat Audit": "axe-core (automated accessibility testing)",
    "Standar": "WCAG 2.2",
    "Level Cakupan": "Level A dan Level AA yang didukung rule engine axe-core",
    "Sumber Data Demografis": "BPS (data sekunder, prevalensi kesulitan fungsional per wilayah)",
    "Metode Keputusan": "Simple Additive Weighting (SAW), 3 skenario bobot",
}

METHODOLOGY_PIPELINE = [
    "Data Collection", "Data Integration", "Data Cleaning", "Hash Deduplication",
    "Failure Rate", "Technical Score", "Demographic Score", "Baseline Comparison",
    "Normalization", "SAW", "Ranking", "Sensitivity Analysis", "Explainability",
    "Dashboard DSS",
]

RESEARCH_DATA_PIPELINE = [
    "website_master", "page_sample", "audit_findings", "sc_function_mapping",
    "bps_demography", "Integrated Dataset", "Scoring & Ranking",
]

RESEARCH_CONTRIBUTIONS = [
    "Integrated accessibility audit dataset (audit WCAG + demografi dalam satu pipeline).",
    "Pemetaan WCAG Success Criterion ke kategori kesulitan fungsional (functional difficulty mapping).",
    "Technical Score per website per kategori kesulitan fungsional.",
    "Demographic Score berbasis prevalensi kesulitan fungsional wilayah (data sekunder BPS).",
    "Priority ranking berbasis SAW yang mengintegrasikan skor teknis dan demografis.",
    "Analisis sensitivitas tiga skenario bobot untuk menguji kestabilan ranking.",
    "Perbandingan terhadap tiga baseline (raw findings, technical-only, demographic-only).",
    "Explainability tingkat website — penelusuran ranking kembali ke Success Criterion dan halaman sumber temuan.",
]

RESEARCH_LIMITATIONS = [
    "Audit otomatis axe-core BUKAN audit kepatuhan WCAG penuh (full WCAG compliance) — hanya mencakup barrier yang dapat dideteksi otomatis.",
    "Kategori kesulitan mendengar bernilai technical_score nol pada seluruh website karena axe-core tidak menguji elemen audio/video (mis. subtitle, transkrip); ini adalah keterbatasan cakupan deteksi otomatis, bukan bukti tiadanya hambatan bagi pengguna dengan kesulitan mendengar.",
    "Data demografi BPS adalah data sekunder prevalensi wilayah, BUKAN jumlah pengguna aktual masing-masing website.",
    "Tidak ada responden atau panel ahli eksternal yang dilibatkan dalam proses audit maupun validasi.",
    "Ranking yang dihasilkan bersifat decision-support / alat bantu prioritisasi, bukan keputusan final pemerintah.",
    "Sensitivity analysis dibatasi pada tiga skenario bobot yang ditentukan penelitian (S1/S2/S3), bukan eksplorasi ruang bobot penuh.",
    "Explainability yang disediakan bersifat analytical traceability (penelusuran Success Criterion yang berkontribusi terhadap skor), bukan Explainable AI dalam arti model machine learning.",
]

CLAIM_TERMINOLOGY = {
    "Hindari": [
        "WCAG compliance checker", "Explainable AI", "jumlah pengguna aktual website",
        "keputusan final pemerintah", "hubungan kausal", "signifikansi statistik (tanpa pengujian)",
    ],
    "Gunakan": [
        "automated-detectable accessibility barriers / automated accessibility findings",
        "explainability / analytical traceability",
        "prevalensi kesulitan fungsional wilayah berdasarkan data sekunder BPS",
        "decision-support / alat bantu prioritisasi",
        "asosiasi / korelasi (dengan uji statistik yang jelas)",
        "signifikan (p < 0.05) — hanya jika benar-benar diuji",
    ],
}

NAV_PAGES = [
    "01 · Executive Overview",
    "02 · Research Scope & Methodology",
    "03 · Audit Landscape",
    "04 · WCAG & Functional Mapping",
    "05 · Technical & Demographic Score",
    "06 · Normalization & SAW Model",
    "07 · Priority Ranking",
    "08 · Scenario & Sensitivity",
    "09 · Baseline Comparison",
    "10 · Explainability",
    "11 · Website Explorer",
    "12 · Research Results Tables",
    "13 · Research Figures",
    "14 · Data & Provenance",
    "15 · Downloads",
]


# =====================================================================
# 1. PAGE CONFIG & STYLE
# =====================================================================

st.set_page_config(
    page_title="DSS Prioritas Aksesibilitas Website Pemerintah",
    page_icon="\u267F",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1400px; }
        html, body, [class*="css"] { font-family: "Inter", "Segoe UI", sans-serif; }

        .hero-card {
            padding: 2rem 2.2rem;
            border-radius: 20px;
            background: linear-gradient(120deg, #0f172a 0%, #1e3a8a 55%, #0891b2 100%);
            color: #f8fafc;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.22);
            margin-bottom: 1.4rem;
        }
        .hero-card h1 { color: #ffffff; font-size: 2rem; margin-bottom: 0.35rem; }
        .hero-card p { color: #dbeafe; font-size: 1.02rem; margin-bottom: 0; }
        .hero-badge {
            display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px;
            background: rgba(255,255,255,0.14); color: #e0f2fe; font-size: 0.78rem;
            margin-right: 0.4rem; border: 1px solid rgba(255,255,255,0.25);
        }

        .kpi-card {
            padding: 1rem 1.1rem; border-radius: 14px; background: #ffffff;
            border: 1px solid #e2e8f0; box-shadow: 0 6px 16px rgba(15,23,42,0.05);
            height: 100%;
        }
        .kpi-value { font-size: 1.6rem; font-weight: 700; color: #0f172a; margin: 0; }
        .kpi-label { font-size: 0.8rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: .03em;}

        .section-card {
            padding: 1.1rem 1.25rem; border-radius: 14px; background: #ffffff;
            border: 1px solid #e2e8f0; box-shadow: 0 4px 14px rgba(15,23,42,0.04);
            margin-bottom: 0.9rem;
        }
        .interp-box {
            border-left: 4px solid #0891b2; background: #f0f9ff; border-radius: 8px;
            padding: 0.8rem 1rem; margin-top: 0.6rem; font-size: 0.92rem;
        }
        .interp-box b { color: #0f172a; }

        .badge-robust { background:#dcfce7; color:#166534; padding:0.15rem 0.55rem; border-radius:999px; font-size:0.78rem; font-weight:600;}
        .badge-cukup { background:#fef3c7; color:#92400e; padding:0.15rem 0.55rem; border-radius:999px; font-size:0.78rem; font-weight:600;}
        .badge-sensitif { background:#fee2e2; color:#991b1b; padding:0.15rem 0.55rem; border-radius:999px; font-size:0.78rem; font-weight:600;}

        .stTabs [data-baseweb="tab"] { border-radius: 999px; padding: 0.4rem 0.9rem; }
        section[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
        section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        section[data-testid="stSidebar"] .stRadio label { font-size: 0.86rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def stability_badge_html(status: str) -> str:
    cls = {"Robust": "badge-robust", "Cukup stabil": "badge-cukup", "Sensitif": "badge-sensitif"}.get(status, "badge-cukup")
    return f'<span class="{cls}">{status}</span>'


def interpretation_panel(observation: str, implication: str, caution: str) -> None:
    st.markdown(
        f"""
        <div class="interp-box">
        <b>OBSERVATION</b> — {observation}<br/>
        <b>IMPLICATION</b> — {implication}<br/>
        <b>CAUTION</b> — {caution}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =====================================================================
# 2. DATA LOADING LAYER
#    Semua fungsi bersifat read-only & fail-soft: file yang tidak
#    tersedia menghasilkan None, bukan exception yang menghentikan app.
# =====================================================================

@st.cache_data(show_spinner=False)
def sha256_file(path_str: str) -> Optional[str]:
    path = Path(path_str)
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@st.cache_data(show_spinner=False)
def load_csv_cached(path_str: str) -> Optional[pd.DataFrame]:
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_json_cached(path_str: str) -> Optional[dict]:
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_joblib_cached(path_str: str) -> Optional[dict]:
    path = Path(path_str)
    if not path.exists() or not HAS_JOBLIB:
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def file_meta(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "size_kb": round(stat.st_size / 1024, 1),
        "modified": pd.Timestamp(stat.st_mtime, unit="s").strftime("%Y-%m-%d %H:%M"),
    }


class DataBundle:
    """Kumpulan seluruh dataset & artefak beserta catatan provenance."""

    def __init__(self):
        self.notes: list[str] = []

        # --- LEVEL 3: dataset baseline (wajib, path fixed sesuai spec) ---
        self.audit_baseline_path = DATA_DIR / "audit_findings.csv"
        self.priority_baseline_path = DATA_DIR / "priority_results.csv"
        self.audit_baseline = load_csv_cached(str(self.audit_baseline_path))
        self.priority_baseline = load_csv_cached(str(self.priority_baseline_path))

        # --- Artefak notebook (Level 2 — analytical source of truth) ---
        self.page_sample = load_csv_cached(str(ARTIFACT_DIR / "page_sample_updated.csv"))
        self.sc_mapping = load_csv_cached(str(ARTIFACT_DIR / "sc_function_mapping.csv"))
        self.audit_integrated = load_csv_cached(str(ARTIFACT_DIR / "audit_findings_integrated.csv"))
        self.priority_notebook = load_csv_cached(str(ARTIFACT_DIR / "priority_results.csv"))
        self.top_issue_pages = load_csv_cached(str(ARTIFACT_DIR / "top_issue_affected_pages.csv"))
        self.baseline_stats = load_csv_cached(str(ARTIFACT_DIR / "baseline_comparison_stats.csv"))
        self.explainability_log = load_csv_cached(str(ARTIFACT_DIR / "explainability_drilldown_log.csv"))
        self.manifest = load_json_cached(str(ARTIFACT_DIR / "dataset_manifest_v1_0.json"))
        self.model_export = load_joblib_cached(str(ARTIFACT_DIR / "model_saw_v1_0.joblib"))

        # --- Resolusi priority_results: prioritaskan artefak notebook ---
        if self.priority_notebook is not None:
            self.priority = self.priority_notebook
            self.priority_source = f"artifacts/priority_results.csv ({len(self.priority_notebook)} baris — hasil notebook final)"
        elif self.priority_baseline is not None:
            self.priority = self.priority_baseline
            self.priority_source = f"data/priority_results.csv ({len(self.priority_baseline)} baris — dataset baseline, artefak notebook belum tersedia)"
            self.notes.append("priority_results.csv dari artifacts/ tidak ditemukan — dashboard menggunakan data/priority_results.csv sebagai fallback.")
        else:
            self.priority = None
            self.priority_source = "Tidak tersedia"

        # --- Resolusi audit findings: prioritaskan artefak integrated ---
        if self.audit_integrated is not None:
            self.audit = self.audit_integrated
            self.audit_source = f"artifacts/audit_findings_integrated.csv ({len(self.audit_integrated)} baris — hasil integrasi notebook)"
        elif self.audit_baseline is not None:
            self.audit = self.audit_baseline
            self.audit_source = f"data/audit_findings.csv ({len(self.audit_baseline)} baris — dataset baseline mentah, belum terintegrasi mapping fungsional)"
            self.notes.append("audit_findings_integrated.csv dari artifacts/ tidak ditemukan — dashboard menggunakan data/audit_findings.csv (belum memiliki category/mapping_value).")
        else:
            self.audit = None
            self.audit_source = "Tidak tersedia"

        # --- Website lookup (institution_name, province_name) ---
        self.website_lookup = None
        if self.audit_integrated is not None:
            cols = [c for c in ["website_id", "institution_name", "province_name", "bps_region_code"]
                    if c in self.audit_integrated.columns]
            if "website_id" in cols:
                self.website_lookup = (
                    self.audit_integrated[cols].drop_duplicates(subset="website_id").reset_index(drop=True)
                )
        if self.website_lookup is None:
            self.notes.append("Nama institusi/provinsi tidak dapat ditampilkan — memerlukan artifacts/audit_findings_integrated.csv.")

        # missing-required flag
        self.missing_required = self.audit_baseline is None or self.priority_baseline is None

    def website_label(self, website_id: str) -> str:
        if self.website_lookup is not None:
            row = self.website_lookup[self.website_lookup["website_id"] == website_id]
            if len(row):
                inst = row.iloc[0].get("institution_name")
                if isinstance(inst, str) and inst.strip():
                    return f"{website_id} — {inst}"
        return website_id

    def merge_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or self.website_lookup is None or "website_id" not in df.columns:
            return df
        return df.merge(self.website_lookup, on="website_id", how="left")


@st.cache_resource(show_spinner=False)
def get_data_bundle() -> DataBundle:
    return DataBundle()


def missing_required_block():
    st.error(
        "**Required dataset unavailable.**\n\n"
        "Expected:\n"
        f"- {'✓' if (DATA_DIR / 'audit_findings.csv').exists() else '✗'} `data/audit_findings.csv`\n"
        f"- {'✓' if (DATA_DIR / 'priority_results.csv').exists() else '✗'} `data/priority_results.csv`\n\n"
        "Letakkan kedua file tersebut pada folder `data/` di direktori yang sama dengan `app.py`, "
        "lalu muat ulang aplikasi."
    )


def optional_artifact_notice(label: str) -> None:
    st.info(f"Optional research artifact unavailable: **{label}**. Sebagian visualisasi/download terkait fitur ini dinonaktifkan.")


# =====================================================================
# 3. SHARED HELPERS UNTUK ANALITIK RINGAN (TIDAK MENGUBAH METODE)
#    Fungsi berikut hanya melakukan agregasi/filtering tampilan atas
#    kolom yang sudah dihasilkan notebook — tidak menghitung skor baru.
# =====================================================================

def category_scenario_slice(priority_df: pd.DataFrame, category: str, scenario: str) -> pd.DataFrame:
    return priority_df[(priority_df["category"] == category) & (priority_df["scenario"] == scenario)].copy()


def score_only_slice(priority_df: pd.DataFrame, category: str, scenario_for_dedup: str = "S2") -> pd.DataFrame:
    """technical_score & demographic_score tidak bergantung skenario — ambil 1 baris representatif per website."""
    sub = priority_df[priority_df["category"] == category]
    if scenario_for_dedup in sub["scenario"].unique():
        sub = sub[sub["scenario"] == scenario_for_dedup]
    else:
        sub = sub.drop_duplicates(subset=["website_id"])
    return sub.copy()


def kpi_card(col, value, label):
    with col:
        st.markdown(
            f'<div class="kpi-card"><p class="kpi-value">{value}</p><p class="kpi-label">{label}</p></div>',
            unsafe_allow_html=True,
        )


# =====================================================================
# 4. PAGES
# =====================================================================

def page_executive_overview(db: DataBundle):
    st.markdown(
        """
        <div class="hero-card">
        <span class="hero-badge">GEMASTIK 2026 · Data Mining / Sistem Cerdas Terapan</span>
        <span class="hero-badge">Decision Support System</span>
        <h1>DSS Prioritas Aksesibilitas Website Pemerintah</h1>
        <p>Integrasi Audit WCAG dan Prevalensi Kesulitan Fungsional untuk Prioritas Perbaikan
        Aksesibilitas 30 Website Dinas Sosial Provinsi di Indonesia.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if db.missing_required:
        missing_required_block()
        return

    priority = db.priority
    audit = db.audit
    page_sample = db.page_sample

    n_website = priority["website_id"].nunique() if priority is not None else "—"
    n_pages = page_sample["page_id"].nunique() if page_sample is not None else (
        db.audit_baseline["page_id"].nunique() if db.audit_baseline is not None else "—"
    )
    n_valid_pages = (
        page_sample[page_sample["render_status"] == "rendered"]["page_id"].nunique()
        if page_sample is not None and "render_status" in page_sample.columns else "—"
    )
    n_findings = len(db.audit_baseline) if db.audit_baseline is not None else (len(audit) if audit is not None else "—")
    n_affected_nodes = (
        int(audit["affected_node_count"].sum()) if audit is not None and "affected_node_count" in audit.columns else "—"
    )
    n_sc = audit["wcag_sc"].nunique() if audit is not None and "wcag_sc" in audit.columns else "—"

    priority_1 = "—"
    if priority is not None:
        top_s2 = category_scenario_slice(priority, "melihat", "S2")
        top_row = top_s2[top_s2["rank"] == 1]
        if len(top_row):
            priority_1 = db.website_label(top_row.iloc[0]["website_id"])

    n_robust = "—"
    if priority is not None and "stability_status" in priority.columns:
        n_robust = priority.drop_duplicates(subset=["website_id", "category"])
        n_robust = int((n_robust["stability_status"] == "Robust").sum())

    st.markdown("#### Ringkasan Utama")
    r1 = st.columns(4)
    kpi_card(r1[0], n_website, "Website Diaudit")
    kpi_card(r1[1], n_pages, "Halaman Disampel")
    kpi_card(r1[2], n_valid_pages, "Halaman Valid (Rendered)")
    kpi_card(r1[3], f"{n_findings:,}" if isinstance(n_findings, int) else n_findings, "Temuan Audit")
    r2 = st.columns(4)
    kpi_card(r2[0], f"{n_affected_nodes:,}" if isinstance(n_affected_nodes, int) else n_affected_nodes, "Affected Nodes")
    kpi_card(r2[1], n_sc, "WCAG Success Criteria Terlibat")
    kpi_card(r2[2], priority_1, "Prioritas #1 (Melihat · S2)")
    kpi_card(r2[3], n_robust, "Website Berstatus Robust")

    st.caption(
        "Skenario acuan KPI di atas: **S2 (Balanced)**, kategori **Melihat**, kecuali dinyatakan lain. "
        "Seluruh angka bersumber langsung dari artefak penelitian — lihat halaman **Data & Provenance**."
    )

    st.markdown("---")
    st.markdown("### Alur Penelitian (Research Story)")
    story_cols = st.columns(5)
    story_steps = [
        ("Problem", "Sumber daya pemerintah untuk remediasi aksesibilitas terbatas — perlu prioritisasi berbasis data."),
        ("Evidence", "Automated accessibility findings (axe-core) + prevalensi kesulitan fungsional (data sekunder BPS)."),
        ("Method", "Technical Score + Demographic Score → Normalisasi → Simple Additive Weighting (SAW)."),
        ("Validation", "Perbandingan terhadap 3 baseline + sensitivity analysis 3 skenario bobot."),
        ("Output", "Priority Ranking per kategori kesulitan fungsional + Priority Explainability."),
    ]
    for col, (title, desc) in zip(story_cols, story_steps):
        with col:
            st.markdown(f"**{title}**")
            st.caption(desc)

    st.markdown("---")
    st.markdown("### Temuan Eksekutif")

    if priority is not None:
        s2 = priority[priority["scenario"] == "S2"]
        finding_cols = st.columns(2)
        with finding_cols[0]:
            st.markdown("**Finding 01 — Priority Tertinggi per Kategori (S2)**")
            for cat in CATEGORIES:
                sub = s2[(s2["category"] == cat) & (s2["rank"] == 1)]
                if len(sub):
                    st.write(f"- {CATEGORY_LABELS[cat]}: **{db.website_label(sub.iloc[0]['website_id'])}** "
                             f"(final score {sub.iloc[0]['final_score']:.4f})")
            st.markdown("**Finding 02 — Stabilitas Ranking**")
            if "stability_status" in priority.columns:
                dedup = priority.drop_duplicates(subset=["website_id", "category"])
                counts = dedup["stability_status"].value_counts()
                for status in STABILITY_ORDER:
                    st.write(f"- {status}: **{int(counts.get(status, 0))}** kombinasi website × kategori")
        with finding_cols[1]:
            st.markdown("**Finding 03 — Dominasi Komponen Skor**")
            top_by_cat = s2[s2["rank"] <= 3].copy()
            if len(top_by_cat):
                dominant = np.where(
                    top_by_cat["technical_norm"] >= top_by_cat["demographic_norm"], "Technical", "Demographic"
                )
                top_by_cat["dominant"] = dominant
                dom_counts = top_by_cat["dominant"].value_counts()
                for k, v in dom_counts.items():
                    st.write(f"- Top-3 didorong komponen **{k}**: {int(v)} kasus")
            st.markdown("**Finding 04 — Cakupan Deteksi Otomatis**")
            st.write("- Kategori **Mendengar** secara konsisten bernilai `technical_score = 0` "
                      "karena axe-core tidak menguji elemen audio/video — bukan indikasi tiadanya hambatan.")
    else:
        st.info("Tabel priority_results tidak tersedia untuk menyusun temuan eksekutif.")

    if db.notes:
        with st.expander("Catatan ketersediaan data pada halaman ini"):
            for n in db.notes:
                st.caption(f"• {n}")


def page_research_scope(db: DataBundle):
    st.header("Research Scope & Methodology")
    st.caption("Ruang lingkup dan alur metodologi penelitian — sumber kebenaran: dokumen penelitian/logbook (Level 1) dan notebook (Level 2).")

    scope_cols = st.columns(4)
    kpi_card(scope_cols[0], "30", "WEBSITES")
    kpi_card(scope_cols[1], "150", "SAMPLED PAGES")
    kpi_card(scope_cols[2], "5", "PAGE TYPES")
    kpi_card(scope_cols[3], "WCAG 2.2\nA + AA", "STANDARD & LEVEL")

    st.markdown("#### Tabel Ruang Lingkup")
    scope_df = pd.DataFrame(list(RESEARCH_SCOPE.items()), columns=["Scope", "Value"])
    st.table(scope_df)

    st.markdown("#### Research Data Pipeline")
    st.markdown(" → ".join(f"`{s}`" for s in RESEARCH_DATA_PIPELINE))

    st.markdown("#### Methodology Pipeline (Notebook)")
    st.markdown(" → ".join(f"`{s}`" for s in METHODOLOGY_PIPELINE))

    st.markdown("#### Research Contribution (Novelty)")
    for i, c in enumerate(RESEARCH_CONTRIBUTIONS, 1):
        st.write(f"{i}. {c}")
    st.caption(
        "Catatan: novelty penelitian BUKAN terletak pada metode SAW itu sendiri (bukan metode baru), "
        "melainkan pada integrasi temuan WCAG, kategori kesulitan fungsional, prevalensi wilayah, "
        "ranking per kategori, dan stability analysis dalam satu workflow yang terdokumentasi dan reproducible."
    )

    with st.expander("Batas Klaim Penelitian (istilah yang digunakan dashboard)"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Hindari**")
            for t in CLAIM_TERMINOLOGY["Hindari"]:
                st.write(f"❌ {t}")
        with c2:
            st.markdown("**Gunakan**")
            for t in CLAIM_TERMINOLOGY["Gunakan"]:
                st.write(f"✅ {t}")


def page_audit_landscape(db: DataBundle):
    st.header("Audit Landscape")
    audit = db.audit
    page_sample = db.page_sample
    st.caption(f"Sumber data temuan: {db.audit_source}")

    if audit is None:
        missing_required_block()
        return

    tabs = st.tabs(["Website & Page Coverage", "Render Status", "Findings Distribution", "Findings per Website/Page"])

    with tabs[0]:
        if page_sample is not None:
            cov = page_sample.groupby("website_id")["page_id"].nunique().reset_index(name="n_halaman")
            cov = db.merge_labels(cov).sort_values("n_halaman")
            fig = px.bar(cov, x="n_halaman", y=cov.get("institution_name", cov["website_id"]),
                         orientation="h", title="Jumlah Halaman Sampel per Website",
                         labels={"n_halaman": "Jumlah halaman", "y": "Website"})
            fig.update_layout(height=700)
            st.plotly_chart(fig, use_container_width=True)
        else:
            optional_artifact_notice("artifacts/page_sample_updated.csv")

    with tabs[1]:
        if page_sample is not None and "render_status" in page_sample.columns:
            status_counts = page_sample["render_status"].value_counts().reset_index()
            status_counts.columns = ["Render Status", "Count"]
            fig = px.pie(status_counts, names="Render Status", values="Count", hole=0.45,
                         color="Render Status", color_discrete_map={"rendered": "#2f855a", "failed": "#c53030"},
                         title="Render Status Seluruh Halaman Sampel")
            st.plotly_chart(fig, use_container_width=True)
            interpretation_panel(
                "Sebagian kecil halaman gagal dirender saat proses audit otomatis.",
                "Halaman yang gagal dirender tidak digunakan sebagai basis temuan valid dan dikeluarkan dari perhitungan skor.",
                "Kegagalan render adalah keterbatasan teknis crawling/rendering, bukan indikasi tingkat aksesibilitas halaman tersebut.",
            )
        else:
            optional_artifact_notice("artifacts/page_sample_updated.csv (kolom render_status)")

    with tabs[2]:
        if "impact_label" in audit.columns:
            impact_counts = audit["impact_label"].value_counts().reindex(IMPACT_ORDER).fillna(0).reset_index()
            impact_counts.columns = ["Impact", "Count"]
            fig = px.bar(impact_counts, x="Impact", y="Count", color="Impact",
                         color_discrete_map=IMPACT_COLORS, title="Distribusi Temuan berdasarkan Impact")
            st.plotly_chart(fig, use_container_width=True)
        if "wcag_level" in audit.columns:
            level_counts = audit["wcag_level"].value_counts().reset_index()
            level_counts.columns = ["Level", "Count"]
            fig2 = px.bar(level_counts, x="Level", y="Count", title="Distribusi Temuan berdasarkan WCAG Level",
                          color_discrete_sequence=["#2f855a"])
            st.plotly_chart(fig2, use_container_width=True)
        if "wcag_sc" in audit.columns:
            top_sc = audit["wcag_sc"].value_counts().head(10).reset_index()
            top_sc.columns = ["WCAG SC", "Jumlah Temuan"]
            fig3 = px.bar(top_sc.sort_values("Jumlah Temuan"), x="Jumlah Temuan", y="WCAG SC", orientation="h",
                          title="Top 10 WCAG Success Criteria", color_discrete_sequence=["#805ad5"])
            st.plotly_chart(fig3, use_container_width=True)
        if "rule_id" in audit.columns:
            top_rule = audit["rule_id"].value_counts().head(10).reset_index()
            top_rule.columns = ["Rule ID", "Jumlah Temuan"]
            fig4 = px.bar(top_rule.sort_values("Jumlah Temuan"), x="Jumlah Temuan", y="Rule ID", orientation="h",
                          title="Top 10 Rule ID axe-core", color_discrete_sequence=["#2b6cb0"])
            st.plotly_chart(fig4, use_container_width=True)

    with tabs[3]:
        if "website_id" in audit.columns:
            per_website = audit.groupby("website_id").size().reset_index(name="jumlah_temuan")
            per_website = db.merge_labels(per_website).sort_values("jumlah_temuan", ascending=False)
            st.markdown("**Findings per Website**")
            st.dataframe(per_website, use_container_width=True, hide_index=True)
        if "page_id" in audit.columns:
            per_page = audit.groupby("page_id").size().reset_index(name="jumlah_temuan").sort_values("jumlah_temuan", ascending=False)
            st.markdown("**Findings per Page (Top 20)**")
            st.dataframe(per_page.head(20), use_container_width=True, hide_index=True)
        if "affected_node_count" in audit.columns:
            st.metric("Total Affected Nodes", f"{int(audit['affected_node_count'].sum()):,}")


def page_wcag_functional_mapping(db: DataBundle):
    st.header("WCAG & Functional Difficulty Mapping")
    st.caption("Pemetaan WCAG Success Criterion ke kategori kesulitan fungsional — komponen inti novelty penelitian.")

    sc_mapping = db.sc_mapping
    if sc_mapping is None:
        optional_artifact_notice("artifacts/sc_function_mapping.csv")
        return

    pivot = sc_mapping.pivot(index="wcag_sc", columns="category", values="mapping_value")
    ordered_cols = [c for c in CATEGORIES if c in pivot.columns]
    pivot = pivot[ordered_cols]

    fig = px.imshow(
        pivot, text_auto=".1f", color_continuous_scale="YlOrRd", aspect="auto",
        labels=dict(x="Kategori Kesulitan Fungsional", y="WCAG Success Criterion", color="Mapping value"),
        title="Mapping Matrix — WCAG SC × Functional Difficulty Category",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Tabel Mapping")
    display_cols = [c for c in ["wcag_sc", "category", "mapping_value", "source_type", "justification", "mapping_status"]
                     if c in sc_mapping.columns]
    st.dataframe(sc_mapping[display_cols].sort_values(["wcag_sc", "category"]), use_container_width=True, hide_index=True)

    st.markdown("#### Mapping Explanation")
    st.caption(
        "Nilai mapping (0.0–1.0) merepresentasikan **functional difficulty category** — seberapa relevan "
        "suatu WCAG Success Criterion terhadap kategori kesulitan fungsional tertentu, bukan pemetaan biner "
        "\"WCAG → jenis disabilitas\" yang disederhanakan."
    )
    for sc in sorted(sc_mapping["wcag_sc"].unique()):
        just = sc_mapping.loc[sc_mapping["wcag_sc"] == sc, "justification"]
        if len(just) and isinstance(just.iloc[0], str):
            with st.expander(f"SC {sc}"):
                st.write(just.iloc[0])


def page_technical_demographic_score(db: DataBundle):
    st.header("Technical & Demographic Score")
    priority = db.priority
    if priority is None:
        missing_required_block()
        return

    category = st.selectbox("Kategori Kesulitan Fungsional", CATEGORIES, format_func=lambda c: CATEGORY_LABELS[c])
    sub = score_only_slice(priority, category)
    sub_labeled = db.merge_labels(sub)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Technical Score Distribution**")
        fig = px.histogram(sub, x="technical_score", nbins=15, color_discrete_sequence=["#2b6cb0"])
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Technical score dibentuk dari temuan audit dan mempertimbangkan severity (impact_weight) "
            "serta relevansi fungsional (mapping_value) sesuai pipeline penelitian."
        )
    with col2:
        st.markdown("**Demographic Score Distribution**")
        fig2 = px.histogram(sub, x="demographic_score", nbins=15, color_discrete_sequence=["#dd6b20"])
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Demographic score bersumber dari prevalensi kesulitan fungsional wilayah (data sekunder BPS) — bukan jumlah pengguna aktual website.")

    st.markdown("#### Top Technical Burden")
    label_col = "institution_name" if "institution_name" in sub_labeled.columns else "website_id"
    top_tech = sub_labeled.nlargest(10, "technical_score")
    fig3 = px.bar(top_tech.sort_values("technical_score"), x="technical_score", y=label_col, orientation="h",
                  title=f"Top 10 Technical Burden — {CATEGORY_LABELS[category]}", color_discrete_sequence=["#c53030"])
    st.plotly_chart(fig3, use_container_width=True)

    st.markdown("#### Technical vs Demographic — Scatter")
    fig4 = px.scatter(
        sub_labeled, x="technical_norm", y="demographic_norm",
        size=sub_labeled["final_score"] if "final_score" in sub_labeled.columns else None,
        hover_name=label_col, color_discrete_sequence=[CATEGORY_COLORS[category]],
        labels={"technical_norm": "Technical (normalized)", "demographic_norm": "Demographic (normalized)"},
        title=f"Technical vs Demographic — {CATEGORY_LABELS[category]}",
    )
    st.plotly_chart(fig4, use_container_width=True)
    interpretation_panel(
        "Website dengan technical burden serupa dapat menempati posisi berbeda pada sumbu demografis.",
        "Dua website dengan kondisi teknis mirip dapat memperoleh prioritas berbeda ketika konteks demografis wilayahnya berbeda.",
        "Ukuran titik (final_score) hanya representatif untuk skenario bobot yang sedang aktif ditampilkan pada tabel priority_results.",
    )


def page_normalization_saw(db: DataBundle):
    st.header("Normalization & SAW Decision Model")
    priority = db.priority
    if priority is None:
        missing_required_block()
        return

    st.markdown("#### Normalization Analysis")
    st.markdown("`Raw Score` → `Min-Max Normalization` → `Comparable Score`")
    category = st.selectbox("Kategori untuk tabel normalisasi", CATEGORIES, format_func=lambda c: CATEGORY_LABELS[c], key="norm_cat")
    sub = score_only_slice(priority, category)
    norm_table = db.merge_labels(sub)[
        [c for c in ["website_id", "institution_name", "technical_score", "technical_norm", "demographic_score", "demographic_norm"] if c in db.merge_labels(sub).columns]
    ]
    st.dataframe(norm_table, use_container_width=True, hide_index=True)

    fig = px.scatter(sub, x="technical_score", y="technical_norm", color_discrete_sequence=["#2b6cb0"],
                      title="Raw vs Normalized — Technical Score")
    fig2 = px.scatter(sub, x="demographic_score", y="demographic_norm", color_discrete_sequence=["#dd6b20"],
                       title="Raw vs Normalized — Demographic Score")
    c1, c2 = st.columns(2)
    c1.plotly_chart(fig, use_container_width=True)
    c2.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.markdown("#### Decision Model — Simple Additive Weighting (SAW)")
    st.markdown(
        "```\n"
        "Technical Score (normalized)\n"
        "        +\n"
        "Demographic Score (normalized)\n"
        "        ↓  (dibobot sesuai skenario)\n"
        "Weighted Sum\n"
        "        ↓\n"
        "Final SAW Score\n"
        "        ↓\n"
        "Rank (per kategori × skenario)\n"
        "```"
    )
    scen_table = pd.DataFrame(
        [{"Skenario": k, "Bobot Technical": v[0], "Bobot Demographic": v[1], "Deskripsi": SCENARIO_LABELS[k]} for k, v in SCENARIOS.items()]
    )
    st.table(scen_table.set_index("Skenario"))
    st.caption(
        "Formula, bobot, dan hasil SAW pada halaman ini identik dengan output "
        "`fixed_notebook_enriched.ipynb` — dashboard tidak menghitung ulang dengan formula berbeda."
    )

    if db.model_export:
        with st.expander("Parameter Model Resmi (dari model_saw_v1_0.joblib)"):
            st.json({k: v for k, v in db.model_export.items() if k != "sc_function_weights"})
    elif not HAS_JOBLIB:
        st.caption("Catatan: pustaka `joblib` tidak tersedia di lingkungan ini sehingga parameter model resmi tidak dapat dimuat.")
    else:
        optional_artifact_notice("artifacts/model_saw_v1_0.joblib")


def page_priority_ranking(db: DataBundle):
    st.header("Priority Ranking")
    priority = db.priority
    if priority is None:
        missing_required_block()
        return

    scenario = st.selectbox("Skenario Bobot", list(SCENARIOS.keys()), index=1, format_func=lambda s: SCENARIO_LABELS[s])
    st.info(SCENARIO_LABELS[scenario])

    tabs = st.tabs([CATEGORY_LABELS[c] for c in CATEGORIES] + ["Semua Kategori"])
    for tab, category in zip(tabs[:-1], CATEGORIES):
        with tab:
            sub = category_scenario_slice(priority, category, scenario)
            sub = db.merge_labels(sub).sort_values("rank")
            label_col = "institution_name" if "institution_name" in sub.columns else "website_id"

            top10 = sub.head(10).sort_values("final_score")
            fig = px.bar(
                top10, x="final_score", y=label_col, orientation="h",
                text=top10["rank"].astype(str).radd("Rank "),
                color_discrete_sequence=[CATEGORY_COLORS[category]],
                title=f"Top 10 Priority — {CATEGORY_LABELS[category]} ({scenario})",
            )
            st.plotly_chart(fig, use_container_width=True)

            display_cols = [c for c in ["rank", "website_id", "institution_name", "technical_score",
                                         "demographic_score", "final_score", "stability_status"] if c in sub.columns]
            table = sub[display_cols].copy()
            if "stability_status" in table.columns:
                table["stability_status"] = table["stability_status"].apply(stability_badge_html)
            st.markdown(table.to_html(escape=False, index=False), unsafe_allow_html=True)

    with tabs[-1]:
        sub_all = priority[priority["scenario"] == scenario]
        fig_all = px.histogram(sub_all, x="final_score", color="category", nbins=20, barmode="overlay",
                                color_discrete_map=CATEGORY_COLORS, opacity=0.6,
                                title=f"Distribusi Final Score per Kategori — Skenario {scenario}")
        st.plotly_chart(fig_all, use_container_width=True)


def page_scenario_sensitivity(db: DataBundle):
    st.header("Scenario & Sensitivity")
    priority = db.priority
    if priority is None:
        missing_required_block()
        return

    category = st.selectbox("Kategori", CATEGORIES, format_func=lambda c: CATEGORY_LABELS[c], key="sens_cat")
    sub = priority[priority["category"] == category]

    st.markdown("#### Ranking Across Scenarios")
    wide = sub.pivot_table(index="website_id", columns="scenario", values="rank").reset_index()
    wide = db.merge_labels(wide)
    label_col = "institution_name" if "institution_name" in wide.columns else "website_id"

    fig = go.Figure()
    for _, row in wide.iterrows():
        rank_range = max(row["S1"], row["S2"], row["S3"]) - min(row["S1"], row["S2"], row["S3"])
        color = "#c53030" if rank_range >= 10 else "#a0aec0"
        fig.add_trace(go.Scatter(
            x=["S1", "S2", "S3"], y=[row["S1"], row["S2"], row["S3"]],
            mode="lines+markers", line=dict(color=color, width=1.4),
            name=str(row[label_col]), showlegend=False,
            hovertemplate=f"{row[label_col]}<br>%{{x}}: rank %{{y}}<extra></extra>",
        ))
    fig.update_yaxes(autorange="reversed", title="Rank")
    fig.update_layout(title=f"Pergerakan Rank Lintas Skenario — {CATEGORY_LABELS[category]} (merah = rank range ≥ 10)", height=550)
    st.plotly_chart(fig, use_container_width=True)
    interpretation_panel(
        "Sebagian website menunjukkan pergerakan rank besar antar skenario bobot, sebagian lain relatif stabil.",
        "Sensitivitas keputusan terhadap perubahan bobot dapat dilihat langsung dari kemiringan garis di atas.",
        "Garis merah menandai rank range ≥ 10 sebagai ambang visual, bukan ambang statistik formal.",
    )

    st.markdown("---")
    st.markdown("#### Sensitivity / Stability")
    st.caption(" · ".join(f"**{k}**: {v}" for k, v in STABILITY_DEFINITION.items()))

    if "stability_status" in sub.columns:
        stability_dedup = sub.drop_duplicates(subset=["website_id"])
        stab_counts = stability_dedup["stability_status"].value_counts().reindex(STABILITY_ORDER).fillna(0).reset_index()
        stab_counts.columns = ["Status", "Jumlah Website"]
        fig2 = px.bar(stab_counts, x="Status", y="Jumlah Website", color="Status",
                      color_discrete_map=STABILITY_COLORS, title=f"Stability Distribution — {CATEGORY_LABELS[category]}")
        st.plotly_chart(fig2, use_container_width=True)

        stable_list = db.merge_labels(stability_dedup[stability_dedup["stability_status"] == "Robust"])
        sensitive_list = db.merge_labels(stability_dedup[stability_dedup["stability_status"] == "Sensitif"])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Website Robust**")
            col = "institution_name" if "institution_name" in stable_list.columns else "website_id"
            st.dataframe(stable_list[[col]], hide_index=True, use_container_width=True)
        with c2:
            st.markdown("**Website Sensitif**")
            col = "institution_name" if "institution_name" in sensitive_list.columns else "website_id"
            st.dataframe(sensitive_list[[col]], hide_index=True, use_container_width=True)
    else:
        optional_artifact_notice("kolom stability_status pada priority_results.csv")


def page_baseline_comparison(db: DataBundle):
    st.header("Baseline Comparison")
    priority = db.priority
    if priority is None:
        missing_required_block()
        return

    for name, desc in BASELINE_DEFINITIONS.items():
        st.markdown(f"**{name}** — {desc}")

    st.markdown(
        "```\n"
        "Baseline A (raw findings) → Baseline B (technical only) → Baseline C (demographic only)\n"
        "                                        ↓\n"
        "                         SAW (Technical + Demographic terintegrasi)\n"
        "                                        ↓\n"
        "                            Integrated Priority Ranking\n"
        "```"
    )
    st.caption("Tujuan perbandingan ini adalah menunjukkan nilai tambah integrasi data, bukan sekadar menampilkan ranking.")

    category = st.selectbox("Kategori", CATEGORIES, format_func=lambda c: CATEGORY_LABELS[c], key="baseline_cat")
    scenario = st.selectbox("Skenario", list(SCENARIOS.keys()), index=1, format_func=lambda s: SCENARIO_LABELS[s], key="baseline_scn")

    sub = category_scenario_slice(priority, category, scenario)
    baseline_cols = [c for c in ["baseline_a_rank", "baseline_b_rank", "baseline_c_rank"] if c in sub.columns]
    if baseline_cols:
        melted = sub.melt(id_vars=["website_id", "rank"], value_vars=baseline_cols,
                           var_name="baseline", value_name="baseline_rank")
        melted["baseline"] = melted["baseline"].map({
            "baseline_a_rank": "Baseline A", "baseline_b_rank": "Baseline B", "baseline_c_rank": "Baseline C"
        })
        fig = px.scatter(melted, x="baseline_rank", y="rank", color="baseline",
                          labels={"baseline_rank": "Rank Baseline", "rank": "Rank SAW"},
                          title=f"SAW vs Baseline — {CATEGORY_LABELS[category]} ({scenario})")
        fig.add_shape(type="line", x0=1, y0=1, x1=len(sub), y1=len(sub), line=dict(dash="dash", color="gray"))
        st.plotly_chart(fig, use_container_width=True)
        interpretation_panel(
            "Titik yang menjauh dari garis diagonal menunjukkan perbedaan urutan prioritas antara SAW dan baseline terkait.",
            "Perbedaan ini mencerminkan kontribusi integrasi technical + demographic score terhadap urutan prioritas akhir.",
            "Diagonal hanya acuan visual (rank SAW = rank baseline), bukan garis regresi statistik.",
        )
    else:
        optional_artifact_notice("kolom baseline_a_rank/b_rank/c_rank pada priority_results.csv")

    st.markdown("#### Statistik Perbandingan (Spearman & Kendall)")
    if db.baseline_stats is not None:
        stats_sub = db.baseline_stats[
            (db.baseline_stats["category"] == category) & (db.baseline_stats["scenario"] == scenario)
        ]
        st.dataframe(stats_sub, use_container_width=True, hide_index=True)
        st.caption("`signifikan_p<0.05` menandakan hasil uji Spearman aktual dari notebook — bukan klaim yang ditambahkan dashboard.")
    else:
        optional_artifact_notice("artifacts/baseline_comparison_stats.csv")


def page_explainability(db: DataBundle):
    st.header("Priority Explainability")
    st.caption("Analytical traceability — penelusuran Success Criterion yang berkontribusi terhadap prioritas (bukan Explainable AI).")

    priority = db.priority
    top_issue_pages = db.top_issue_pages
    if priority is None:
        missing_required_block()
        return

    category = st.selectbox("Kategori", CATEGORIES, format_func=lambda c: CATEGORY_LABELS[c], key="explain_cat")
    scenario = st.selectbox("Skenario", list(SCENARIOS.keys()), index=1, format_func=lambda s: SCENARIO_LABELS[s], key="explain_scn")
    sub = category_scenario_slice(priority, category, scenario).sort_values("rank")
    sub_labeled = db.merge_labels(sub)
    label_col = "institution_name" if "institution_name" in sub_labeled.columns else "website_id"

    website_choice = st.selectbox("Pilih Website", sub_labeled["website_id"], format_func=db.website_label)
    row = sub_labeled[sub_labeled["website_id"] == website_choice].iloc[0]

    st.markdown(f"### Why is **{db.website_label(website_choice)}** prioritized?")
    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, int(row["rank"]), "Rank")
    kpi_card(c2, f"{row['final_score']:.4f}" if "final_score" in row else "—", "Final Score")
    kpi_card(c3, f"{row['technical_score']:.4f}" if "technical_score" in row else "—", "Technical Score")
    kpi_card(c4, f"{row['demographic_score']:.6f}" if "demographic_score" in row else "—", "Demographic Score")
    if "stability_status" in row:
        st.markdown(f"Stability status: {stability_badge_html(row['stability_status'])}", unsafe_allow_html=True)

    st.markdown("#### Top 3 Contributing Success Criteria")
    top_sc_cols = [c for c in ["top_issue_1", "top_issue_2", "top_issue_3"] if c in row]
    top_scs = [row[c] for c in top_sc_cols if row.get(c, "-") != "-"]
    if top_scs:
        st.write(", ".join(f"`{sc}`" for sc in top_scs))
        if top_issue_pages is not None:
            detail = top_issue_pages[
                (top_issue_pages["website_id"] == website_choice) & (top_issue_pages["category"] == category)
            ]
            st.dataframe(detail, use_container_width=True, hide_index=True)
        else:
            optional_artifact_notice("artifacts/top_issue_affected_pages.csv")
    else:
        st.caption("Tidak ada Top Issue relevan tercatat untuk kombinasi website/kategori ini.")

    if db.explainability_log is not None:
        with st.expander("Explainability Drill-down Log (notebook — contoh rank tertinggi & terendah)"):
            st.dataframe(db.explainability_log, use_container_width=True, hide_index=True)


def page_website_explorer(db: DataBundle):
    st.header("Website Explorer")
    priority = db.priority
    if priority is None:
        missing_required_block()
        return

    website_ids = sorted(priority["website_id"].unique())
    website_choice = st.selectbox("Pilih Website", website_ids, format_func=db.website_label)

    profile = db.website_lookup
    if profile is not None:
        row = profile[profile["website_id"] == website_choice]
        if len(row):
            r = row.iloc[0]
            st.markdown(f"### {r.get('institution_name', website_choice)}")
            st.caption(f"Provinsi: {r.get('province_name', '—')} · Kode wilayah BPS: {r.get('bps_region_code', '—')}")
    else:
        st.markdown(f"### {website_choice}")

    scenario = st.selectbox("Skenario", list(SCENARIOS.keys()), index=1, format_func=lambda s: SCENARIO_LABELS[s], key="explorer_scn")

    tabs = st.tabs([CATEGORY_LABELS[c] for c in CATEGORIES])
    for tab, category in zip(tabs, CATEGORIES):
        with tab:
            row = priority[(priority["website_id"] == website_choice) & (priority["category"] == category)
                            & (priority["scenario"] == scenario)]
            if not len(row):
                st.info("Data tidak tersedia untuk kombinasi ini.")
                continue
            row = row.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            kpi_card(c1, int(row["rank"]), "Priority Rank")
            kpi_card(c2, f"{row['final_score']:.4f}", "Final Score")
            kpi_card(c3, f"{row['technical_score']:.4f}", "Technical Score")
            kpi_card(c4, f"{row['demographic_score']:.6f}", "Demographic Score")

            if "stability_status" in row:
                st.markdown(f"**Stability:** {stability_badge_html(row['stability_status'])}", unsafe_allow_html=True)
            if all(c in row for c in ["baseline_a_rank", "baseline_b_rank", "baseline_c_rank"]):
                st.markdown(
                    f"**Baseline ranks** — A: {int(row['baseline_a_rank'])} · "
                    f"B: {int(row['baseline_b_rank'])} · C: {int(row['baseline_c_rank'])}"
                )

            top_scs = [row[c] for c in ["top_issue_1", "top_issue_2", "top_issue_3"] if c in row and row[c] != "-"]
            st.markdown("**Top WCAG Issues:** " + (", ".join(f"`{s}`" for s in top_scs) if top_scs else "—"))

            if db.top_issue_pages is not None and top_scs:
                affected = db.top_issue_pages[
                    (db.top_issue_pages["website_id"] == website_choice) & (db.top_issue_pages["category"] == category)
                ]
                st.markdown("**Affected Pages**")
                st.dataframe(affected, use_container_width=True, hide_index=True)

            if db.audit is not None and "website_id" in db.audit.columns:
                site_findings = db.audit[db.audit["website_id"] == website_choice]
                if "category" in site_findings.columns:
                    site_findings = site_findings[site_findings["category"] == category]
                if "impact_label" in site_findings.columns and len(site_findings):
                    impact_dist = site_findings["impact_label"].value_counts().reindex(IMPACT_ORDER).fillna(0)
                    st.markdown("**Impact Distribution (temuan pada website ini)**")
                    st.bar_chart(impact_dist)


def page_research_results_tables(db: DataBundle):
    st.header("Research Results")
    st.caption("Tabel siap kutip untuk Bab Hasil dan Pembahasan.")

    priority = db.priority
    audit = db.audit

    tables = []
    if audit is not None:
        overview = pd.DataFrame({
            "Dataset": ["audit_findings", "priority_results"],
            "Rows": [len(audit), len(priority) if priority is not None else 0],
        })
        tables.append(("Table 1 — Dataset Overview", overview))
        if "website_id" in audit.columns:
            coverage = audit.groupby("website_id").size().reset_index(name="jumlah_temuan")
            tables.append(("Table 2 — Website Coverage", db.merge_labels(coverage)))
        if "impact_label" in audit.columns:
            impact_dist = audit["impact_label"].value_counts().reindex(IMPACT_ORDER).reset_index()
            impact_dist.columns = ["Impact", "Count"]
            tables.append(("Table 4 — Impact Distribution", impact_dist))
        if "wcag_sc" in audit.columns:
            sc_dist = audit["wcag_sc"].value_counts().reset_index()
            sc_dist.columns = ["WCAG SC", "Count"]
            tables.append(("Table 5 — WCAG Success Criteria", sc_dist))

    if db.sc_mapping is not None:
        tables.append(("Table 6 — Functional Mapping", db.sc_mapping))

    if priority is not None:
        tech_table = priority.drop_duplicates(subset=["website_id", "category"])[
            [c for c in ["website_id", "category", "technical_score", "technical_norm"] if c in priority.columns]
        ]
        tables.append(("Table 7 — Technical Score", tech_table))
        demo_table = priority.drop_duplicates(subset=["website_id", "category"])[
            [c for c in ["website_id", "category", "demographic_score", "demographic_norm"] if c in priority.columns]
        ]
        tables.append(("Table 8 — Demographic Score", demo_table))
        tables.append(("Table 11 — Priority Ranking (seluruh kategori & skenario)", priority))
        if "stability_status" in priority.columns:
            stability_table = priority.drop_duplicates(subset=["website_id", "category"])[
                ["website_id", "category", "stability_status"]
            ]
            tables.append(("Table 13 — Stability", stability_table))

    if db.baseline_stats is not None:
        tables.append(("Table 14 — Baseline Comparison", db.baseline_stats))
    if db.explainability_log is not None:
        tables.append(("Table 15 — Explainability", db.explainability_log))

    if not tables:
        missing_required_block()
        return

    table_titles = [t[0] for t in tables]
    choice = st.selectbox("Pilih tabel", table_titles)
    for title, df in tables:
        if title == choice:
            st.markdown(f"#### {title}")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download tabel ini (CSV)", df.to_csv(index=False).encode("utf-8"),
                file_name=f"{title.split(' — ')[0].replace(' ', '_')}.csv", mime="text/csv",
            )


FIGURE_CATALOG = [
    ("fig_01_dataset_overview.png", "Dataset / Coverage", "Missing Value Overview", "Persentase missing value per dataset input."),
    ("fig_02_website_coverage.png", "Dataset / Coverage", "Website & Page Coverage", "Jumlah halaman dan temuan per website, serta status render."),
    ("fig_04_findings_by_impact.png", "Audit", "Findings by Impact & Level", "Top rule, top SC, distribusi impact, dan distribusi level WCAG."),
    ("fig_04b_weighted_impact_ranking.png", "Audit", "Weighted Impact Ranking", "Distribusi impact per website (stacked) dan ranking total weighted impact."),
    ("fig_05_top_wcag_rules.png", "Audit", "Heatmap Website × Impact", "Jumlah temuan per website menurut label impact."),
    ("fig_06_top_wcag_sc.png", "WCAG / Functional Difficulty", "Mapping Heatmap", "WCAG SC × Functional Difficulty Category (mapping value)."),
    ("fig_07_technical_score.png", "Technical Score", "Technical Score Overview", "Ranking, boxplot, distribusi, dan heatmap technical score per kategori."),
    ("fig_08_demographic_score.png", "Demographic Score", "Demographic Score Overview", "Prevalensi per provinsi dan distribusi demographic score per kategori."),
    ("fig_09_score_comparison.png", "Normalization", "Raw vs Normalized", "Perbandingan technical & demographic score sebelum vs sesudah normalisasi."),
    ("fig_09b_category_comparison.png", "Normalization", "Perbandingan Kategori", "Rata-rata skor, boxplot, dan scatter antar kategori kesulitan fungsional."),
    ("fig_10_saw_ranking.png", "SAW", "Komposisi Final Score", "Kontribusi weighted technical vs demographic — top 10 kategori melihat per skenario."),
    ("fig_10b_top10_ranking.png", "Ranking", "Top 10 Priority (Melihat, S2)", "Top 10 ranking dan distribusi final score seluruh kategori."),
    ("fig_11_scenario_comparison.png", "Scenario", "Rank Movement (Melihat)", "Pergerakan rank lintas skenario S1/S2/S3."),
    ("fig_12_ranking_stability.png", "Stability", "Rank Range per Kategori", "Distribusi rank range lintas skenario per kategori."),
    ("fig_13_sensitivity_analysis.png", "Stability", "Sensitivity Summary", "Stability status per kategori, frekuensi Top-3, dan distribusi rank range."),
    ("fig_14_explainability.png", "Explainability", "Kontribusi SC (Melihat)", "Kontribusi tiap SC terhadap technical score kategori melihat."),
    ("fig_15_priority_profile.png", "Explainability", "Priority Profile (Top 5)", "Scatter technical vs demographic norm, ukuran titik = final score."),
    ("fig_relationship_correlation.png", "Explainability", "Correlation Matrix", "Korelasi Spearman antar variabel numerik relevan (kategori melihat, S2)."),
    ("fig_relationship_scatter.png", "Explainability", "Findings vs Technical Score", "Hubungan jumlah temuan dan weighted impact terhadap technical score."),
    ("dashboard_top10_per_kategori.png", "Ranking", "Dashboard — Top 10 per Kategori", "Ringkasan top 10 prioritas ketiga kategori pada skenario S2."),
    ("dashboard_stabilitas_ranking.png", "Stability", "Dashboard — Stabilitas Ranking", "Ringkasan status kestabilan ranking per kategori."),
]


def page_research_figures(db: DataBundle):
    st.header("Research Figures")
    groups = sorted(set(g for _, g, _, _ in FIGURE_CATALOG))
    group_choice = st.selectbox("Kelompok Figure", ["Semua"] + groups)

    any_found = False
    for fname, group, title, caption in FIGURE_CATALOG:
        if group_choice != "Semua" and group != group_choice:
            continue
        fpath = ARTIFACT_DIR / fname
        with st.container():
            st.markdown(f"**{title}** · _{group}_")
            if fpath.exists():
                any_found = True
                st.image(str(fpath), caption=caption, use_container_width=True)
                with open(fpath, "rb") as f:
                    st.download_button(f"Download {fname}", f.read(), file_name=fname, mime="image/png", key=f"dl_{fname}")
            else:
                st.caption(f"Figure belum tersedia: `artifacts/{fname}`")
            st.markdown("---")

    if not any_found:
        optional_artifact_notice("figure PNG pada folder artifacts/ (fig_*.png, dashboard_*.png)")


def page_data_provenance(db: DataBundle):
    st.header("Data & Provenance")

    st.markdown("#### Resolusi Sumber Dataset Aktif")
    st.write(f"- **Priority results**: {db.priority_source}")
    st.write(f"- **Audit findings**: {db.audit_source}")

    st.markdown("#### File Registry")
    registry_files = [
        DATA_DIR / "audit_findings.csv", DATA_DIR / "priority_results.csv",
        ARTIFACT_DIR / "page_sample_updated.csv", ARTIFACT_DIR / "sc_function_mapping.csv",
        ARTIFACT_DIR / "audit_findings_integrated.csv", ARTIFACT_DIR / "priority_results.csv",
        ARTIFACT_DIR / "top_issue_affected_pages.csv", ARTIFACT_DIR / "baseline_comparison_stats.csv",
        ARTIFACT_DIR / "explainability_drilldown_log.csv",
        ARTIFACT_DIR / "model_saw_v1_0.joblib", ARTIFACT_DIR / "dataset_manifest_v1_0.json",
    ]
    rows = []
    for p in registry_files:
        meta = file_meta(p)
        rows.append({
            "File": str(p.relative_to(BASE_DIR)),
            "Tersedia": "✓" if meta["exists"] else "✗",
            "Ukuran (KB)": meta.get("size_kb", "—"),
            "Terakhir Diubah": meta.get("modified", "—"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Dataset Manifest (checksum SHA-256)")
    if db.manifest:
        st.json(db.manifest)
        with st.expander("Verifikasi checksum file lokal vs manifest"):
            for fname, expected_hash in db.manifest.get("checksums_sha256", {}).items():
                local_path = ARTIFACT_DIR / fname
                actual_hash = sha256_file(str(local_path))
                match = "✓ cocok" if actual_hash == expected_hash else ("✗ tidak cocok" if actual_hash else "file tidak ditemukan")
                st.write(f"- `{fname}`: {match}")
    else:
        optional_artifact_notice("artifacts/dataset_manifest_v1_0.json")

    st.markdown("#### Model Artifact")
    model_meta = file_meta(ARTIFACT_DIR / "model_saw_v1_0.joblib")
    if model_meta["exists"]:
        st.write(f"- Nama file: `model_saw_v1_0.joblib`")
        st.write(f"- Ukuran: {model_meta['size_kb']} KB")
        if db.model_export:
            st.write(f"- Model version: `{db.model_export.get('model_version', '—')}`")
            st.write(f"- Algorithm: `{db.model_export.get('algorithm', '—')}`")
        st.caption("Dashboard hanya menampilkan metadata model — tidak melakukan inference baru dari artefak ini.")
    else:
        optional_artifact_notice("artifacts/model_saw_v1_0.joblib")


def page_downloads(db: DataBundle):
    st.header("Download Center")
    st.caption("Hanya artefak yang benar-benar tersedia pada folder proyek yang ditampilkan.")

    catalog = [
        (DATA_DIR / "audit_findings.csv", "CSV", "Dataset baseline — temuan audit mentah"),
        (DATA_DIR / "priority_results.csv", "CSV", "Dataset baseline — hasil prioritisasi"),
        (ARTIFACT_DIR / "page_sample_updated.csv", "CSV", "Sampel halaman final (setelah dibatasi scope)"),
        (ARTIFACT_DIR / "sc_function_mapping.csv", "CSV", "Mapping WCAG SC → kategori kesulitan fungsional"),
        (ARTIFACT_DIR / "audit_findings_integrated.csv", "CSV", "Temuan audit terintegrasi dengan mapping & profil website"),
        (ARTIFACT_DIR / "priority_results.csv", "CSV", "Hasil prioritisasi final (notebook)"),
        (ARTIFACT_DIR / "top_issue_affected_pages.csv", "CSV", "Top issue & halaman terdampak per website"),
        (ARTIFACT_DIR / "baseline_comparison_stats.csv", "CSV", "Statistik perbandingan SAW vs baseline"),
        (ARTIFACT_DIR / "explainability_drilldown_log.csv", "CSV", "Log drill-down explainability (contoh rank tertinggi/terendah)"),
        (ARTIFACT_DIR / "model_saw_v1_0.joblib", "Model", "Model artifact SAW terekspor"),
        (ARTIFACT_DIR / "dataset_manifest_v1_0.json", "JSON", "Manifest checksum seluruh artefak"),
        (ARTIFACT_DIR / "dashboard_top10_per_kategori.png", "Image", "Figure — Top 10 per kategori"),
        (ARTIFACT_DIR / "dashboard_stabilitas_ranking.png", "Image", "Figure — Stabilitas ranking"),
    ]

    for path, ftype, purpose in catalog:
        meta = file_meta(path)
        cols = st.columns([3, 1, 1, 3, 1.4])
        cols[0].write(f"`{path.relative_to(BASE_DIR)}`")
        cols[1].write(ftype)
        cols[2].write(f"{meta.get('size_kb', '—')} KB" if meta["exists"] else "—")
        cols[3].write(purpose)
        if meta["exists"]:
            with open(path, "rb") as f:
                safe_key = str(path.relative_to(BASE_DIR)).replace("/", "_").replace("\\", "_")
                cols[4].download_button("Download", f.read(), file_name=path.name, key=f"dl_center_{safe_key}")
        else:
            cols[4].caption("Tidak tersedia")


# =====================================================================
# 5. APP ENTRYPOINT
# =====================================================================

def main():
    inject_css()
    db = get_data_bundle()

    st.sidebar.markdown("### Navigasi DSS")
    page = st.sidebar.radio("Pilih halaman", NAV_PAGES, label_visibility="collapsed")

    st.sidebar.divider()
    st.sidebar.caption(f"Versi aplikasi: **{APP_VERSION}**")
    st.sidebar.caption(f"Sumber priority_results: {db.priority_source}")
    st.sidebar.caption(f"Sumber audit_findings: {db.audit_source}")
    if db.manifest:
        st.sidebar.caption(f"Dataset version (manifest): `{db.manifest.get('dataset_version', '—')}`")

    dispatch = {
        NAV_PAGES[0]: page_executive_overview,
        NAV_PAGES[1]: page_research_scope,
        NAV_PAGES[2]: page_audit_landscape,
        NAV_PAGES[3]: page_wcag_functional_mapping,
        NAV_PAGES[4]: page_technical_demographic_score,
        NAV_PAGES[5]: page_normalization_saw,
        NAV_PAGES[6]: page_priority_ranking,
        NAV_PAGES[7]: page_scenario_sensitivity,
        NAV_PAGES[8]: page_baseline_comparison,
        NAV_PAGES[9]: page_explainability,
        NAV_PAGES[10]: page_website_explorer,
        NAV_PAGES[11]: page_research_results_tables,
        NAV_PAGES[12]: page_research_figures,
        NAV_PAGES[13]: page_data_provenance,
        NAV_PAGES[14]: page_downloads,
    }

    try:
        dispatch[page](db)
    except Exception as exc:  # pragma: no cover
        st.error("Terjadi kendala saat menampilkan halaman ini. Detail teknis dicatat pada log aplikasi.")
        st.caption(f"Ref: {type(exc).__name__}")
        raise


if __name__ == "__main__":
    main()
