import os

import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

API_HOST = os.getenv("API_HOST", "http://127.0.0.1:8000")

st.set_page_config(layout="wide")
st.title("📊 Entity Summarizer")

if 'summary_data' not in st.session_state:
    st.session_state.summary_data = None
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = None
if 'entity_name' not in st.session_state:
    st.session_state.entity_name = ""


@st.cache_data(ttl=3600, show_spinner=False)
def get_entity_summary(entity: str):
    try:
        response = requests.get(f"{API_HOST}/summarize/{entity}", timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {str(e)}")
        return None


def display_tabs(data):
    tabs = st.tabs(["📄 Summary", "📂 Documents"])

    with tabs[0]:
        st.markdown(data.get("summary", "No summary found."), unsafe_allow_html=True)


        if data.get("official_news"):
            st.subheader("📎 Official News")
            for item in data["official_news"]:
                st.markdown(f"- [{item['title']}]({item['link']})")
        else:
            st.info("No official news available.")

    with tabs[1]:
        if data.get("official_documents"):
            docs_by_year = {}
            for doc in data["official_documents"]:
                year = doc.get("year", "Unknown")
                docs_by_year.setdefault(year, []).append(doc)

            years = sorted(docs_by_year.keys(), reverse=True)
            selected_year = st.selectbox(
                "Select a year",
                years,
                index=years.index(st.session_state.selected_year) if st.session_state.selected_year in years else 0,
                key='year_select'
            )
            st.session_state.selected_year = selected_year

            for doc in docs_by_year[selected_year]:
                st.markdown(f"- [{doc['title']}]({doc['link']})")
        else:
            st.info("No documents found.")

    # Download button
    entity_safe = st.session_state.entity_name.replace(" ", "_")
    pdf_download_url = f"{API_HOST}/download/{entity_safe}"
    try:
        response = requests.get(pdf_download_url)
        response.raise_for_status()
        st.download_button(
            "📄 Download Summary PDF",
            data=response.content,
            file_name=f"{entity_safe}_summary.pdf",
            mime="application/pdf"
        )
    except requests.exceptions.RequestException:
        st.warning("PDF download failed. Try again after summarization.")


# Main form
with st.form("summary_form"):
    entity = st.text_input("Enter company/entity name", value=st.session_state.entity_name)
    submit_button = st.form_submit_button("Summarize Entity")

if submit_button:
    if not entity.strip():
        st.warning("Please enter a valid company/entity name.")
    else:
        st.session_state.entity_name = entity.strip()
        with st.spinner("Summarizing..."):
            data = get_entity_summary(entity.strip())

            if data and "error" not in data:
                st.session_state.summary_data = data
                if data.get("official_documents"):
                    docs_by_year = {}
                    for doc in data["official_documents"]:
                        year = doc.get("year", "Unknown")
                        docs_by_year.setdefault(year, []).append(doc)
                    st.session_state.selected_year = sorted(docs_by_year.keys(), reverse=True)[0]
                st.rerun()
            elif data and "error" in data:
                st.error(data["error"])
            else:
                st.error("Failed to summarize entity. Please try again.")


def display_financial_dashboard(financial_data: dict):
    if not financial_data:
        st.info("No financial data available for visualization.")
        return

    years = sorted(financial_data.keys(), reverse=True)
    current_year = str(datetime.now().year)
    current_month = datetime.now().month
    completed_quarters = ["Q1", "Q2", "Q3", "Q4"]
    if current_year in years:
        if current_month <= 3:
            completed_quarters = ["Q1"]
        elif current_month <= 6:
            completed_quarters = ["Q1", "Q2"]
        elif current_month <= 9:
            completed_quarters = ["Q1", "Q2", "Q3"]

    selected_year = st.selectbox("Select Year", years, index=0)
    available_quarters = sorted(financial_data[selected_year].keys())
    if selected_year == current_year:
        available_quarters = [q for q in available_quarters if q in completed_quarters]

    selected_quarter = st.selectbox("Select Quarter", available_quarters, index=len(available_quarters)-1)

    current = financial_data[selected_year][selected_quarter]

    # Handle previous quarter logic (including previous year's Q4 when Q1 is selected)
    previous = None
    prev_quarter_text = ""

    if selected_quarter == "Q1" and len(years) > 1 and str(int(selected_year) - 1) in financial_data:
        # If Q1 is selected, get Q4 from previous year
        prev_year = str(int(selected_year) - 1)
        if "Q4" in financial_data[prev_year]:
            previous = financial_data[prev_year]["Q4"]
            prev_quarter_text = f"Q4 {prev_year}"
    else:
        # Otherwise get previous quarter from same year
        q_list = ["Q1", "Q2", "Q3", "Q4"]
        curr_idx = q_list.index(selected_quarter)
        if curr_idx > 0:
            prev_q = q_list[curr_idx - 1]
            if prev_q in financial_data[selected_year]:
                previous = financial_data[selected_year][prev_q]
                prev_quarter_text = f"{prev_q} {selected_year}"

    st.subheader(f"📊 {selected_quarter} {selected_year} Financials")
    df = pd.DataFrame([
        {"Metric": "Revenue", "Value": current.get("revenue", 0)},
        {"Metric": "Profit", "Value": current.get("profit", 0)}
    ])
    fig = px.bar(df, x="Metric", y="Value", title="Quarterly Metrics", text="Value")
    st.plotly_chart(fig, use_container_width=True)

    if previous:
        st.markdown(f"### 🔁 Comparison with Previous Quarter ({prev_quarter_text})")
        comp_df = pd.DataFrame([
            {"Metric": "Revenue", "Previous": previous.get("revenue", 0), "Current": current.get("revenue", 0)},
            {"Metric": "Profit", "Previous": previous.get("profit", 0), "Current": current.get("profit", 0)}
        ])
        # Calculate change percentage safely (handling division by zero)
        comp_df["Change (%)"] = comp_df.apply(
            lambda row: ((row["Current"] - row["Previous"]) / max(row["Previous"], 0.01)) * 100
            if row["Previous"] != 0 else 0,
            axis=1
        )

        # Format values explicitly rather than using .style.format
        formatted_df = pd.DataFrame({
            "Metric": comp_df["Metric"],
            "Previous": [f"{val:.2f}" for val in comp_df["Previous"]],
            "Current": [f"{val:.2f}" for val in comp_df["Current"]],
            "Change (%)": [f"{val:+.2f}%" for val in comp_df["Change (%)"]]
        })

        st.dataframe(formatted_df)

    st.markdown("### 🔮 Prediction (Linear Extrapolation)")
    q_index = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

    # Collect all available quarterly data for the selected year
    past_data = []
    for year in years:
        for q in sorted(financial_data[year].keys()):
            data = financial_data[year][q]
            if data.get("revenue") is not None and data.get("profit") is not None:
                quarter_num = q_index[q]
                year_num = int(year)
                # Create a numerical representation for sorting (year*10 + quarter)
                time_key = year_num*10 + quarter_num
                past_data.append((time_key, quarter_num, year, q, data["revenue"], data["profit"]))

    # Sort by time key to ensure chronological order
    past_data.sort()

    if len(past_data) >= 2:
        # Extract data for prediction
        time_keys = [item[0] for item in past_data]
        revenues = [item[4] for item in past_data]
        profits = [item[5] for item in past_data]

        # Calculate trends based on last two data points
        rev_trend = (revenues[-1] - revenues[-2])
        prof_trend = (profits[-1] - profits[-2])

        # Determine next quarter
        current_q_idx = q_index[selected_quarter]
        current_year_num = int(selected_year)

        next_q_idx = current_q_idx + 1
        next_year_num = current_year_num

        if next_q_idx > 4:
            next_q_idx = 1
            next_year_num += 1

        next_q = [k for k, v in q_index.items() if v == next_q_idx][0]

        # Display prediction
        st.info(f"Prediction for {next_q} {next_year_num}:\n"
                f"- Revenue: {revenues[-1] + rev_trend:.2f}\n"
                f"- Profit: {profits[-1] + prof_trend:.2f}")

        # Create and display trend chart
        if len(past_data) >= 3:  # Only show chart if we have enough data points
            trend_df = pd.DataFrame([
                {"Period": f"{item[3]} {item[2]}", "Revenue": item[4], "Profit": item[5]}
                for item in past_data[-4:]  # Show last 4 quarters
            ])

            # Add prediction point
            trend_df = pd.concat([
                trend_df,
                pd.DataFrame([{
                    "Period": f"{next_q} {next_year_num} (Pred)",
                    "Revenue": revenues[-1] + rev_trend,
                    "Profit": profits[-1] + prof_trend
                }])
            ])

            fig = px.line(trend_df, x="Period", y=["Revenue", "Profit"],
                          title="Financial Trends with Prediction",
                          markers=True)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Not enough data for prediction. At least two quarters of data are required.")


if st.session_state.summary_data:
    display_tabs(st.session_state.summary_data)

    if "financial_data" in st.session_state.summary_data:
        display_financial_dashboard(st.session_state.summary_data["financial_data"])
