

# -------------------- Imports --------------------

import calendar
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import re

from utils.bootstrap import ensure_bootstrap

ctx = ensure_bootstrap(page_title="Home — iSOFT Dashboards", page_icon="🏠")
# Top developer banner (page header)
st.markdown(
    """
    <div style="text-align:center; margin-bottom:1rem;">
        <small style="color:grey; font-size:0.9rem;">Developed by</small><br>
        <img src="https://b3660930.smushcdn.com/3660930/wp-content/uploads/2024/03/iSOFT-Logo-Tag-New-e1721176700423.png?lossy=2&strip=1&webp=1"
             alt="iSOFT ANZ" width="180">
    </div>
    """,
    unsafe_allow_html=True
)
# -------------------- Helpers --------------------
@st.cache_data(show_spinner=False)
def _load_csv(file) -> pd.DataFrame:
    """
    Load uploaded file reliably.
    - If CSV: try multiple encodings (utf-8-sig, utf-8, cp1252, latin-1)
      and let pandas infer the delimiter.
    - If Excel: use openpyxl explicitly.
    - Always rewind the file pointer before each attempt.
    - Return raw text (header=None) so we can detect the true header later.
    """
    name = getattr(file, "name", "").lower()

    if name.endswith(".csv"):
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            file.seek(0)
            try:
                return pd.read_csv(
                    file,
                    header=None,
                    dtype=str,
                    engine="python",
                    encoding=enc,
                    sep=None,           # infer delimiter
                    on_bad_lines="skip" # tolerate odd rows
                )
            except UnicodeDecodeError:
                continue
        # last resort
        file.seek(0)
        return pd.read_csv(
            file,
            header=None,
            dtype=str,
            engine="python",
            encoding="latin-1",
            sep=None,
            on_bad_lines="skip"
        )

    # Excel path
    file.seek(0)
    return pd.read_excel(file, header=None, dtype=str, engine="openpyxl")


