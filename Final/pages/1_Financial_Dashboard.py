
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --------------- App setup Initial --------------
st.set_page_config(page_title="Financial Dashboard", page_icon=":bar_chart:", layout="wide")
color_theme = px.colors.qualitative.Pastel
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
st.markdown("<h1 style='text-align: center;'>Financial Dashboard</h1>", unsafe_allow_html=True)

# --- FAQ (collapsed expander at top) ---
def render_faq_expander():
    import streamlit as st

    faqs = [
        ("How do I upload my CSV files?",
         "- Upload **Balance Activity Report (BAR) CSV first**, then **Expenses CSV** from the sidebar.\n"
         "- Both files are required.\n"
         "- After upload, the app builds a **unified dataset** you can preview/download."),
        ("I see 'NaN' — what does that mean?",
         "- **NaN** = missing/empty value in the source CSV.\n"
         "- Check **Unified Data → Preview** for rows/columns with NaNs.\n"
         "- Fix in the CSV if needed and re-upload."),
        ("How are PAYOUT and DEPOSIT handled?",
         "- **PAYOUT** → Category = **Transfers**; treated as **debit** (money out).\n"
         "- **DEPOSIT** → Category = **No Category**; treated as **credit** (money in) and **excluded** from spend pies."),
        ("Who is the 'User' for payouts?",
         "- We extract the name **after 'to'** in the description.\n"
         "  e.g., *'payout to Mr James Brook'* → **User = James Brook**."),
        ("What is Total Expenditure?",
         "- Sum of **Debit Net Amount** for **CARD**, **PAYOUT**, **ADJUSTMENT**.\n"
         "- **DEPOSIT** and card refunds are credits and not counted in expenditure."),
        ("Where can I verify or export the merged data?",
         "- Open **Unified Data** to *Preview*, see a *Summary*, or **Download** `unified_transactions.csv`."),
        ("Why might a BAR transaction be missing from the unified file?",
         "- Join is on **Transaction Id**. If an ID is blank, mismatched, or absent in the other file, it won’t match.\n"
         "- Check both source files or use *Missing Transaction Checker*."),
        ("What is the 'Incomplete' category?",
         "- If a **CARD** transaction has no category and the Expense Status = 'Incomplete',\n"
         "  the dashboard assigns **Category = Incomplete**.\n"
         "- This highlights expenses that need Finance follow-up."),
        ("Why do I see 'Adjustments' as a User?",
         "- **ADJUSTMENT** transactions are manual corrections in Airwallex.\n"
         "- For clarity, the dashboard groups them under **User = Adjustments**\n"
         "  and **Category = Air wallex Expense**."),
        ("Why might a user name appear twice?",
         "- Sometimes names differ slightly due to extra spaces or hidden characters.\n"
         "- Example: *'Christine  Thomas'* (double space) vs *'Christine Thomas'.*\n"
         "- We now clean most cases, but if you see duplicates, check the source file formatting."),
    ]
    with st.expander("❓ FAQ — click to open", expanded=False):
        # Quick dropdown for one answer
        questions = [q for q, _ in faqs]
        choice = st.selectbox("Quick question", options=questions, index=0)
        st.markdown(dict(faqs)[choice])

        st.divider()
        st.caption("All questions & answers")
        # Full list
        for q, a in faqs:
            st.markdown(f"**{q}**")
            st.markdown(a)
            st.markdown("---")
render_faq_expander()


# Sidebar file upload
bal_file = st.sidebar.file_uploader("Upload Balance Activity Report CSV", type="csv")
exp_file = st.sidebar.file_uploader("Upload Expenses CSV", type="csv")

# Guard: show UI first, don't read until something is uploaded
if not exp_file and not bal_file:
    st.info("📁 Upload one or both files to begin.")
    st.stop()
elif not exp_file or not bal_file:
    st.error("❌ Please upload both files to proceed.")
    st.stop()

balance_file = pd.read_csv(bal_file, encoding="utf-8-sig")
expense_file = pd.read_csv(exp_file, encoding="utf-8-sig")

# -------- BALANCE (balance_file) USING FINANCIAL TRANSACTION TYPE --------
def _pick(df, names):
    m = {c.lower().strip(): c for c in df.columns}
    for n in names:
        col = m.get(n.lower())
        if col in df.columns:
            return col
    return None

fin_type_col = _pick(balance_file, ["Financial Transaction Type"])
time_col     = _pick(balance_file, ["Time", "Created At"])
desc_col     = _pick(balance_file, ["Description", "Reference"])
txn_col      = _pick(balance_file, ["Transaction Id", "Request Id"])
amount_col   = _pick(balance_file, ["Amount"])

# Upper-case the FIN type and filter required four
ft = balance_file[fin_type_col].astype(str).str.strip().str.upper()
mask = ft.isin(["DEPOSIT", "CARD_REFUND", "PAYOUT", "ADJUSTMENT"])
bf = balance_file.loc[mask].copy()
bf["Type"] = ft.loc[bf.index]  # standardize to 'Type' column in final DF

