from pathlib import Path

import streamlit as st

from core.db.connection import get_db_info
from core.repositories.clients_repository import ClientsRepository
from core.repositories.orders_repository import OrdersRepository
from core.repositories.prices_repository import PricesRepository


ROOT_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT_DIR / "Logo_CA1C_COM.png"


def inject_home_styles() -> None:
    st.markdown(
        """
        <style>
            .hero-shell {
                background: linear-gradient(135deg, #fff8ed 0%, #f2dfca 100%);
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 24px;
                padding: 2rem;
                margin-bottom: 1.5rem;
            }

            .hero-kicker {
                color: #a61029;
                font-size: 0.95rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .hero-title {
                color: #34141b;
                font-size: 2.4rem;
                font-weight: 800;
                line-height: 1.1;
                margin: 0.35rem 0 0.75rem 0;
            }

            .hero-copy {
                color: #5f2c34;
                font-size: 1rem;
                max-width: 44rem;
            }

            .section-title {
                color: #34141b;
                font-size: 1.35rem;
                font-weight: 700;
                margin: 0.5rem 0 1rem 0;
            }

            .metric-card {
                background: #fffdf8;
                border: 1px solid rgba(166, 16, 41, 0.12);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(52, 20, 27, 0.06);
                min-height: 210px;
                padding: 1.35rem;
            }

            .metric-label {
                color: #7f4c54;
                font-size: 0.9rem;
                font-weight: 700;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }

            .metric-value {
                color: #a61029;
                font-size: 2rem;
                font-weight: 800;
                margin: 0.45rem 0;
            }

            .metric-copy {
                color: #5f2c34;
                font-size: 0.95rem;
                line-height: 1.55;
                margin-bottom: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


db_info = get_db_info()
clients_repository = ClientsRepository()
orders_repository = OrdersRepository()
prices_repository = PricesRepository()
client_count = clients_repository.get_client_count()
open_orders_count = orders_repository.get_open_order_count()
active_prices_count = prices_repository.get_active_price_count()

inject_home_styles()

hero_col, logo_col = st.columns([1.8, 1], gap="large")

with hero_col:
    st.markdown('<div class="hero-shell">', unsafe_allow_html=True)
    st.markdown('<div class="hero-kicker">Control Panel</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-title">Welcome to the CA1C System dashboard</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="hero-copy">
            This is the new Streamlit workspace for the CA1C business tools.
            Use the quick-access modules below to manage clients, orders, and
            pricing from a cleaner cloud-ready interface.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with logo_col:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    else:
        st.info("Logo asset not found yet.")

st.markdown('<div class="section-title">Quick Access</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4, gap="medium")

with col1:
    render_metric_card(
        "Clients",
        str(client_count),
        "Client records loaded through the repository layer and ready for future search, edit, and onboarding workflows.",
    )
    st.page_link("views/2_clients.py", label="Open Clients", icon="👥")

with col2:
    render_metric_card(
        "Orders",
        str(open_orders_count),
        "Open orders now come from the orders repository, ready for the next workflow and fulfillment steps.",
    )
    st.page_link("views/3_orders.py", label="Open Orders", icon="📦")

with col3:
    render_metric_card(
        "Prices",
        str(active_prices_count),
        "Active catalog prices now come from the new prices repository and will feed real order valuation next.",
    )
    st.page_link("views/4_prices.py", label="Open Prices", icon="💰")

with col4:
    db_value = "Ready for Turso" if db_info.backend == "turso" else str(db_info.table_count)
    db_copy = db_info.message
    if db_info.backend == "sqlite" and db_info.status == "connected":
        db_copy = (
            f"Connected to local SQLite. SQLite {db_info.sqlite_version or 'unknown'} "
            f"with {db_info.table_count} table(s). Clients: {client_count}."
        )
    elif db_info.backend == "turso":
        db_copy = f"Cloud database configuration detected. Clients: {client_count}."

    render_metric_card("DB Status", db_value, db_copy)
    if db_info.backend == "sqlite" and db_info.status == "connected":
        st.caption("Database ready")
    elif db_info.backend == "turso":
        st.caption("Cloud database configuration detected")
    else:
        st.caption("Awaiting local DB file or cloud credentials")

st.divider()

left_col, right_col = st.columns([1.2, 1], gap="large")

with left_col:
    st.subheader("What is ready")
    st.write(
        """
        The new shell includes branded navigation, a dashboard landing page,
        and repository-backed modules for clients, orders, and prices. It is
        structured to deploy cleanly on Streamlit Cloud.
        """
    )

with right_col:
    st.subheader("Database Status")
    if db_info.backend == "sqlite" and db_info.status == "connected":
        st.success("Connected to local SQLite")
        st.write(f"Tables detected: {db_info.table_count}")
        st.write(f"Clients: {client_count}")
        st.write(f"Open orders: {open_orders_count}")
        st.write(f"Active prices: {active_prices_count}")
        st.caption(f"DB path: {db_info.database_path}")
    elif db_info.backend == "turso":
        st.info("Ready for Turso")
        st.write(f"Clients: {client_count}")
        st.write(f"Open orders: {open_orders_count}")
        st.write(f"Active prices: {active_prices_count}")
        st.write("Set the Turso URL and auth token in Streamlit secrets to enable cloud mode.")
    elif db_info.status == "missing":
        st.warning("Local SQLite database file not found.")
        st.caption(f"Expected path: {db_info.database_path}")
    else:
        st.error(db_info.message)
