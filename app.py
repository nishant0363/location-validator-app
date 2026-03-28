import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
# from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials
st.set_page_config(layout="wide")
st.markdown("""
    <style>
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        header {visibility: hidden;}
        .block-container {
            padding-top: 0rem;
        }
    </style>
""", unsafe_allow_html=True)

SHEET_NAME = "Google_API_Data_inside_NM_Blr"   # <-- change this

# -------------------------------
# GOOGLE SHEETS CONNECTION
# -------------------------------
@st.cache_resource
def connect_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    # creds = ServiceAccountCredentials.from_json_keyfile_name(
    #     "credentials.json", scope
    # )

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

sheet = connect_gsheet()

# -------------------------------
# LOAD DATA
# -------------------------------
@st.cache_data(ttl=5)
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    if "status" not in df.columns:
        df["status"] = ""

    df["status"] = df["status"].fillna("").astype(str).str.strip()

    return df

df = load_data()

# -------------------------------
# UPDATE FUNCTION
# -------------------------------
def update_status(row_idx, value):
    # +2 because:
    # row 1 = header
    # dataframe index starts at 0
    sheet.update_cell(row_idx + 2, df.columns.get_loc("status") + 1, value)

# -------------------------------
# SESSION STATE
# -------------------------------
if "current_idx" not in st.session_state:
    pending = df[~df["status"].isin(["OK", "NOT_OK"])]
    st.session_state.current_idx = pending.index[0] if len(pending) > 0 else 0

idx = st.session_state.current_idx
row = df.loc[idx]

# -------------------------------
# LAYOUT
# -------------------------------
left, right = st.columns([1, 4])

# ===============================
# LEFT PANEL
# ===============================
with left:

    st.subheader("Controls")

    jump_idx = st.number_input("Go to row", 0, len(df)-1, idx)

    if st.button("Go"):
        st.session_state.current_idx = jump_idx
        st.rerun()

    col1, col2 = st.columns(2)

    if col1.button("⬅️ Prev"):
        if idx > 0:
            st.session_state.current_idx -= 1
            st.rerun()

    if col2.button("➡️ Next"):
        if idx < len(df) - 1:
            st.session_state.current_idx += 1
            st.rerun()

    # st.markdown("---")

    st.subheader("Selected Row Data")
    st.write(row["Property_Name"])
    st.write(row["Category"])
    st.write(row["Micro_Market"])

    gmap_link = f"https://www.google.com/maps/place/?q=place_id:{row['place_id']}"
    st.markdown(f"[Open in Google Maps]({gmap_link})")

    col3, col4 = st.columns(2)

    if col3.button("✅ OK"):
        update_status(idx, "OK")
        st.session_state.current_idx += 1
        st.cache_data.clear()
        st.rerun()

    if col4.button("❌ Not OK"):
        update_status(idx, "NOT_OK")
        st.session_state.current_idx += 1
        st.cache_data.clear()
        st.rerun()

    st.download_button(
            "Download Updated CSV",
            df.to_csv(index=False),
            file_name="updated_data.csv",
            mime="text/csv"
        )

# ===============================
# RIGHT PANEL
# ===============================
with right:
    st.subheader("Dataset View")
    def highlight_row(x):
        return ['background-color: yellow' if x.name == idx else '' for _ in x]

    st.dataframe(df.style.apply(highlight_row, axis=1), height=200)

    # st.markdown("---")

    st.subheader("Map")

    lat = row["Latitude"]
    lon = row["Longitude"]

    m = folium.Map(location=[lat, lon], zoom_start=16)

    folium.Marker(
        [lat, lon],
        tooltip=row["Property_Name"],
        icon=folium.Icon(color="red")
    ).add_to(m)

    st_folium(m, width=1200, height=300, key=f"map_{idx}")