# Amount
# Amount (remove commas, currency symbols, spaces, etc. before numeric)
bf["Amount"] = (
    bf[amount_col]
      .astype(str)
      .str.replace(r"[^\d.\-]", "", regex=True)  # drops commas, $, AUD, spaces
      .pipe(pd.to_numeric, errors="coerce")
      .fillna(0.0)
)


# Employee (optional, keep if you use it elsewhere)
bf["Employee"] = (
    bf[desc_col].astype(str)
      .str.extract(r"\bto\s+(.+?)(?=[,;()]+|$)", expand=False)
      .str.strip()
)

# Expense category mapping (in BALANCE section)
bf["Expense category"] = np.select(
    [bf["Type"].eq("PAYOUT"), bf["Type"].eq("ADJUSTMENT")],
    ["Transfers", "Air wallex Expense"],   # <-- ADJUSTMENT label here
    default=pd.NA
)

# Time + parts
bf["Time"]  = pd.to_datetime(bf[time_col].astype(str), errors="coerce", utc=True).dt.tz_convert(None)
bf["Date"]  = bf["Time"].dt.date
bf["Month"] = bf["Time"].dt.strftime("%b").str.upper()
bf["Year"]  = bf["Time"].dt.year.astype("Int64").astype(str)

# Your requested Debit/Credit convention:
# - DEPOSIT, CARD_REFUND -> treat as DEBIT (per your instruction)
# Debit = CARD_PURCHASE, PAYOUT, ADJUSTMENT
# Credit = DEPOSIT, CARD_REFUND
bf["Debit Net Amount"]  = np.where(bf["Type"].isin(["PAYOUT", "ADJUSTMENT"]), bf["Amount"], 0.0)
bf["Credit Net Amount"] = np.where(bf["Type"].isin(["DEPOSIT", "CARD_REFUND"]), bf["Amount"], 0.0)


balance_filtered = bf[[
    txn_col, "Type", "Employee", "Amount", "Expense category",
    "Time", "Date", "Month", "Year", "Debit Net Amount", "Credit Net Amount"
]].rename(columns={txn_col: "Transaction Id"})
balance_filtered["Expense status"] = np.nan   # balance report doesn’t have this



# --- build from Expense file ---
ef = expense_file.copy()

# Parse time
ef["Time"] = pd.to_datetime(ef["Transaction timestamp UTC"], errors="coerce", utc=True).dt.tz_convert(None)
ef["Date"] = ef["Time"].dt.date
ef["Month"] = ef["Time"].dt.strftime("%b").str.upper()
ef["Year"] = ef["Time"].dt.year.astype("Int64").astype(str)

# Employee: take just the first name before comma
ef["Employee"] = ef["Employee(s)"].astype(str).str.split(",").str[0].str.strip()

ef["Amount"] = (
    ef["Billing amount"]
      .astype(str)
      .str.replace(r"[^\d.\-]", "", regex=True)
      .pipe(pd.to_numeric, errors="coerce")
      .fillna(0.0)
)

# Expense category
ef["Expense category"] = ef["Expense category"].astype(str).str.strip()
ef["Expense status"]   = ef.get("Expense status")
# Type = CARD for all
ef["Type"] = "CARD"

# --- final output (include the two columns) ---
expense_filtered = ef[[
    "Time", "Date", "Month", "Year",
    "Employee",
    "Transaction Id",
    "Amount",
    "Expense category",
    "Expense status",           
    "Type"
]].copy()

# Add debit/credit columns
expense_filtered["Debit Net Amount"]  = expense_filtered["Amount"]
expense_filtered["Credit Net Amount"] = 0.0
# Merge the two DataFrames (same column names)
final_dataframe = pd.concat([expense_filtered, balance_filtered], ignore_index=True)
# --- standardise columns coming from expense/balance merges ---
df = final_dataframe.copy()

# Type normalized
type_upper = df["Type"].astype(str).str.strip().str.upper()
df["Type"] = type_upper
# After df["User"] = ...
df.loc[df["Type"] == "ADJUSTMENT", "User"] = "Adjustment"

# Standardise people/category column names to what the dashboard expects
# (balance_filtered has Employee; expenses had Employee; dashboard uses 'User' + 'Category')
df["User"] = df["Employee"].astype(str).str.replace(r"\s+", " ", regex=True).str.replace(u"\xa0", " ", regex=False).str.strip().str.title()
df["Category"] = df["Expense category"].astype(str).str.strip()
# --- enforce rules for ADJUSTMENT (after User/Category are set) ---
adj_mask = df["Type"].astype(str).str.upper().eq("ADJUSTMENT")
df.loc[adj_mask, "User"] = "Adjustments"              # plural, as requested
df.loc[adj_mask, "Category"] = "Air wallex Expense"   # exact label you asked for
card_mask = type_upper.eq("CARD")
# take category only from expense file for CARD rows
df.loc[card_mask, "Category"] = (
    df.loc[card_mask, "Expense category"]
      .astype(str).str.strip()
      .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
)

