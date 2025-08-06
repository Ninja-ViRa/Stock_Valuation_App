pip install -r requirements.txt
import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Constants
TERMINAL_GROWTH_RATE = 0.04
FORECAST_YEARS = 20
RISK_FREE_RATE = 0.045  # Latest 10-year US Treasury yield
MARKET_RISK_PREMIUM = 0.025  # Latest US equity market premium

# ----------------------------
# Utility Functions
# ----------------------------

def get_growth_rate(ticker):
    try:
        stock = yf.Ticker(ticker)
        growth = stock.info.get("earningsQuarterlyGrowth", None)
        if growth and growth > 0:
            return growth, "Yahoo Finance"
    except:
        pass
    return 0.10, "Default"

def get_eps(ticker):
    try:
        stock = yf.Ticker(ticker)
        eps = stock.info.get("trailingEps", None)
        if eps and eps > 0:
            return eps, "Yahoo Finance"
    except:
        pass
    return None, "Unavailable"

def get_beta(ticker):
    try:
        stock = yf.Ticker(ticker)
        beta = stock.info.get("beta", None)
        if beta and beta > 0:
            return beta
    except:
        pass
    return 1.0  # Default beta

# ----------------------------
# Data Preview
# ----------------------------

def preview_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info

    data = {
        "EPS (ttm)": info.get("trailingEps", None),
        "Net Income to Common": info.get("netIncomeToCommon", None),
        "Operating Cash Flow": info.get("operatingCashflow", None),
        "Capital Expenditures": info.get("capitalExpenditures", 0),
        "Shares Outstanding": info.get("sharesOutstanding", None),
        "Beta": info.get("beta", None)
    }

    st.subheader("📊 Data Preview")
    st.write(pd.DataFrame(data.items(), columns=["Metric", "Value"]))

    return data

# ----------------------------
# Valuation Methods
# ----------------------------

def calculate_eps_valuation(ticker, discount_rate, growth_rate):
    try:
        eps, source = get_eps(ticker)
        if eps is None or eps <= 0:
            st.warning(f"⚠️ EPS unavailable for {ticker}")
            return None

        growths = [growth_rate, growth_rate, growth_rate / 2, growth_rate / 2, TERMINAL_GROWTH_RATE]
        projected = [eps * ((1 + growths[i]) ** (i + 1)) for i in range(FORECAST_YEARS)]
        discounted = [val / ((1 + discount_rate) ** (i + 1)) for i, val in enumerate(projected)]

        terminal = projected[-1] * (1 + TERMINAL_GROWTH_RATE) / (discount_rate - TERMINAL_GROWTH_RATE)
        discounted_terminal = terminal / ((1 + discount_rate) ** FORECAST_YEARS)

        intrinsic = sum(discounted) + discounted_terminal

        if discounted_terminal / intrinsic > 0.6:
            capped_terminal = 0.6 * intrinsic
            intrinsic = sum(discounted) + capped_terminal

        return round(intrinsic, 2)
    except Exception as e:
        st.error(f"❌ EPS valuation failed for {ticker}: {e}")
        return None

def calculate_ocf_based_intrinsic_value(ticker, discount_rate):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        growth_1_5 = info.get("earningsQuarterlyGrowth", 0.10)
        growth_6_10 = growth_1_5 / 2
        growth_11_20 = TERMINAL_GROWTH_RATE

        ocf = info.get("operatingCashflow", None)
        shares = info.get("sharesOutstanding", None)
        if ocf is None or ocf <= 0 or shares is None or shares <= 0:
            return None, None, None

        projected_ocf = []
        discounted_ocf = []

        for year in range(1, 21):
            if year <= 5:
                growth = growth_1_5
            elif year <= 10:
                growth = growth_6_10
            else:
                growth = growth_11_20

            projected = ocf * ((1 + growth) ** year)
            discount_factor = 1 / ((1 + discount_rate) ** year)
            discounted = projected * discount_factor

            projected_ocf.append(projected)
            discounted_ocf.append(discounted)

        total_value = sum(discounted_ocf)
        intrinsic_per_share = total_value / shares

        cash = info.get("cash", 0)
        short_term_investments = info.get("shortTermInvestments", 0)
        short_term_debt = info.get("shortTermDebt", 0)
        long_term_debt = info.get("longTermDebt", 0)

        cash_per_share = (cash + short_term_investments) / shares
        debt_per_share = (short_term_debt + long_term_debt) / shares

        final_value = intrinsic_per_share + cash_per_share - debt_per_share

        return round(final_value, 2), projected_ocf, discounted_ocf

    except Exception as e:
        st.error(f"❌ OCF-based valuation failed for {ticker}: {e}")
        return None, None, None

# ----------------------------
# Streamlit UI
# ----------------------------

st.title("📈 Stock Valuation Dashboard")

ticker = st.text_input("Enter Ticker Symbol", "AAPL")

if ticker:
    growth_rate, source = get_growth_rate(ticker)
    beta = get_beta(ticker)
    calculated_discount_rate = RISK_FREE_RATE + beta * MARKET_RISK_PREMIUM

    st.write(f"📉 Using growth rate: **{growth_rate:.2%}** from **{source}**")

    with st.expander("ℹ️ Discount Rate Details"):
        st.markdown(f"""
        - **Risk-Free Rate**: {RISK_FREE_RATE:.2%}  
        - **Market Risk Premium**: {MARKET_RISK_PREMIUM:.2%}  
        - **Beta**: {beta:.2f}  
        - **Calculated Discount Rate**: {calculated_discount_rate:.2%}  
        """)
        st.markdown("[🔗 Source: market-risk-premia.com](https://www.market-risk-premia.com/us.html)")

    custom_rate = st.slider(
        "Adjust Discount Rate (if needed)",
        min_value=0.03,
        max_value=0.15,
        value=round(calculated_discount_rate, 3),
        step=0.001
    )

    preview_data(ticker)

    #eps_val = calculate_eps_valuation(ticker, custom_rate, growth_rate)
    #st.subheader("💰 Valuation Results")
    #st.write(f"**EPS-based Valuation:** ${eps_val}")

    ocf_val, projected_ocf, discounted_ocf = calculate_ocf_based_intrinsic_value(ticker, custom_rate)

    if ocf_val:
        st.subheader("📊 20-Year OCF-Based Valuation")
        st.write(f"**Intrinsic Value (OCF-based):** ${ocf_val}")

        st.subheader("📈 Projected vs Discounted OCF")
        years = list(range(1, 21))
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(years, projected_ocf, label="Projected OCF", color="blue")
        ax.plot(years, discounted_ocf, label="Discounted OCF", color="green")
        ax.set_xlabel("Year")
        ax.set_ylabel("Operating Cash Flow (USD)")
        ax.set_title(f"Projected vs Discounted OCF for {ticker}")
        ax.legend()
        ax.grid(True)
        st.pyplot(fig)
