import streamlit as st
from yahooquery import search
import yfinance as yf
import pandas as pd
import plotly.express as px
def format_number(num):
    try:
        abs_num = abs(num)
        if abs_num < 100000:
            return str(int(num))
        elif abs_num < 1_000_000:
            return f"{num / 100000:.2f} Lakh"
        elif abs_num < 1_000_000_000:
            return f"{num / 1_000_000:.0f} M"
        else:
            return f"{num / 1_000_000_000:.2f} B"
    except:
        return num


def get_ticker_from_name(company_name):
    results = search(company_name)
    for item in results.get('quotes', []):
        if item.get('quoteType') == 'EQUITY':
            return item['symbol']
    return None


def get_income_statement(ticker_symbol):
    company = yf.Ticker(ticker_symbol)
    income_annual = company.financials
    income_quarterly = company.quarterly_financials

    if income_annual is None or income_annual.empty:
        income_annual = pd.DataFrame()
    if income_quarterly is None or income_quarterly.empty:
        income_quarterly = pd.DataFrame()
    return income_annual, income_quarterly


def format_dataframe(df):
    return df.applymap(lambda x: format_number(x) if isinstance(x, (int, float)) else x)


def plot_metric(df, metric, title):
    st.write(f"### {title}")
    if metric in df.index:
        data = df.loc[metric].dropna()
        data.index = pd.to_datetime(data.index)
        st.line_chart(data)
    else:
        st.warning(f"{metric} not available in data.")


# ========== Streamlit UI ==========

st.set_page_config(page_title="Financial P&L Viewer", layout="wide")

st.title("📊 Company Financial Data")
st.write("Enter a company name (e.g., Apple, Tesla, Microsoft) to view its income statement.")

company_name = st.text_input("Company Name", placeholder="e.g. Apple")

if company_name:
    if ("company_name" not in st.session_state) or (st.session_state.company_name != company_name):
        st.session_state.company_name = company_name
        with st.spinner("Searching for company..."):
            st.session_state.ticker = get_ticker_from_name(company_name)
        if st.session_state.ticker:
            with st.spinner("Fetching income statements..."):
                st.session_state.annual, st.session_state.quarterly = get_income_statement(st.session_state.ticker)
        else:
            st.session_state.annual, st.session_state.quarterly = pd.DataFrame(), pd.DataFrame()

    ticker = st.session_state.get("ticker", None)
    annual = st.session_state.get("annual", pd.DataFrame())
    quarterly = st.session_state.get("quarterly", pd.DataFrame())

    if ticker:
        st.success(f"Found Ticker: {ticker}")

        if not annual.empty:
            formatted_annual = format_dataframe(annual)
            st.subheader("📅 Annual Income Statement")
            st.dataframe(formatted_annual, use_container_width=True)
        else:
            st.warning("No annual income statement data available.")

        if not quarterly.empty:
            formatted_quarterly = format_dataframe(quarterly)
            st.subheader("📆 Quarterly Income Statement")
            st.dataframe(formatted_quarterly, use_container_width=True)
        else:
            st.warning("No quarterly income statement data available.")

        # === Show Graphs Button ===
        if st.button("📈 Show Graphs"):
            if not annual.empty:
                st.subheader("📊 Key Financial Metrics (Annual)")

                col1, col2 = st.columns(2)
                with col1:
                    plot_metric(annual, "Total Revenue", "Total Revenue")
                with col2:
                    plot_metric(annual, "Cost Of Revenue", "Cost of Revenue")

                col3, col4 = st.columns(2)
                with col3:
                    plot_metric(annual, "Total Expenses", "Total Expenses")
                with col4:
                    plot_metric(annual, "Net Income", "Net Income")
            else:
                st.warning("No annual data available for graphing.")

            if not quarterly.empty:
                st.subheader("📉 Key Financial Metrics (Quarterly)")

                col5, col6 = st.columns(2)
                with col5:
                    plot_metric(quarterly, "Total Revenue", "Total Revenue (Quarterly)")
                with col6:
                    plot_metric(quarterly, "Cost Of Revenue", "Cost of Revenue (Quarterly)")

                col7, col8 = st.columns(2)
                with col7:
                    plot_metric(quarterly, "Total Expenses", "Total Expenses (Quarterly)")
                with col8:
                    plot_metric(quarterly, "Net Income", "Net Income (Quarterly)")
            else:
                st.warning("No quarterly data available for graphing.")

        # ===== Additional Plotly Charts =====

        if not quarterly.empty:
            quarterly_plot = quarterly.copy()
            quarterly_plot.columns = pd.to_datetime(quarterly_plot.columns, errors='coerce')

            # 1. Bar Chart - Net Income
            if "Net Income" in quarterly_plot.index:
                st.subheader("💰 Net Income (Quarterly) - Bar Chart")
                net_income = quarterly_plot.loc["Net Income"].dropna()
                fig_bar = px.bar(
                    x=net_income.index,
                    y=net_income.values,
                    title="Net Income per Quarter",
                    labels={"x": "Quarter", "y": "Net Income"}
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # 2. Donut Chart - Total Expenses vs Total Revenue
            if all(x in quarterly_plot.index for x in ["Total Expenses", "Total Revenue"]):
                st.subheader("🍩 Expenses vs Revenue (Latest Quarter) - Donut Chart")
                latest_quarter = quarterly_plot.columns[-1]
                exp_val = quarterly_plot.loc["Total Expenses", latest_quarter]
                rev_val = quarterly_plot.loc["Total Revenue", latest_quarter]
                donut_data = pd.DataFrame({
                    "Category": ["Expenses", "Remaining (Profit or Margin)"],
                    "Value": [exp_val, rev_val - exp_val]
                })
                fig_donut = px.pie(
                    donut_data,
                    names="Category",
                    values="Value",
                    hole=0.5,
                    title=f"Latest Quarter: {latest_quarter.date()}"
                )
                st.plotly_chart(fig_donut, use_container_width=True)

            # 3. Area Chart - Revenue vs Cost of Revenue - FIXED VERSION
            if all(x in quarterly_plot.index for x in ["Total Revenue", "Cost Of Revenue"]):
                st.subheader("📉 Revenue vs Cost of Revenue - Area Chart")

                # Create a dataframe for the area chart
                dates = quarterly_plot.columns
                revenue_data = quarterly_plot.loc["Total Revenue"].values
                cost_data = quarterly_plot.loc["Cost Of Revenue"].values

                # Create proper data structure for plotting
                area_data = []

                for i, date in enumerate(dates):
                    if pd.notna(revenue_data[i]):
                        area_data.append({
                            "Date": date,
                            "Category": "Total Revenue",
                            "Amount": revenue_data[i]
                        })
                    if pd.notna(cost_data[i]):
                        area_data.append({
                            "Date": date,
                            "Category": "Cost Of Revenue",
                            "Amount": cost_data[i]
                        })

                # Convert to DataFrame
                area_df = pd.DataFrame(area_data)

                if not area_df.empty:
                    fig_area = px.area(
                        area_df,
                        x="Date",
                        y="Amount",
                        color="Category",
                        title="Total Revenue vs Cost of Revenue",
                        labels={"Date": "Quarter", "Amount": "Amount ($)"}
                    )
                    st.plotly_chart(fig_area, use_container_width=True)
                else:
                    st.warning("Not enough data for the area chart.")
        else:
            st.warning("No quarterly financial data to plot.")

    else:
        st.error("❌ Could not find a valid ticker for the given company name.")
