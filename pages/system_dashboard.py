# pages/system_dashboard.py
import streamlit as st
from utils.styling import create_metric_card, COLORS
import plotly.express as px
from datetime import datetime


def create_dashboard(db, analytics):
    """Create the main dashboard with metrics and charts"""
    st.markdown("<h1 class='main-header'>📊 Sales Dashboard</h1>", unsafe_allow_html=True)

    # One-time notification after scheduling a demo
    if st.session_state.get("demo_created_notification"):
        st.success(f"✅ Demo #{st.session_state.demo_created_notification} added successfully!")
        st.session_state.demo_created_notification = None

    if not analytics or not db:
        st.error("Analytics or Database not available.")
        return

    # Fetch analytics safely
    try:
        sales_summary = analytics.get_sales_summary()
        demo_stats = analytics.get_demo_conversion_rates()
        customer_analysis = analytics.get_customer_analysis()
        payment_analysis = analytics.get_payment_analysis()
    except Exception:
        sales_summary = {"total_sales": 0, "pending_amount": 0}
        demo_stats = {"conversion_rate": 0}
        customer_analysis = {"total_customers": 0}
        payment_analysis = {"total_pending": 0}

    # ------------------- METRICS ROW -------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(create_metric_card(f"₹{sales_summary['total_sales']:,.0f}", "Total Sales", "💰", COLORS["primary"]), unsafe_allow_html=True)

    with col2:
        st.markdown(create_metric_card(f"₹{sales_summary['pending_amount']:,.0f}", "Pending Payments", "⏳", COLORS["warning"]), unsafe_allow_html=True)

    with col3:
        st.markdown(create_metric_card(f"{demo_stats['conversion_rate']:.1f}%", "Demo Conversion", "🎯", COLORS["success"]), unsafe_allow_html=True)

    with col4:
        st.markdown(create_metric_card(f"{customer_analysis['total_customers']}", "Total Customers", "👥", COLORS["secondary"]), unsafe_allow_html=True)

    # ------------------- SALES TREND + PAYMENT CHARTS -------------------
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<h3 class='section-header'>Sales Trend</h3>", unsafe_allow_html=True)
        try:
            sales_trend = analytics.get_sales_trend()
            if not sales_trend.empty:
                fig = px.line(
                    sales_trend,
                    x="sale_date",
                    y="total_amount",
                    title="Daily Sales Trend",
                    color_discrete_sequence=[COLORS["primary"]],
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No sales data available.")
        except Exception:
            st.info("Error loading sales trend.")

    with col2:
        st.markdown("<h3 class='section-header'>Payment Status</h3>", unsafe_allow_html=True)
        try:
            payment_data = analytics.get_payment_distribution()
            if not payment_data.empty:
                fig = px.pie(
                    payment_data,
                    values="amount",
                    names="payment_method",
                    title="Payment Methods Distribution",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No payment data available.")
        except Exception:
            st.info("Error loading payment distribution.")

    # ------------------- RECENT SALES + UPCOMING DEMOS -------------------
    col1, col2 = st.columns(2)

    # Recent Sales
    with col1:
        st.markdown("<h3 class='section-header'>Recent Sales</h3>", unsafe_allow_html=True)
        recent_sales = db.get_dataframe(
            "sales",
            """
            SELECT s.invoice_no, c.name AS customer_name, c.village,
                   s.total_amount, s.sale_date
            FROM sales s
            JOIN customers c ON s.customer_id = c.customer_id
            ORDER BY s.created_date DESC LIMIT 8
            """,
        )
        if not recent_sales.empty:
            st.dataframe(recent_sales, use_container_width=True, hide_index=True)
        else:
            st.info("No recent sales.")

    # Upcoming Demos
    with col2:
        st.markdown("<h3 class='section-header'>Upcoming Demos</h3>", unsafe_allow_html=True)

        upcoming_demos = db.get_dataframe(
            "demos",
            """
            SELECT d.demo_id, c.name AS customer_name, c.village,
                   p.product_name, d.demo_date, d.demo_time
            FROM demos d
            LEFT JOIN customers c ON d.customer_id = c.customer_id
            LEFT JOIN products p ON d.product_id = p.product_id
            WHERE date(d.demo_date) >= date('now')
            AND LOWER(TRIM(d.conversion_status)) = 'scheduled'
            ORDER BY d.demo_date ASC, d.demo_time ASC
            LIMIT 8
            """,
        )

        if not upcoming_demos.empty:
            upcoming_demos.columns = ["Demo ID", "Customer", "Village", "Product", "Date", "Time"]
            st.dataframe(upcoming_demos, use_container_width=True, hide_index=True)

            if st.button("📋 View All Demos"):
                st.session_state.current_page = "demos"
                st.rerun()
        else:
            st.warning("⚠️ No upcoming demos scheduled.")
            if st.button("➕ Schedule a Demo"):
                st.session_state.current_page = "demos"
                st.rerun()