# Incomplete rule (CARD only)
incomplete_mask = (
    card_mask
    & df["Category"].isna()
    & df.get("Expense status", "").astype(str).str.strip().str.lower().eq("incomplete"))
df.loc[incomplete_mask, "Category"] = "Incomplete"


# Time fields
df["Time"] = pd.to_datetime(df["Time"], errors="coerce")
df["Month"] = df["Time"].dt.strftime("%b").str.upper()
df["Year"] = df["Time"].dt.year.astype("Int64").astype(str)
df["MonthYear"] = pd.to_datetime(df["Year"] + "-" + df["Month"] + "-01", format="%Y-%b-%d", errors="coerce")

# Ensure numerics & don’t overwrite precomputed debit/credit
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
df["Debit Net Amount"]  = pd.to_numeric(df.get("Debit Net Amount", 0.0),  errors="coerce").fillna(0.0)
df["Credit Net Amount"] = pd.to_numeric(df.get("Credit Net Amount", 0.0), errors="coerce").fillna(0.0)

# Spend-only amount for pies/charts = debits
df["Final_Amount"] = df["Debit Net Amount"]

# (Optional safety fallback — only used if a row somehow has both 0s)
t_upper = df["Type"].astype(str).str.upper()
missing_mask = (df["Debit Net Amount"] == 0) & (df["Credit Net Amount"] == 0)
if missing_mask.any():
    debit_types  = {"CARD", "PAYOUT", "ADJUSTMENT"}
    credit_types = {"DEPOSIT", "CARD_REFUND"}
    df.loc[missing_mask & t_upper.isin(debit_types),  "Debit Net Amount"]  = df.loc[missing_mask & t_upper.isin(debit_types),  "Amount"]
    df.loc[missing_mask & t_upper.isin(credit_types), "Credit Net Amount"] = df.loc[missing_mask & t_upper.isin(credit_types), "Amount"]


import io

st.subheader("Unified Data")
with st.expander("Open preview / summary / download", expanded=False):
    tab1, tab2, tab3 = st.tabs(["Preview", "Summary", "Download"])

    with tab1:
        df_preview = df.sort_values("Time", na_position="last")
        st.dataframe(df_preview.head(200), use_container_width=True, height=420)

    with tab2:
        colA, colB, colC = st.columns(3)
        colA.metric("Total Debits",  f"${df['Debit Net Amount'].sum():,.2f}")
        colB.metric("Total Credits", f"${df['Credit Net Amount'].sum():,.2f}")
        colC.metric("Net", f"${(df['Debit Net Amount'].sum() - df['Credit Net Amount'].sum()):,.2f}")

        st.write("Counts by Type")
        st.dataframe(
            df['Type'].value_counts().rename_axis('Type').reset_index(name='Count'),
            use_container_width=True
        )

        st.write("Sums by Type")
        st.dataframe(
            df.groupby('Type')[['Amount','Debit Net Amount','Credit Net Amount']].sum().round(2).reset_index(),
            use_container_width=True
        )

    with tab3:
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Download unified CSV",
            data=csv_bytes,
            file_name="unified_transactions.csv",
            mime="text/csv"
        )



# ------------------ Filters ------------------
st.sidebar.header("Filter Transactions")
all_months = sorted(df['Month'].dropna().unique())
all_years = sorted(df['Year'].dropna().unique())
selected_months = st.sidebar.multiselect("Select Months", ["ALL"] + all_months, default=["ALL"])
selected_years = st.sidebar.multiselect("Select Years", ["ALL"] + all_years, default=["ALL"])
selected_months = all_months if "ALL" in selected_months else selected_months
selected_years = all_years if "ALL" in selected_years else selected_years

# Transaction Type selector
all_types = sorted(df['Type'].dropna().unique())
selected_types = st.sidebar.multiselect("Select Transaction Types", ["ALL"] + all_types, default=["ALL"])
selected_types = all_types if "ALL" in selected_types or not selected_types else selected_types

# Base filter
base_filtered = df[
    df['Month'].isin(selected_months) &
    df['Year'].isin(selected_years) &
    df['Type'].isin(selected_types)
].copy()

# User filter (+ Sales Team shortcut)
base_filtered['User'] = base_filtered['User'].astype(str).str.strip().str.title()
unique_users = sorted(base_filtered['User'].dropna().unique())
user_options = ["All", "Sales Team"] + unique_users
selected_users = st.sidebar.multiselect("Select User(s)", user_options, default="All")

sales_team_keywords = ['Mohit', 'Adarsh', 'Praveen', 'Shailabh', 'Ameet', 'Jas', 'Hemant']

