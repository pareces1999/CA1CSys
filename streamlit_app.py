import streamlit as st

st.set_page_config(
    page_title="CA1C System",
    page_icon="🐂",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.image("assets/logo.png", width=150)

pages = [
    st.Page("views/1_🏠_Home.py",    title="Home",    icon="🏠", url_path="home"),
    st.Page("views/2_👥_Clients.py", title="Clients", icon="👥", url_path="clients"),
    st.Page("views/3_📦_Orders.py",  title="Orders",  icon="📦", url_path="orders"),
    st.Page("views/4_💰_Prices.py",  title="Prices",  icon="💰", url_path="prices"),
]

pg = st.navigation(pages, position="sidebar")
pg.run()