from __future__ import annotations

from pathlib import Path
import hashlib
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st


# =========================================================
# Konfigurasi aplikasi
# =========================================================
APP_VERSION = "v1.1"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRIORITY_PATH = DATA_DIR / "priority_results.csv"
AUDIT_PATH = DATA_DIR / "audit_findings.csv"

CATEGORY_OPTIONS = {
    "Melihat": "melihat",
    "Mendengar": "mendengar",
    "Menggunakan Jari/Tangan": "tangan",
}

SCENARIO_OPTIONS = {
    "S1: Technical Dominant (0.7 / 0.3)": "S1",
    "S2: Balanced (0.5 / 0.5)": "S2",
    "S3: Demographic Sensitive (0.3 / 0.7)": "S3",
}

SCENARIO_DESCRIPTIONS = {
    "S1": "Technical Dominant — 70% skor teknis dan 30% skor demografis.",
    "S2": "Balanced — 50% skor teknis dan 50% skor demografis.",
    "S3": "Demographic Sensitive — 30% skor teknis dan 70% skor demografis.",
}

CATEGORY_DESCRIPTIONS = {
    "melihat": "Prioritas untuk kebutuhan pengguna dengan kesulitan melihat.",
    "mendengar": "Prioritas untuk kebutuhan pengguna dengan kesulitan mendengar.",
    "tangan": "Prioritas untuk kebutuhan pengguna dengan keterbatasan tangan atau motorik.",
}

SC_LABELS = {
    "1.1.1": "Alternatif teks untuk media non-teks",
    "1.3.1": "Informasi dan hubungan yang bermakna",
    "1.4.1": "Penggunaan warna",
    "1.4.3": "Kontras warna",
    "1.4.4": "Perbesaran teks",
    "2.1.1": "Akses keyboard",
    "2.1.3": "Keyboard (tanpa pengecualian)",
    "2.2.1": "Batas waktu yang dapat disesuaikan",
    "2.2.2": "Paus, berhenti, sembunyikan",
    "2.4.2": "Judul halaman",
    "2.4.4": "Tujuan tautan yang jelas",
    "3.1.1": "Bahasa halaman",
    "4.1.2": "Nama, peran, nilai",
}


st.set_page_config(
    page_title="DSS Prioritas Aksesibilitas Website",
    page_icon="♿",
    layout="wide",
)