if "All" in selected_users or not selected_users:
    filtered_df = base_filtered.copy()
elif "Sales Team" in selected_users:
    sales_matches = [u for u in unique_users if any(k.lower() in u.lower() for k in sales_team_keywords)]
    explicit = [u for u in selected_users if u not in ("All", "Sales Team")]
    final_users = set(sales_matches) | set(explicit)
    filtered_df = base_filtered[base_filtered['User'].isin(final_users)].copy()
else:
    filtered_df = base_filtered[base_filtered['User'].isin(selected_users)].copy()

# Month label ordering
filtered_df['MonthLabel'] = filtered_df['MonthYear'].dt.strftime('%b %Y')
sorted_months = filtered_df[['MonthYear', 'MonthLabel']].drop_duplicates().sort_values('MonthYear')
month_order = sorted_months['MonthLabel'].tolist()
filtered_df['MonthLabel'] = pd.Categorical(filtered_df['MonthLabel'], categories=month_order, ordered=True)

# Pie-safe amount: credits for DEPOSIT, debits for CARD/PAYOUT

t_upper = filtered_df['Type'].astype(str).str.upper()
filtered_df['Final_Amount'] = np.select(
    [t_upper.eq('DEPOSIT'), t_upper.eq('CARD'), t_upper.eq('PAYOUT')],
    [filtered_df['Credit Net Amount'], filtered_df['Debit Net Amount'], filtered_df['Debit Net Amount']],
    default=filtered_df['Debit Net Amount']
)

# ------------------ Metric Tile ------------------
total_expenditure = filtered_df["Debit Net Amount"].sum()

st.metric("Total Expenditure", f"${total_expenditure:,.2f}")


# ------------------ Expenditure over time (by user) ------------------
expenditure_df = (
    filtered_df.groupby(['MonthYear', 'User'])['Debit Net Amount']
    .sum()
    .reset_index()
    .dropna()
)
expenditure_df['MonthLabel'] = expenditure_df['MonthYear'].dt.strftime('%b %Y')
sorted_months = expenditure_df[['MonthYear', 'MonthLabel']].drop_duplicates().sort_values('MonthYear')
month_order = sorted_months['MonthLabel'].tolist()
expenditure_df['MonthLabel'] = pd.Categorical(expenditure_df['MonthLabel'], categories=month_order, ordered=True)