def _standardise_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Detect the header row inside report exports and map to Date/Description/Debit(AUD)/Type."""
    import re

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(s or "").strip().lower())

    # ---- 1) Find the real header row (look for Date + Description + Amount-like) ----
    header_idx = 0
    scan_limit = min(len(raw), 60)
    for i in range(scan_limit):
        row = raw.iloc[i].astype(str).tolist()
        low = [_norm(x) for x in row]
        if ("date" in low) and ({"description", "vendor", "details"} & set(low)) and (
            {"debitaud", "amount", "amt", "value", "debit"} & set(low)
        ):
            header_idx = i
            break

    # ---- 2) Rebuild DataFrame with detected header ----
    header = raw.iloc[header_idx].tolist()
    df = raw.iloc[header_idx + 1:].copy()
    df.columns = header
    df = df.replace({"": pd.NA, "nan": pd.NA}).dropna(how="all")

    # ---- 3) Map varying column names to required ones ----
    cols_norm = {c: _norm(c) for c in df.columns}
    def _find(*cands):
        cand_norm = {_norm(x) for x in cands}
        for orig, n in cols_norm.items():
            if n in cand_norm:
                return orig
        return None

    date_col = _find("Date", "Txn Date", "Transaction Date")
    desc_col = _find("Description", "Vendor", "Details", "Narration")
    # prefer 'Debit (AUD)' if present
    amt_col  = _find("Debit (AUD)", "Debit(AUD)", "Debit AUD", "Amount", "Amt", "Value", "Debit")
    type_col = _find("Type", "Type of Subs expenses", "Subscription Type", "Subs Type",
                     "Category", "Categories")

    missing = []
    if date_col is None: missing.append("Date")
    if desc_col is None: missing.append("Description")
    if amt_col  is None: missing.append("Debit(AUD)")

    if missing:
        st.error(f"Missing required columns: {', '.join(missing)}.")
        st.stop()

    out = pd.DataFrame({
            "Date": df[date_col],
            "Description": df[desc_col],
            # clean amount text; _prepare will to_numeric+abs
            "Debit(AUD)": (
                df[amt_col].astype(str)
                .str.replace(r"[,$()\s]", "", regex=True)
                .str.replace("\u00a0", "", regex=False)
            ),
            "Type": (
                df[type_col].fillna("No Category Found") if type_col is not None
                else "No Category Found"
            ),
        })
    return out




# ---- Category normalisation ----
TYPE_CANON_DICT = {
    "tech": "Tech",
    "technology": "Tech",
    "it": "Tech",
    "software": "Tech",
    "saas": "Tech",
    "cloud": "Tech",
    "marketing": "Marketing",
    "mkt": "Marketing",
    "green": "Green",
    "sustainability": "Green",
    "other": "Others",
    "others": "Others",
}

def _canon_type(val: str) -> str:
    s = str(val or "").strip().lower()
    # strip punctuation / multiple spaces
    s = re.sub(r"[^a-z]+", " ", s).strip()
    # fast dictionary hits
    if s in TYPE_CANON_DICT:
        return TYPE_CANON_DICT[s]
    # heuristic contains checks
    if s.startswith("tech") or "technolog" in s:
        return "Tech"
    if "market" in s:
        return "Marketing"
    if "green" in s or "sustain" in s:
        return "Green"
    if "other" in s:
        return "Others"
    # title-case fallback (so custom categories still look nice if user adds new types)
    return s.title() if s else "Others"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- keep only expenditure ---
    if "Source" in df.columns:
        df = df[df["Source"].astype(str).str.strip().str.lower() == "spend money"]

    def _parse_date(x):
        if pd.isna(x): return pd.NaT
        if isinstance(x, (pd.Timestamp, datetime)): return pd.to_datetime(x)
        return pd.to_datetime(str(x), dayfirst=True, errors='coerce')
    # keep only expenditure rows
    if "Source" in df.columns:
        df = df[df["Source"].astype(str).str.strip().str.lower() == "spend money"]

    # ... your _parse_date then:
    df["Date"] = df["Date"].apply(_parse_date)
    df = df.dropna(subset=["Date"])

    # DO NOT .abs(); keep sign and drop non-positive amounts
    df["Debit(AUD)"] = pd.to_numeric(df["Debit(AUD)"], errors="coerce")
    df = df[df["Debit(AUD)"] > 0]


    df["Date"] = df["Date"].apply(_parse_date)
    df = df.dropna(subset=["Date"])

    df["Type"] = df["Type"].apply(_canon_type)

    # --- clean vendor names (e.g. "Airwallex Expenses - ..." -> "Airwallex Expenses") ---
    def _clean_vendor(v: str) -> str:
        if pd.isna(v): 
            return "Unknown"
        v = str(v).strip()
        if v.lower().startswith("airwallex expenses"):
            return "Airwallex Expenses"
        return v.split("-")[0].strip()  # take before dash if present
    df["Vendor"] = df["Description"].apply(_clean_vendor)

    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Month Name"] = df["Month"].apply(lambda m: calendar.month_abbr[m] if pd.notna(m) else None)
    df["Month-Year"] = df["Date"].dt.to_period("M").astype(str)

    return df



def _kpi_tiles(df: pd.DataFrame):
    total_spend = df["Debit(AUD)"].sum()
    months_present = df["Month-Year"].nunique()
    avg_monthly = total_spend / months_present if months_present else 0.0
    active_subs = df["Vendor"].nunique()

    top_vendor_row = (
        df.groupby("Vendor", as_index=False)["Debit(AUD)"].sum()
          .sort_values("Debit(AUD)", ascending=False)
          .head(1)
    )
    top_vendor = top_vendor_row["Vendor"].iloc[0] if not top_vendor_row.empty else "—"
    top_vendor_amt = top_vendor_row["Debit(AUD)"].iloc[0] if not top_vendor_row.empty else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Spend", f"${total_spend:,.2f}")
    c2.metric("Avg Monthly Spend", f"${avg_monthly:,.2f}")
    c3.metric("Top Vendor", f"{top_vendor}", delta=f"${top_vendor_amt:,.2f}")


COLOR_MAP = {
    "Tech": "#ADA3A3",   # Plotly classic grey
    "Marketing": "#EF553B",  # Plotly classic red
    "Others": "#0074D9",     # Plotly classic blue
}



MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# -------------------- Upload & Filters --------------------
st.sidebar.header("Upload & Filters")
uploaded = st.sidebar.file_uploader(
    "Upload subscriptions CSV/Excel",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=False,
)

if not uploaded:
    st.info(
        "Upload a CSV/Excel with columns: Date, Description, Debit(AUD), Type of Subs expenses.\n"
        "Example: 02 Jan 2025, Microsoft, 691.84, Others"
    )
    st.stop()

raw = _load_csv(uploaded)
df = _standardise_columns(raw)
df = _prepare(df)

# Year filter
all_years = sorted(df["Year"].dropna().unique().tolist())
sel_years = st.sidebar.multiselect("Year", options=["ALL"] + all_years, default=["ALL"])
years = all_years if ("ALL" in sel_years or not sel_years) else sel_years

# Month (name) filter
sel_months_lbl = st.sidebar.multiselect(
    "Month", options=["ALL"] + MONTH_ORDER, default=["ALL"]
)
months = MONTH_ORDER if ("ALL" in sel_months_lbl or not sel_months_lbl) else sel_months_lbl

# Type filter
all_types = sorted(df["Type"].dropna().unique().tolist())
sel_types = st.sidebar.multiselect("Type of Subscription", options=["ALL"] + all_types, default=["ALL"])
types = all_types if ("ALL" in sel_types or not sel_types) else sel_types

# Vendor filter
all_vendors = sorted(df["Vendor"].dropna().unique().tolist())
sel_vendors = st.sidebar.multiselect("Vendors", options=["ALL"] + all_vendors, default=["ALL"])
vendors = all_vendors if ("ALL" in sel_vendors or not sel_vendors) else sel_vendors

# Apply filters
filtered = df[
    df["Year"].isin(years)
    & df["Month Name"].isin(months)
    & df["Type"].isin(types)
    & df["Vendor"].isin(vendors)
].copy()

# -------------------- Title & KPIs --------------------
st.title("Subscription Dashboard")

_kpi_tiles(filtered)


st.divider()
# -------------------- Spend Over Time (Month Name axis) --------------------
st.subheader("Spend Over Time")

show_ot_table = st.toggle("Show Over-Time Data", value=False, key="ot_table")

view_mode = st.segmented_control("View", options=["Overall", "Facet by Type"], default="Overall")

# Aggregate by Month Name (across years); enforce month ordering
by_month = filtered.groupby("Month Name", as_index=False)["Debit(AUD)"].sum()
by_month["Month Name"] = pd.Categorical(by_month["Month Name"], categories=MONTH_ORDER, ordered=True)
by_month = by_month.sort_values("Month Name")

if view_mode == "Overall":
    fig_line = px.line(
        by_month,
        x="Month Name",
        y="Debit(AUD)",
        markers=True,
        title="Overall Subscription Spend (by Month)",
        labels={"Month Name": "Month", "Debit(AUD)": "Spend (AUD)"},
        category_orders={"Month Name": MONTH_ORDER},
    )
else:
    by_month_type = filtered.groupby(["Month Name", "Type"], as_index=False)["Debit(AUD)"].sum()
    by_month_type["Month Name"] = pd.Categorical(by_month_type["Month Name"], categories=MONTH_ORDER, ordered=True)
    by_month_type = by_month_type.sort_values(["Month Name", "Type"])
    fig_line = px.line(
        by_month_type,
        x="Month Name",
        y="Debit(AUD)",
        color="Type",
        facet_col="Type",
        facet_col_wrap=2,
        markers=True,
        title="Subscription Spend by Type (by Month)",
        labels={"Month Name": "Month", "Debit(AUD)": "Spend (AUD)"},
        category_orders={"Month Name": MONTH_ORDER},
        color_discrete_map=COLOR_MAP,
    )
if show_ot_table:
    st.dataframe(by_month if view_mode == "Overall" else by_month_type) 

st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# -------------------- Monthly Stacked Bar (stacked on Type) --------------------
st.subheader("Monthly Spend by Type")
monthly_type = filtered.groupby(["Month Name", "Type"], as_index=False)["Debit(AUD)"].sum()
monthly_type["Month Name"] = pd.Categorical(monthly_type["Month Name"], categories=MONTH_ORDER, ordered=True)
monthly_type = monthly_type.sort_values(["Month Name", "Type"])


show_stack_table = st.toggle("Show Monthly Type Data", value=False, key="stack_table")

fig_stack = px.bar(
    monthly_type,
    x="Month Name",
    y="Debit(AUD)",
    color="Type",
    title="Stacked Monthly Subscription Spend by Type",
    labels={"Month Name": "Month", "Debit(AUD)": "Spend (AUD)"},
    category_orders={"Month Name": MONTH_ORDER},
    color_discrete_map=COLOR_MAP,
)
st.plotly_chart(fig_stack, use_container_width=True)

if show_stack_table:
    st.dataframe(monthly_type)

st.divider()

# -------------------- Vendor Spend (Top N) --------------------
st.subheader("Vendors by Spend")

# ---- Vendors Summary (Top/Bottom + Custom Pick) ----
vendor_sum = (
    filtered.groupby("Vendor", as_index=False)["Debit(AUD)"].sum()
            .sort_values("Debit(AUD)", ascending=False)
)

tab1, tab2 = st.tabs(["Top / Bottom", "Choose Vendors"])

with tab1:
    c1, c2, c3 = st.columns([1.2, 1, 3])
    with c1:
        top_n = st.number_input("Top N", min_value=0, max_value=50, value=min(10, len(vendor_sum)))
    with c2:
        bottom_n = st.number_input("Bottom N", min_value=0, max_value=50, value=0)

    # Build selection
    top_df = vendor_sum.head(int(top_n))
    bottom_df = vendor_sum.tail(int(bottom_n))
    sel_df = pd.concat([top_df, bottom_df]).drop_duplicates(subset=["Vendor"])  # avoid dupes if overlap

    title = f"Top {int(top_n)}" + (f" & Bottom {int(bottom_n)}" if bottom_n else "") + " Vendors by Spend"

    fig_vendor_tb = px.bar(
        sel_df,
        x="Vendor",
        y="Debit(AUD)",
        title=title,
        labels={"Debit(AUD)": "Spend (AUD)"},
        color="Vendor",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_vendor_tb.update_xaxes(tickangle=-30)
    st.plotly_chart(fig_vendor_tb, use_container_width=True)

with tab2:
    options = vendor_sum["Vendor"].tolist()
    default_pick = options[: min(10, len(options))]
    picks = st.multiselect("Select vendors", options=options, default=default_pick, key="vendor_custom_pick")

    pick_df = vendor_sum[vendor_sum["Vendor"].isin(picks)]
    fig_vendor_pick = px.bar(
        pick_df,
        x="Vendor",
        y="Debit(AUD)",
        title="Selected Vendors by Spend",
        labels={"Debit(AUD)": "Spend (AUD)"},
        color="Vendor",
       color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_vendor_pick.update_xaxes(tickangle=-30)
    st.plotly_chart(fig_vendor_pick, use_container_width=True)

# Optional table
if st.toggle("Show Vendor Summary", value=False, key="vendor_table"):
    st.dataframe(vendor_sum)

st.divider()

# ---- Monthly Vendor Lines (Top/Bottom + Custom Pick) ----
st.subheader("Monthly Vendor Spend (Line)")

if filtered.empty:
    st.info("No data in current filter.")
else:
    # Monthly aggregation ONLY
    vm = (
        filtered.assign(Period=filtered["Date"].dt.to_period("M"))
                .groupby(["Vendor", "Period"], as_index=False)["Debit(AUD)"].sum()
                .sort_values(["Vendor", "Period"])
    )
    # MoM % per vendor
    vm["MoM_Pct"] = vm.groupby("Vendor")["Debit(AUD)"].pct_change().fillna(0.0)
    vm["Month Name"] = vm["Period"].dt.strftime("%b")   # Jan, Feb, Mar
    vm["Year"] = vm["Period"].dt.year
    vm["Month-Year"] = vm["Period"].dt.strftime("%b %Y")  # e.g. Jan 2025
    # replace your month_order line with this:
    month_order = vm.sort_values("Period")["Month-Year"].unique().tolist()

    # Optional table
    if st.toggle("Show Monthly Vendor Data", value=False, key="vendor_line_table"):
        st.dataframe(vm)  
    # rank vendors by latest month spend
    latest = vm["Period"].max()
    latest_rank = vm[vm["Period"] == latest].sort_values("Debit(AUD)", ascending=False)

    tab1, tab2 = st.tabs(["Top / Bottom", "Choose Vendors"])

    # ---------- Tab 1: Top / Bottom ----------
    with tab1:
        max_n = int(latest_rank.shape[0])
        c1, c2, _ = st.columns([1.2, 1, 3])
        with c1:
            top_n = st.number_input("Top N", min_value=0, max_value=max_n, value=min(10, max_n))
        with c2:
            bottom_n = st.number_input("Bottom N", min_value=0, max_value=max_n, value=0)

        top_vendors = latest_rank.head(int(top_n))["Vendor"].tolist()
        bottom_vendors = latest_rank.tail(int(bottom_n))["Vendor"].tolist() if bottom_n else []
        sel_vendors = list(dict.fromkeys(top_vendors + bottom_vendors))  # de-dupe, keep order

        vm_sel = vm[vm["Vendor"].isin(sel_vendors)].copy()


        fig_tb = px.line(
            vm_sel,
            x="Month-Year",
            y="Debit(AUD)",
            color="Vendor",
            markers=True,
            labels={"Month-Year": "Month", "Debit(AUD)": "Spend (AUD)"},
            title="Monthly Spend by Vendor",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            category_orders={"Month-Year": month_order},
            custom_data=["MoM_Pct"],
        )

        fig_tb.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Month=%{x}"
                          "<br>Spend=$%{y:,.2f}<br>MoM=%{customdata[0]:.1%}"
                          "<extra></extra>"
        )
        st.plotly_chart(fig_tb, use_container_width=True)

    # ---------- Tab 2: Choose Vendors ----------
    with tab2:
        all_vendors = latest_rank["Vendor"].tolist()
        default_pick = all_vendors[: min(10, len(all_vendors))]  # default up to 10
        picks = st.multiselect("Select vendors", options=all_vendors, default=default_pick, key="vendor_line_pick")

        vm_pick = vm[vm["Vendor"].isin(picks)].copy()

        fig_pick = px.line(
            vm_pick,
            x="Month-Year",
            y="Debit(AUD)",
            color="Vendor",
            markers=True,
            labels={"Month": "Month", "Debit(AUD)": "Spend (AUD)"},
            title="Monthly Spend by Selected Vendors",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            category_orders={"Month-Year": month_order},
            custom_data=["MoM_Pct"],
        )
        fig_pick.update_traces(
            hovertemplate="<b>%{fullData.name}</b><br>Month=%{x}"
                          "<br>Spend=$%{y:,.2f}<br>MoM=%{customdata[0]:.1%}"
                          "<extra></extra>"
        )
        st.plotly_chart(fig_pick, use_container_width=True)
         

