
# streamlit_app.py
import streamlit as st
import pandas as pd
from io import StringIO
from fb_mapper import transform

st.set_page_config(page_title="Facebook Bulk CSV Builder", page_icon="📤", layout="wide")

st.title("Facebook Bulk CSV Builder")
st.caption("Upload a simple CSV or paste rows. The app validates, fills defaults, and outputs a Facebook-ready bulk import CSV.")

with st.expander("Input format (simple mode)", expanded=False):
    st.markdown("""
    **Columns required on ad set rows** (use exactly these headers):
    - Input Level (`campaign` or `adset`)
    - Campaign Name, Campaign Status, Special Ad Categories, Special Ad Category Country
    - Campaign Objective, Buying Type, Campaign Bid Strategy, Campaign Daily Budget, Campaign Start Time, Campaign Stop Time
    - Ad Set Name, Ad Set Run Status, Ad Set Daily Budget, Ad Set Time Start, Ad Set Time Stop
    - Countries, Age Min, Age Max, Gender, Custom Audiences, Excluded Custom Audiences, Optimisation Goal
    - Ad Name, Ad Status, Title, Body, Link, URL Tags, Call to Action, Image File Name
    """)

tab_upload, tab_paste = st.tabs(["Upload CSV","Paste rows"])

df_input = None

with tab_upload:
    f = st.file_uploader("Upload simple-mode CSV", type=["csv"])
    if f is not None:
        df_input = pd.read_csv(f)

with tab_paste:
    text = st.text_area("Paste CSV rows including header", height=200, placeholder="Input Level,Campaign Name,...")
    if text:
        df_input = pd.read_csv(StringIO(text))

st.divider()

if df_input is not None:
    st.subheader("Preview input")
    st.dataframe(df_input.head(20), use_container_width=True)
    try:
        out_df, err_df = transform(df_input)
        if not err_df.empty:
            st.error("Validation issues found. Fix before exporting.")
            st.dataframe(err_df, use_container_width=True)
        else:
            st.success("Validated. Ready to export.")
        st.subheader("Mapped output")
        st.dataframe(out_df.head(50), use_container_width=True)

        csv_bytes = out_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download Facebook-ready CSV", data=csv_bytes, file_name="facebook_bulk_upload.csv", mime="text/csv")
    except Exception as e:
        st.error(f"Processing failed: {e}")
else:
    st.info("Upload a CSV or paste rows to begin.")