def inject_custom_css() -> None:
    """Memberikan tema visual yang lebih menarik dan konsisten."""
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background: linear-gradient(135deg, #f8fbff 0%, #eef4ff 100%);
        }
        .hero-card {
            padding: 1.35rem 1.4rem;
            border-radius: 18px;
            background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
            color: white;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.16);
            margin-bottom: 1rem;
        }
        .hero-card h1 { color: white; margin-bottom: 0.2rem; }
        .hero-card p { color: #e2e8f0; margin-bottom: 0; }
        .info-card {
            padding: 0.95rem 1rem;
            border-radius: 14px;
            background: white;
            border: 1px solid #dbeafe;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
            height: 100%;
        }
        .stSidebar > div {
            background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 999px;
            padding: 0.45rem 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_custom_css()


# =========================================================
# Fungsi pembacaan dan validasi data
# =========================================================
def sha256_file(path: Path) -> str:
    """Menghitung checksum SHA-256 tanpa mengubah file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_latest_data_files(data_dir: Path) -> tuple[Path, Path]:
    """Memilih pasangan file CSV terbaru pada folder data."""
    priority_candidates = sorted(
        data_dir.glob("priority_results*.csv"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    audit_candidates = sorted(
        data_dir.glob("audit_findings*.csv"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )

    if not priority_candidates or not audit_candidates:
        raise FileNotFoundError("Tidak ada file data CSV yang ditemukan.")

    return priority_candidates[0], audit_candidates[0]


@st.cache_data(show_spinner=False)
def load_data(
    priority_path: str,
    audit_path: str,
    priority_signature: str,
    audit_signature: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Membaca dua dataset secara read-only."""
    priority = pd.read_csv(priority_path)
    audit = pd.read_csv(audit_path)

    priority_required = {
        "website_id",
        "category",
        "scenario",
        "technical_score",
        "technical_norm",
        "demographic_score",
        "demographic_norm",
        "final_score",
        "rank",
        "baseline_a_rank",
        "baseline_b_rank",
        "baseline_c_rank",
        "stability_status",
        "top_issue_1",
        "top_issue_2",
        "top_issue_3",
    }
    audit_required = {
        "finding_id",
        "page_id",
        "website_id",
        "rule_id",
        "wcag_sc",
        "impact_label",
        "affected_node_count",
        "finding_signature",
        "validation_status",
    }

    missing_priority = priority_required - set(priority.columns)
    missing_audit = audit_required - set(audit.columns)

    if missing_priority:
        raise ValueError(
            "Kolom priority_results.csv belum lengkap: "
            + ", ".join(sorted(missing_priority))
        )
    if missing_audit:
        raise ValueError(
            "Kolom audit_findings.csv belum lengkap: "
            + ", ".join(sorted(missing_audit))
        )

    # Normalisasi ringan hanya di memori; file sumber tidak ditulis ulang.
    priority["website_id"] = priority["website_id"].astype(str).str.strip()
    priority["category"] = priority["category"].astype(str).str.strip().str.lower()
    priority["scenario"] = priority["scenario"].astype(str).str.strip().str.upper()

    audit["website_id"] = audit["website_id"].astype(str).str.strip()
    audit["page_id"] = audit["page_id"].astype(str).str.strip()
    audit["rule_id"] = audit["rule_id"].astype(str).str.strip()
    audit["wcag_sc"] = audit["wcag_sc"].astype(str).str.strip()

    numeric_priority = [
        "technical_score",
        "technical_norm",
        "demographic_score",
        "demographic_norm",
        "final_score",
        "rank",
    ]
    for column in numeric_priority:
        priority[column] = pd.to_numeric(priority[column], errors="coerce")

    audit["affected_node_count"] = pd.to_numeric(
        audit["affected_node_count"], errors="coerce"
    ).fillna(0)

    return priority, audit


def calculate_stability(priority: pd.DataFrame) -> pd.DataFrame:
    """Menghitung status kestabilan berdasarkan rentang ranking lintas skenario."""
    rank_wide = (
        priority[["website_id", "category", "scenario", "rank"]]
        .pivot_table(index=["website_id", "category"], columns="scenario", values="rank")
        .reset_index()
    )

    scenario_columns = [column for column in ["S1", "S2", "S3"] if column in rank_wide.columns]
    if not scenario_columns:
        return pd.DataFrame(columns=["website_id", "category", "stability_status"])

    rank_wide["rank_range"] = rank_wide[scenario_columns].max(axis=1) - rank_wide[scenario_columns].min(axis=1)
    rank_wide["stability_status"] = np.where(
        rank_wide["rank_range"] <= 3,
        "Stabil",
        "Sensitif terhadap Bobot",
    )

    return rank_wide[["website_id", "category", "stability_status"]]


def stability_badge(status: str) -> str:
    """Badge teks yang tetap terbaca di tabel Streamlit."""
    badges = {
        "Stabil": "🟢 Stabil",
        "Sensitif terhadap Bobot": "🟡 Sensitif terhadap Bobot",
    }
    return badges.get(status, status)


def plot_top10_per_category(priority_df: pd.DataFrame, scenario: str) -> plt.Figure:
    """Menggambar plot Top 10 per kategori sesuai pola notebook."""
    categories = ["melihat", "mendengar", "tangan"]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=False)

    for ax, category in zip(axes, categories):
        category_data = priority_df[
            priority_df["category"].eq(category)
            & priority_df["scenario"].eq(scenario)
        ].copy()

        if category_data.empty:
            ax.text(0.5, 0.5, "Data tidak tersedia", ha="center", va="center")
            ax.set_title(f"Top 10 — {category.title()}")
            ax.set_axis_off()
            continue

        top10 = category_data.sort_values("rank").head(10)
        ax.barh(top10["website_id"], top10["final_score"], color="#2b6cb0")
        ax.invert_yaxis()
        ax.set_title(f"Top 10 Prioritas — {category.title()} ({scenario})")
        ax.set_xlabel("Final Score (SAW)")

    plt.tight_layout()
    return fig


def plot_stability_distribution(priority_df: pd.DataFrame) -> plt.Figure:
    """Menggambar distribusi stabilitas ranking lintas skenario."""
    counts = (
        priority_df.groupby(["category", "stability_status"])
        .size()
        .unstack(fill_value=0)
        .reindex(
            index=["melihat", "mendengar", "tangan"],
            columns=["Stabil", "Sensitif terhadap Bobot"],
            fill_value=0,
        )
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    counts.plot(kind="bar", stacked=True, ax=ax, color=["#2f855a", "#c53030"])
    ax.set_title("Stabilitas Ranking Lintas Skenario Bobot")
    ax.set_ylabel("Jumlah Website")
    ax.set_xlabel("Kategori Kesulitan Fungsional")
    plt.xticks(rotation=0)
    plt.tight_layout()
    return fig


def extract_wcag_sc(issue_value: object) -> str | None:
    """Mengambil nomor Success Criterion dari teks seperti 'SC 1.4.3'."""
    if pd.isna(issue_value):
        return None
    match = re.search(r"\d+(?:\.\d+)+", str(issue_value))
    return match.group(0) if match else None


def build_issue_detail(
    priority_row: pd.Series,
    audit: pd.DataFrame,
) -> pd.DataFrame:
    """Menyusun detail Top 3 Issue dan halaman terdampak untuk satu website."""
    website_id = str(priority_row["website_id"])
    website_findings = audit[audit["website_id"].eq(website_id)].copy()

    issue_rows: list[dict[str, object]] = []
    for order, column in enumerate(
        ["top_issue_1", "top_issue_2", "top_issue_3"],
        start=1,
    ):
        issue_label = priority_row.get(column)
        wcag_sc = extract_wcag_sc(issue_label)

        if wcag_sc is None:
            issue_rows.append(
                {
                    "Prioritas": order,
                    "WCAG / SC": "-",
                    "Deskripsi": "-",
                    "Rule ID": "-",
                    "Jumlah Temuan": 0,
                    "Affected Nodes": 0,
                    "Halaman Terdampak": "-",
                }
            )
            continue

        issue_findings = website_findings[
            website_findings["wcag_sc"].eq(wcag_sc)
        ].copy()

        rule_ids = sorted(
            issue_findings["rule_id"].dropna().astype(str).unique().tolist()
        )
        page_ids = sorted(
            issue_findings["page_id"].dropna().astype(str).unique().tolist()
        )

        issue_rows.append(
            {
                "Prioritas": order,
                "WCAG / SC": f"SC {wcag_sc}",
                "Deskripsi": SC_LABELS.get(wcag_sc, "Kebutuhan aksesibilitas terkait"),
                "Rule ID": ", ".join(rule_ids) if rule_ids else "-",
                "Jumlah Temuan": int(len(issue_findings)),
                "Affected Nodes": int(
                    issue_findings["affected_node_count"].sum()
                ),
                "Halaman Terdampak": ", ".join(page_ids) if page_ids else "-",
            }
        )

    return pd.DataFrame(issue_rows)


# =========================================================
# Load data
# =========================================================
try:
    PRIORITY_PATH, AUDIT_PATH = select_latest_data_files(DATA_DIR)
    priority_checksum = sha256_file(PRIORITY_PATH)
    audit_checksum = sha256_file(AUDIT_PATH)

    priority_results, audit_findings = load_data(
        str(PRIORITY_PATH),
        str(AUDIT_PATH),
        priority_checksum,
        audit_checksum,
    )
except FileNotFoundError as error:
    st.error(
        "Dataset tidak ditemukan. Pastikan folder data berisi minimal satu file:\n\n"
        "- `priority_results*.csv`\n"
        "- `audit_findings*.csv`"
    )
    st.stop()
except ValueError as error:
    st.error(str(error))
    st.stop()

stability = calculate_stability(priority_results)
priority_with_stability = priority_results.drop(
    columns=["stability_status"],
    errors="ignore",
).merge(
    stability,
    on=["website_id", "category"],
    how="left",
    validate="many_to_one",
)

priority_checksum = sha256_file(PRIORITY_PATH)
audit_checksum = sha256_file(AUDIT_PATH)


# =========================================================
# Sidebar: filter
# =========================================================
st.sidebar.header("🎛️ Filter Dashboard")
st.sidebar.caption(
    "Sesuaikan kategori dan skenario untuk melihat prioritas website yang ingin dikaji."
)

category_label = st.sidebar.selectbox(
    "Kategori Kesulitan Fungsional",
    options=list(CATEGORY_OPTIONS.keys()),
)
scenario_label = st.sidebar.selectbox(
    "Skenario Bobot",
    options=list(SCENARIO_OPTIONS.keys()),
)

selected_category = CATEGORY_OPTIONS[category_label]
selected_scenario = SCENARIO_OPTIONS[scenario_label]

st.sidebar.info(
    f"Kategori yang dipilih: **{category_label}**. {CATEGORY_DESCRIPTIONS[selected_category]}"
)
st.sidebar.info(SCENARIO_DESCRIPTIONS[selected_scenario])
st.sidebar.divider()
st.sidebar.subheader("📦 Metadata Dataset")
st.sidebar.caption(f"Versi aplikasi: **{APP_VERSION}**")
st.sidebar.caption(f"File prioritas: **{PRIORITY_PATH.name}**")
st.sidebar.caption(f"File audit: **{AUDIT_PATH.name}**")
st.sidebar.caption(f"priority_results checksum: **{priority_checksum[:12]}...**")
st.sidebar.caption(f"audit_findings checksum: **{audit_checksum[:12]}...**")


# =========================================================
# Halaman utama dan metodologi
# =========================================================
dashboard_tab, methodology_tab = st.tabs(
    ["Dashboard Prioritas", "Metodologi & Batasan"]
)

with dashboard_tab:
    st.markdown(
        """
        <div class="hero-card">
            <h1>♿ DSS Prioritas Aksesibilitas Website</h1>
            <p>Dashboard interaktif untuk memantau prioritas perbaikan aksesibilitas berdasarkan hasil analisis QA revisi dan data freeze terbaru.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        f"Filter aktif: **{category_label}** • **{scenario_label}** • **{selected_scenario}**"
    )

    filtered = priority_with_stability[
        priority_with_stability["category"].eq(selected_category)
        & priority_with_stability["scenario"].eq(selected_scenario)
    ].copy()

    if filtered.empty:
        st.warning(
            f"Kategori **{category_label}** tidak tersedia pada "
            "dataset hasil freeze yang sedang ditampilkan."
        )
    else:
        filtered = filtered.sort_values(
            ["rank", "final_score", "website_id"],
            ascending=[True, False, True],
        ).reset_index(drop=True)

        overview_tab, detail_tab, baseline_tab = st.tabs(
            ["Ringkasan", "Detail Website", "Perbandingan Baseline"]
        )

        with overview_tab:
            metric_1, metric_2, metric_3, metric_4 = st.columns(4)
            metric_1.metric("Jumlah Website", filtered["website_id"].nunique())
            metric_2.metric("Website Teratas", filtered.iloc[0]["website_id"])
            metric_3.metric(
                "Skor Akhir Tertinggi",
                f"{filtered['final_score'].max():.6f}",
            )
            metric_4.metric(
                "Website Sensitif",
                int((filtered["stability_status"] == "Sensitif terhadap Bobot").sum()),
            )

            st.subheader("📊 Tabel Ranking & Status Kestabilan")
            ranking_table = filtered[
                [
                    "rank",
                    "website_id",
                    "technical_score",
                    "demographic_score",
                    "final_score",
                    "stability_status",
                ]
            ].copy()

            ranking_table["rank"] = ranking_table["rank"].astype("Int64")
            ranking_table["stability_status"] = ranking_table[
                "stability_status"
            ].map(stability_badge)

            ranking_table = ranking_table.rename(
                columns={
                    "rank": "Rank",
                    "website_id": "Website ID",
                    "technical_score": "Skor Teknis",
                    "demographic_score": "Skor Demografis",
                    "final_score": "Skor Akhir",
                    "stability_status": "Status Kestabilan",
                }
            )

            st.dataframe(
                ranking_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rank": st.column_config.NumberColumn(format="%d"),
                    "Skor Teknis": st.column_config.NumberColumn(format="%.6f"),
                    "Skor Demografis": st.column_config.NumberColumn(format="%.6f"),
                    "Skor Akhir": st.column_config.NumberColumn(format="%.6f"),
                },
            )

            stability_summary = (
                filtered["stability_status"]
                .value_counts()
                .reindex(["Stabil", "Sensitif terhadap Bobot"], fill_value=0)
            )
            st.subheader("📈 Distribusi Status Kestabilan")
            st.bar_chart(stability_summary)

            st.caption(
                "Status Stabil menandakan perubahan peringkat antar skenario relatif kecil, sedangkan Sensitif terhadap Bobot menunjukkan hasil sangat bergantung pada bobot yang dipilih."
            )

            st.subheader("📈 Visualisasi dari Notebook")
            chart_col_1, chart_col_2 = st.columns([1.2, 0.8])
            with chart_col_1:
                top10_fig = plot_top10_per_category(
                    priority_with_stability[priority_with_stability["scenario"].eq(selected_scenario)].copy(),
                    selected_scenario,
                )
                st.pyplot(top10_fig, use_container_width=True)
            with chart_col_2:
                stability_fig = plot_stability_distribution(priority_with_stability)
                st.pyplot(stability_fig, use_container_width=True)

        with detail_tab:
            website_options = filtered["website_id"].tolist()
            selected_website = st.selectbox(
                "Pilih website",
                options=website_options,
                key="website_selector",
            )

            selected_row = filtered[
                filtered["website_id"].eq(selected_website)
            ].iloc[0]

            detail_1, detail_2, detail_3, detail_4 = st.columns(4)
            detail_1.metric("Website ID", selected_website)
            detail_2.metric("Rank", int(selected_row["rank"]))
            detail_3.metric("Skor Akhir", f"{selected_row['final_score']:.6f}")
            detail_4.metric(
                "Status Kestabilan",
                stability_badge(selected_row["stability_status"]),
            )

            st.subheader("🔎 Top 3 Issue & Halaman Terdampak")
            issue_detail = build_issue_detail(
                priority_row=selected_row,
                audit=audit_findings,
            )

            st.dataframe(
                issue_detail,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Prioritas": st.column_config.NumberColumn(format="%d"),
                    "Jumlah Temuan": st.column_config.NumberColumn(format="%d"),
                    "Affected Nodes": st.column_config.NumberColumn(format="%d"),
                },
            )

            st.caption(
                "Halaman terdampak diambil dari audit_findings.csv dan disusun per WCAG / SC yang muncul pada ranking website yang dipilih."
            )

        with baseline_tab:
            baseline_table = filtered[
                [
                    "website_id",
                    "rank",
                    "baseline_a_rank",
                    "baseline_b_rank",
                    "baseline_c_rank",
                    "final_score",
                ]
            ].copy()
            baseline_table = baseline_table.rename(
                columns={
                    "website_id": "Website ID",
                    "rank": "Rank SAW",
                    "baseline_a_rank": "Baseline A",
                    "baseline_b_rank": "Baseline B",
                    "baseline_c_rank": "Baseline C",
                    "final_score": "Skor Akhir",
                }
            )
            st.dataframe(
                baseline_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Rank SAW": st.column_config.NumberColumn(format="%d"),
                    "Baseline A": st.column_config.NumberColumn(format="%d"),
                    "Baseline B": st.column_config.NumberColumn(format="%d"),
                    "Baseline C": st.column_config.NumberColumn(format="%d"),
                    "Skor Akhir": st.column_config.NumberColumn(format="%.6f"),
                },
            )

            st.info(
                "Baseline A = jumlah temuan relevan mentah, Baseline B = technical_score saja, Baseline C = demographic_score saja."
            )

with methodology_tab:
    st.header("Metodologi")
    st.markdown(
        """
        Model menggunakan **Simple Additive Weighting (SAW)** untuk menggabungkan
        skor teknis aksesibilitas dan skor demografis yang telah dinormalisasi.

        - **S1 — Technical Dominant:** 0,7 skor teknis + 0,3 skor demografis.
        - **S2 — Balanced:** 0,5 skor teknis + 0,5 skor demografis.
        - **S3 — Demographic Sensitive:** 0,3 skor teknis + 0,7 skor demografis.

        Status kestabilan dihitung dari rentang ranking website lintas skenario bobot.

        - **Stabil:** rentang ranking <= 3.
        - **Sensitif terhadap Bobot:** rentang ranking > 3.
        """
    )

    st.header("Batasan Model")
    st.markdown(
        """
        - Audit aksesibilitas berasal dari pengujian otomatis menggunakan
          **axe-core**, sehingga tidak mewakili audit kepatuhan WCAG secara penuh.
        - Model menggunakan **data sekunder** dan tidak mengukur pengalaman aktual
          pengguna disabilitas pada setiap website.
        - Penelitian tidak menggunakan responden maupun panel ahli eksternal.
        - Ranking merupakan alat bantu prioritas, bukan keputusan final yang wajib
          diikuti oleh pengelola website.
        - Kategori yang tidak tersedia pada dataset hasil freeze tidak dihitung
          atau dibuat secara sintetis oleh dashboard.
        """
    )

    st.header("Versi & Checksum Dataset")
    checksum_table = pd.DataFrame(
        [
            {
                "Dataset": "priority_results.csv",
                "Versi": APP_VERSION,
                "SHA-256": priority_checksum,
            },
            {
                "Dataset": "audit_findings.csv",
                "Versi": APP_VERSION,
                "SHA-256": audit_checksum,
            },
        ]
    )
    st.dataframe(
        checksum_table,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Aplikasi hanya membaca kedua dataset tersebut dan tidak menulis "
        "atau mengubah isi file sumber."
    )