# ------------------ Dashboard branches ------------------
if "All" in selected_users:
    # Row 1: Total Expenditure bar + Pie by User
    c1, c2 = st.columns(2)
    with c1:
        show_bar_table = st.toggle("Show Table", value=False, key="bar_table_toggle")
        total_df = expenditure_df.groupby('MonthLabel')['Debit Net Amount'].sum().reset_index()
        if show_bar_table:
            st.dataframe(total_df)
        else:
            bar_fig = px.bar(
                total_df, x='MonthLabel', y='Debit Net Amount', text='Debit Net Amount',
                title='Total Expenditure Over Time',
                labels={'MonthLabel': 'Month', 'Debit Net Amount': 'Expenditure'},
                color_discrete_sequence=['#1ABC9C']
            )
            bar_fig.update_traces(texttemplate='%{text:.2s}', textposition='outside')
            bar_fig.update_layout(xaxis_tickangle=-45, height=450)
            st.plotly_chart(bar_fig, use_container_width=True)

    with c2:
        show_pie1_table = st.toggle("Show Table", value=False, key="pie1_table_toggle")

        # Exclude deposits & refunds; keep only positive debit spend
        mask_types = ~filtered_df['Type'].astype(str).str.strip().str.upper().isin(['DEPOSIT', 'CARD_REFUND'])
        mask_amt   = filtered_df['Debit Net Amount'] > 0
        pie_source = filtered_df.loc[mask_types & mask_amt].copy()

        # (optional) hide blanks/Unknown
        pie_source['User'] = pie_source['User'].astype(str).str.strip()
        pie_source = pie_source[pie_source['User'] != ""]

        pie_df = (pie_source
                .groupby('User', as_index=False)['Debit Net Amount']
                .sum()
                .rename(columns={'Debit Net Amount': 'Total Amount'}))

        if pie_df.empty:
            st.info("No debit transactions (excluding deposits/refunds) in the current filter.")
        else:
            if show_pie1_table:
                st.dataframe(pie_df)
            else:
                pie_fig = px.pie(
                    pie_df, names='User', values='Total Amount', hole=0.4,
                    title='Total Amount by User',
                    color_discrete_sequence=color_theme
                )
                pie_fig.update_traces(textposition='inside', textinfo='percent+label', marker_line_width=0)
                st.plotly_chart(pie_fig, use_container_width=True)



    # Row 2: Debit vs Credit
    st.subheader("Debit vs Credit Over Selected Months")

    # Use our derived debit/credit columns built from your rule
    chart_data = (
        filtered_df.groupby('MonthYear')[['Debit Net Amount', 'Credit Net Amount']]
        .sum().reset_index().dropna()
    )
    chart_data['MonthLabel'] = chart_data['MonthYear'].dt.strftime('%b %y').str.upper()
    chart_data = chart_data.sort_values('MonthYear')
    chart_data['MonthLabel'] = pd.Categorical(chart_data['MonthLabel'], categories=chart_data['MonthLabel'].unique(), ordered=True)

    melted = chart_data.melt(
        id_vars='MonthLabel',
        value_vars=['Debit Net Amount', 'Credit Net Amount'],
        var_name='Type', value_name='Amount'
    )

    dc_fig = px.line(
        melted, x='MonthLabel', y='Amount', color='Type', markers=True,
        title="Debit vs Credit Over Selected Months",
        color_discrete_map={'Debit Net Amount': '#E74C3C', 'Credit Net Amount': '#2ECC71'}
    )
    dc_fig.update_layout(xaxis_title="Month", yaxis_title="Amount", legend_title="Transaction Type", height=450)
    dc_fig.update_traces(opacity=0.75)
    st.plotly_chart(dc_fig, use_container_width=True)


    st.subheader("Transaction Type Overview")

    type_counts = filtered_df['Type'].value_counts()

    # make 4 metric columns
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Deposits",      int(type_counts.get("DEPOSIT", 0)))
    c2.metric("Card",          int(type_counts.get("CARD", 0)))
    c3.metric("Payouts",       int(type_counts.get("PAYOUT", 0)))
    c4.metric("Adjustments",   int(type_counts.get("ADJUSTMENT", 0)))



    type_disp = filtered_df['Type'].astype(str).str.strip().str.title()
    show_type_table = st.toggle("Show Tables", value=False, key="type_overview_toggle")

    df_counts = (
        filtered_df.assign(TypeDisplay=type_disp)
        .groupby(['MonthYear', 'TypeDisplay'])
        .size().unstack(fill_value=0).reset_index()
    )
    df_counts['MonthLabel'] = df_counts['MonthYear'].dt.strftime('%b %Y')
    df_counts = df_counts.sort_values('MonthYear')
    df_counts['MonthLabel'] = pd.Categorical(df_counts['MonthLabel'], categories=df_counts['MonthLabel'].unique(), ordered=True)

    pie_type_df = (
        filtered_df.assign(TypeDisplay=type_disp)
        .groupby('TypeDisplay', as_index=False)['Final_Amount'].sum()
        .rename(columns={'Final_Amount': 'Total Amount'})
    )

    if show_type_table:
        st.markdown("**Monthly Transaction Type Counts Table**")
        cols = ['MonthLabel'] + [c for c in ['Card', 'Deposit', 'Payout'] if c in df_counts.columns]
        st.dataframe(df_counts[cols])
        st.markdown("**Total Amount by Type Table**")
        st.dataframe(pie_type_df)
    else:
        cc1, cc2 = st.columns(2)
        with cc1:
            area_fig = go.Figure()
            color_dict = {'Deposit': 'orange', 'Card': 'red', 'Payout': 'teal'}
            for ttype in color_dict:
                if ttype in df_counts.columns:
                    area_fig.add_trace(go.Scatter(
                        x=df_counts['MonthLabel'],
                        y=df_counts[ttype],
                        name=ttype,
                        mode='lines+markers',
                        line=dict(shape='spline', color=color_dict[ttype]),
                        stackgroup='one',
                        fill='tonexty'
                    ))
            area_fig.update_layout(
                xaxis_title='Month',
                yaxis_title='Transaction Count',
                height=450,
                hovermode='x unified',
                showlegend=True,
                title="Monthly Transaction Type Counts"
            )
            st.plotly_chart(area_fig, use_container_width=True)

        with cc2:
            pie_type_fig = px.pie(
                pie_type_df, names='TypeDisplay', values='Total Amount',
                hole=0.4, title="Total Amount by Transaction Type",
                color_discrete_sequence=color_theme
            )
            pie_type_fig.update_traces(textposition='inside', textinfo='percent+label', marker_line_width=0)
            st.plotly_chart(pie_type_fig, use_container_width=True)

    # Row 4: Category pie (expenditure only)
    st.subheader("Category-wise Expenditure Overview")

    mask = ~filtered_df['Type'].astype(str).str.strip().str.upper().isin(['DEPOSIT', 'CARD_REFUND'])
    spend_only = filtered_df.loc[mask].copy()
  


    category_df = (
        spend_only.groupby('Category', as_index=False)['Debit Net Amount']
        .sum()
        .rename(columns={'Debit Net Amount': 'Total Amount'})
    )

    show_category_table = st.toggle("Show Category Table", value=False, key="category_table_toggle")
    if show_category_table:
        st.dataframe(category_df)
    else:
        category_fig = px.pie(
            category_df, names='Category', values='Total Amount',
            title='Total Amount by Category', hole=0.4,
            color_discrete_sequence=color_theme
        )
        category_fig.update_traces(textposition='inside', textinfo='percent+label', marker_line_width=0)
        st.plotly_chart(category_fig, use_container_width=True)


