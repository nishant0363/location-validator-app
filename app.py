import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
import base64
from PIL import Image
import io
from streamlit_paste_button import paste_image_button

st.set_page_config(layout="wide")

st.markdown("""
    <style>
        header {visibility: hidden;}
        .block-container {padding-top: 0rem;}
    </style>
""", unsafe_allow_html=True)

SHEET_NAME = "Google_API_Data_inside_NM"

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

    if "screenshot_num" not in df.columns:
        df["screenshot_num"] = ""

    df["status"] = df["status"].fillna("").astype(str).str.strip()
    df["screenshot_num"] = df["screenshot_num"].fillna("").astype(str).str.strip()

    return df

df = load_data()

# -------------------------------
# UPDATE FUNCTIONS
# -------------------------------
def update_status(row_idx, value):
    sheet.update_cell(row_idx + 2, df.columns.get_loc("status") + 1, value)

def update_screenshot(row_idx, value):
    sheet.update_cell(row_idx + 2, df.columns.get_loc("screenshot_num") + 1, value)

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
left, right = st.columns([2, 4])

# ===============================
# LEFT PANEL (INPUT ONLY)
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

    st.subheader("Selected Row Data")
    st.write(row["Property_Name"])
    st.write(row["Category"])
    st.write(row["Micro_Market"])

    gmap_link = f"https://www.google.com/maps/place/?q=place_id:{row['place_id']}"
    st.markdown(f"[Open in Google Maps]({gmap_link})")

    col3, col4 = st.columns(2)

    if col3.button("✅ OK"):
        update_status(idx, "OK")
        st.success("Marked OK")
        st.cache_data.clear()
        st.rerun()

    if col4.button("❌ Not OK"):
        update_status(idx, "NOT_OK")
        st.session_state.current_idx += 1
        st.cache_data.clear()
        st.rerun()

    # -------------------------------
    # 📋 INPUT SECTION (LEFT)
    # -------------------------------
    st.markdown("---")
    st.subheader("Upload / Paste Screenshot")

    paste_result = paste_image_button(
        label="📋 Paste Screenshot (Ctrl+V)",
        key=f"paste_{idx}"
    )

    uploaded_file = st.file_uploader(
        "Upload Screenshot",
        type=["png", "jpg", "jpeg"],
        key=f"upload_{idx}"
    )

    image_source = None

    if paste_result.image_data is not None:
        if isinstance(paste_result.image_data, Image.Image):
            image_source = paste_result.image_data
        else:
            image_source = Image.open(io.BytesIO(paste_result.image_data))

    elif uploaded_file is not None:
        image_source = Image.open(uploaded_file)

    if image_source is not None:

        if image_source.mode in ("RGBA", "P"):
            image_source = image_source.convert("RGB")

        image_source.thumbnail((450, 350))

        buffer = io.BytesIO()
        # image_source.save(buffer, format="JPEG", quality=60)
        image_source.save(buffer, format="JPEG", quality=70)
        encoded = base64.b64encode(buffer.getvalue()).decode()

        st.image(image_source, caption="Preview", use_container_width=True)

        if len(encoded) > 45000:
            st.error("Image too large after compression")
        else:
            col5, col6 = st.columns(2)

            if col5.button("💾 Save Screenshot"):
                update_screenshot(idx, encoded)
                st.success("Saved!")
                st.cache_data.clear()
                st.rerun()

            if col6.button("➡️ Save & Next"):
                update_screenshot(idx, encoded)
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
# RIGHT PANEL (VIEW ONLY)
# ===============================
with right:
    st.subheader("Dataset View")

    def highlight_row(x):
        return ['background-color: yellow' if x.name == idx else '' for _ in x]

    st.dataframe(df.style.apply(highlight_row, axis=1), height=200)

    st.subheader("Map")

    lat = row["Latitude"]
    lon = row["Longitude"]

    m = folium.Map(location=[lat, lon], zoom_start=16)

    folium.Marker(
        [lat, lon],
        tooltip=row["Property_Name"],
        icon=folium.Icon(color="red")
    ).add_to(m)

    st_folium(m, width=1500, height=300, key=f"map_{idx}")

    # -------------------------------
    # 👁️ VIEW ONLY SCREENSHOT
    # -------------------------------
    st.markdown("---")
    st.subheader("Screenshot View")

    current_ss = row.get("screenshot_num", "")
    if current_ss:
        try:
            img_bytes = base64.b64decode(current_ss)
            st.image(img_bytes, caption="Saved Screenshot", use_container_width=True)
        except:
            st.warning("Unable to display screenshot")
    else:
        st.info("No screenshot uploaded yet")