else:
    # ---------------- Specific users selected ----------------
    st.subheader("Total Expenditure by User Over Time")
    expenditure_df['MonthYear'] = pd.to_datetime(expenditure_df['MonthYear'])
    expenditure_df['MonthLabel'] = expenditure_df['MonthYear'].dt.strftime('%b %Y')
    month_order_df = expenditure_df[['MonthYear', 'MonthLabel']].drop_duplicates().sort_values('MonthYear')
    month_order = month_order_df['MonthLabel'].tolist()
    expenditure_df['MonthLabel'] = pd.Categorical(expenditure_df['MonthLabel'], categories=month_order, ordered=True)

    show_bar_table2 = st.toggle("Show Table", value=False, key="bar_table_toggle2")
    if show_bar_table2:
        pivot_table = expenditure_df.pivot_table(index='MonthLabel', columns='User', values='Debit Net Amount', fill_value=0)
        st.dataframe(pivot_table)
    else:
        fig21 = px.bar(
            expenditure_df,
            x='MonthLabel',
            y='Debit Net Amount',
            color='User',
            text='Debit Net Amount',
            title='Total Expenditure by User Over Time',
            labels={'MonthLabel': 'Month', 'Debit Net Amount': 'Expenditure'},
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig21.update_traces(marker_line_color='rgba(0,0,0,0.1)', marker_line_width=1, texttemplate='%{text:.2s}', textposition='outside')
        fig21.update_layout(xaxis_tickangle=-45, height=500, yaxis_title='Total Expenditure', xaxis_title='Month',
                            uniformtext_minsize=8, uniformtext_mode='hide', barmode='stack')
        st.plotly_chart(fig21, use_container_width=True)

    # Row 2: Debit vs Credit + Pie by Type
    st.subheader("Debit vs Credit & Type Overview")
    c1, c2 = st.columns(2)
    with c1:
        show_table = st.toggle("Show Table", value=False, key="debit_credit_toggle")
        chart_data = (
            filtered_df.groupby('MonthYear')[['Debit Net Amount', 'Credit Net Amount']]
            .sum().reset_index().dropna(how='all', subset=['Debit Net Amount', 'Credit Net Amount'])
        )
        chart_data['MonthLabel'] = chart_data['MonthYear'].dt.strftime('%b %y').str.upper()
        chart_data = chart_data.sort_values('MonthYear')
        chart_data['MonthLabel'] = pd.Categorical(chart_data['MonthLabel'], categories=chart_data['MonthLabel'].unique(), ordered=True)

        if show_table:
            st.dataframe(chart_data[['MonthLabel', 'Debit Net Amount', 'Credit Net Amount']])
        else:
            melted = chart_data.melt(id_vars='MonthLabel',
                                     value_vars=['Debit Net Amount', 'Credit Net Amount'],
                                     var_name='Type', value_name='Amount')
            fig = px.line(melted, x='MonthLabel', y='Amount', color='Type', markers=True,
                          title="Debit vs Credit Over Selected Months",
                          color_discrete_map={'Debit Net Amount': '#E74C3C', 'Credit Net Amount': '#2ECC71'})
            fig.update_layout(xaxis_title="Month", yaxis_title="Amount", legend_title="Transaction Type", height=450)
            fig.update_traces(opacity=0.75)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        type_disp = filtered_df['Type'].astype(str).str.strip().str.title()
        pie_df_type = (filtered_df.assign(TypeDisplay=type_disp)
                       .groupby('TypeDisplay', as_index=False)['Final_Amount'].sum())
        pie_fig = px.pie(pie_df_type, names='TypeDisplay', values='Final_Amount',
                         title='Total Amount by Transaction Type', hole=0.4,
                         color_discrete_sequence=color_theme)
        pie_fig.update_traces(textposition='inside', textinfo='percent+label', marker_line_width=0)
        st.plotly_chart(pie_fig, use_container_width=True)

    # Row 3: Monthly Expenditure + Pie by User
    st.subheader("Monthly User Expenditure & Total Share")
    c1, c2 = st.columns(2)
    with c1:
        user_month_df = (filtered_df.groupby(['MonthYear', 'User'])['Debit Net Amount'].sum().reset_index())
        user_month_df['MonthLabel'] = user_month_df['MonthYear'].dt.strftime('%b %Y')
        user_month_df = user_month_df.sort_values('MonthYear')
        user_month_df['MonthLabel'] = pd.Categorical(user_month_df['MonthLabel'], categories=user_month_df['MonthLabel'].unique(), ordered=True)
        fig_user_exp = px.line(user_month_df, x='MonthLabel', y='Debit Net Amount',
                               color='User', markers=True, title='Monthly Expenditure by User',
                               color_discrete_sequence=color_theme)
        fig_user_exp.update_layout(height=450)
        st.plotly_chart(fig_user_exp, use_container_width=True)

    with c2:
        pie_user_df = filtered_df.groupby('User', as_index=False)['Final_Amount'].sum()
        pie_user_fig = px.pie(pie_user_df, names='User', values='Final_Amount',
                              title='Total Amount by User', hole=0.4,
                              color_discrete_sequence=color_theme)
        pie_user_fig.update_traces(textposition='inside', textinfo='percent+label', marker_line_width=0)
        st.plotly_chart(pie_user_fig, use_container_width=True)

    # Row 4: Monthly Card Transactions
    st.subheader("Card Transactions by User Over Time")
    type_counts = filtered_df['Type'].value_counts()
    c1, c2, c3,c4 = st.columns(4)
    type_counts = filtered_df['Type'].value_counts()
    c1.metric("Deposits", int(type_counts.get("DEPOSIT", 0)))
    c2.metric("Card Transactions", int(type_counts.get("CARD", 0)))
    c3.metric("Payouts", int(type_counts.get("PAYOUT", 0)))
    c4.metric("Adjustments", int(type_counts.get("ADJUSTMENT", 0)))


    c1, c2 = st.columns(2)
    card_df = filtered_df[filtered_df['Type'] == 'CARD'].copy()
    card_user_stats = (card_df.groupby(['MonthYear', 'User'])
                       .agg(Transactions=('Debit Net Amount', 'count'),
                            TotalAmount=('Debit Net Amount', 'sum'))
                       .reset_index())
    card_user_stats['MonthLabel'] = card_user_stats['MonthYear'].dt.strftime('%b %Y')
    card_user_stats = card_user_stats.sort_values('MonthYear')
    month_order = card_user_stats.drop_duplicates('MonthYear')['MonthLabel']
    card_user_stats['MonthLabel'] = pd.Categorical(card_user_stats['MonthLabel'], categories=month_order, ordered=True)

    show_bar_table3 = st.toggle("Show Table", value=False, key="card_histogram_table_toggle")
    if show_bar_table3:
        st.dataframe(card_user_stats[['MonthLabel', 'User', 'Transactions', 'TotalAmount']])
    else:
        fig = go.Figure()
        unique_users_list = list(card_user_stats['User'].unique())
        color_map = {user: color_theme[i % len(color_theme)] for i, user in enumerate(unique_users_list)}
        for user in unique_users_list:
            user_data = card_user_stats[card_user_stats['User'] == user]
            fig.add_trace(go.Bar(
                x=user_data['MonthLabel'],
                y=user_data['Transactions'],
                name=user,
                hovertemplate=(f"<b>{user}</b><br>"
                               "Transactions: %{y}<br>"
                               "Amount: $%{customdata[0]:,.2f}<extra></extra>"),
                customdata=user_data[['TotalAmount']],
                marker_color=color_map[user]
            ))
        fig.update_layout(barmode='group', title='Monthly Card Transactions by User',
                          xaxis_title='Month', yaxis_title='Number of Transactions',
                          height=550, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

    # Row 5: Category Heatmap + Pie (expenditure only)
    st.subheader("Category-wise Analysis")
    cat_user_df = (filtered_df.groupby(['User', 'Category'], as_index=False)['Debit Net Amount'].sum())
    c1, c2 = st.columns(2)
    with c1:
        show_correlation_table = st.toggle("Show Table", value=False, key="cat_heatmap_table_toggle")
        if show_correlation_table:
            st.dataframe(cat_user_df.sort_values(by='Debit Net Amount', ascending=False))
        else:
            fig = px.density_heatmap(
                cat_user_df, x='Category', y='User', z='Debit Net Amount',
                color_continuous_scale='Teal',
                title='Amount Spent by User on Each Category',
                labels={'Debit Net Amount': 'Amount Spent'}
            )
            fig.update_traces(hovertemplate='User: %{y}<br>Category: %{x}<br>Amount Spent: %{z:,.2f}<extra></extra>')
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        show_pie3_table = st.toggle("Show Table", value=False, key="cat_pie_table_toggle")
        if show_pie3_table:
            st.dataframe(filtered_df.groupby('Category', as_index=False)['Debit Net Amount'].sum()
                         .rename(columns={'Debit Net Amount': 'Total Amount'}))
        else:
            category_df = (filtered_df.groupby('Category', as_index=False)['Debit Net Amount']
                           .sum().rename(columns={'Debit Net Amount': 'Total Amount'}))
            cat_fig = px.pie(category_df, names='Category', values='Total Amount',
                             title='Total Amount by Category', hole=0.4,
                             color_discrete_sequence=color_theme)
            cat_fig.update_traces(textposition='inside', textinfo='percent+label', marker_line_width=0)
            st.plotly_chart(cat_fig, use_container_width=True)





### missing transaction IDs checker ###

# ===== Missing Transaction Checker (helpers) =====
def _map_cols(df: pd.DataFrame) -> dict:
    return {c.lower().strip(): c for c in df.columns}

def _pick_name(df: pd.DataFrame, cmap: dict, candidates):
    for c in candidates:
        k = cmap.get(c.lower())
        if k in df.columns:
            return k
    return None

def _norm_id(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()

def _nice_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Friendly subset of common columns if present (by NAME)."""
    m = _map_cols(df)
    def col(*cands): return _pick_name(df, m, list(cands))
    names = [
        col("Transaction Id","TransactionID","Transaction_Id"),
        col("Time","Created At","Transaction timestamp UTC"),
        col("Type"),
        col("Financial Transaction Type","Financial transaction type","Financial_Type"),
        col("Description","Reference"),
        col("Amount","Transaction amount","Billing amount"),
        col("Debit Net Amount","Debit Amount"),
        col("Credit Net Amount","Credit Amount"),
        col("Wallet Currency","Transaction Currency","Billing currency","Currency"),
        col("Employee(s)","User","Employee1"),
        col("Expense category","Category"),
    ]
    names = [n for n in names if n is not None]
    names = list(dict.fromkeys(names))  # dedupe keep order
    return df.loc[:, names] if names else df.copy()

def _pair_missing(A: pd.DataFrame, nameA: str,
                  B: pd.DataFrame, nameB: str):
    """Return (A_only_df, B_only_df) comparing by Transaction Id."""
    if A is None or B is None or A.empty or B.empty:
        return pd.DataFrame(), pd.DataFrame()

    ma, mb = _map_cols(A), _map_cols(B)
    colA = _pick_name(A, ma, ["Transaction Id","TransactionID","Transaction_Id"])
    colB = _pick_name(B, mb, ["Transaction Id","TransactionID","Transaction_Id"])
    if not colA or not colB:
        return pd.DataFrame(), pd.DataFrame()

    A_ids = _norm_id(A[colA]); valid_A = A_ids.ne("") & A_ids.ne("nan") & A_ids.notna()
    B_ids = _norm_id(B[colB]); valid_B = B_ids.ne("") & B_ids.ne("nan") & B_ids.notna()

    setA = set(A_ids[valid_A].unique())
    setB = set(B_ids[valid_B].unique())

    A_only_mask = valid_A & ~A_ids.isin(setB)
    B_only_mask = valid_B & ~B_ids.isin(setA)

    A_only = _nice_subset(A.loc[A_only_mask].copy())
    B_only = _nice_subset(B.loc[B_only_mask].copy())
    return A_only, B_only
 

 ##missing transaction checker UI ##

st.markdown("---")
st.header("🔍 Missing Transaction Checker")
with st.expander("Check missing transactions", expanded=False):
    st.caption("Compare **Transaction Id** across files and see what's present in one but missing in another.")

    compare_choice = st.selectbox(
        "Select comparison",
        [
            "Balance vs Expense",
            "Balance vs Unified (in-app)",
            "Expense vs Unified (in-app)"
        ],
        index=0,
        help="Unified (in-app) uses the dataframe built by this app (no extra upload needed)."
    )

    # Map the selection to actual dataframes
    if compare_choice == "Balance vs Expense":
        A, nameA = balance_file, "Balance"
        B, nameB = expense_file, "Expense"
    elif compare_choice == "Balance vs Unified (in-app)":
        A, nameA = balance_file, "Balance"
        B, nameB = df, "Unified (in-app)"
    else:  # Expense vs Unified
        A, nameA = expense_file, "Expense"
        B, nameB = df, "Unified (in-app)"

    if st.button("Run check", type="primary", use_container_width=True):
        A_only, B_only = _pair_missing(A, nameA, B, nameB)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader(f"Present in {nameA} but MISSING in {nameB}")
            st.write(f"Rows: **{len(A_only)}**")
            st.dataframe(A_only, use_container_width=True, height=320)
            if not A_only.empty:
                st.download_button(
                    f"Download {nameA}-only CSV",
                    data=A_only.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{nameA.lower()}_only_vs_{nameB.lower()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        with c2:
            st.subheader(f"Present in {nameB} but MISSING in {nameA}")
            st.write(f"Rows: **{len(B_only)}**")
            st.dataframe(B_only, use_container_width=True, height=320)
            if not B_only.empty:
                st.download_button(
                    f"Download {nameB}-only CSV",
                    data=B_only.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{nameB.lower()}_only_vs_{nameA.lower()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

        # 3-way summary (optional, shown only when comparing to Unified)
        if "Unified" in nameA or "Unified" in nameB:
            st.caption("Tip: For a full 3-way summary (Balance vs Expense vs Unified), run the external checker you built, or extend this block similarly.")
