# pages/demos.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time


def show_demos_page(db, whatsapp_manager=None):
    """Show demo management and tracking page"""
    st.title("🎯 Demo Management Center")

    if not db:
        st.error("Database not available. Please check initialization.")
        return

    # Tabs for different demo functions
    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Schedule Demo", "📋 Demo Calendar", "📊 Demo Analytics", "🔄 Follow-ups"]
    )

    with tab1:
        show_schedule_demo_tab(db, whatsapp_manager)

    with tab2:
        show_demo_calendar_tab(db)

    with tab3:
        show_demo_analytics_tab(db)

    with tab4:
        show_follow_ups_tab(db, whatsapp_manager)


def show_schedule_demo_tab(db, whatsapp_manager):
    """Show form to schedule new demos"""
    st.subheader("➕ Schedule New Demo")

    # Show demo summary if we just created one
    if "last_demo_id" in st.session_state and st.session_state.last_demo_id:
        show_demo_summary(db, st.session_state.last_demo_id)
        st.session_state.last_demo_id = None  # Clear after showing
        st.divider()

    with st.form("schedule_demo_form"):
        st.markdown("### 👥 Demo Information")

        col1, col2 = st.columns(2)

        with col1:
            # Customer selection
            customers = db.get_dataframe(
                "customers", "SELECT customer_id, name, village FROM customers"
            )
            if not customers.empty:
                customer_options = {
                    f"{row['name']} ({row['village']})": row["customer_id"]
                    for _, row in customers.iterrows()
                }
                selected_customer = st.selectbox(
                    "Select Customer*", options=list(customer_options.keys())
                )
                customer_id = (
                    customer_options[selected_customer] if selected_customer else None
                )
            else:
                st.warning("No customers found. Please add customers first.")
                customer_id = None

            # Distributor selection
            distributors = db.get_dataframe(
                "distributors", "SELECT distributor_id, name, village FROM distributors"
            )
            if not distributors.empty:
                distributor_options = {
                    f"{row['name']} ({row['village']})": row["distributor_id"]
                    for _, row in distributors.iterrows()
                }
                selected_distributor = st.selectbox(
                    "Assign Distributor",
                    options=[""] + list(distributor_options.keys()),
                )
                distributor_id = (
                    distributor_options[selected_distributor]
                    if selected_distributor
                    else None
                )
            else:
                distributor_id = None

        with col2:
            # Product selection
            products = db.get_dataframe(
                "products",
                "SELECT product_id, product_name FROM products WHERE is_active = 1",
            )
            if not products.empty:
                product_options = {
                    row["product_name"]: row["product_id"]
                    for _, row in products.iterrows()
                }
                selected_product = st.selectbox(
                    "Product to Demo*", options=list(product_options.keys())
                )
                product_id = (
                    product_options[selected_product] if selected_product else None
                )
            else:
                st.warning("No products found. Please add products first.")
                product_id = None

            # Demo details
            demo_date = st.date_input("Demo Date*", datetime.now().date())
            demo_time = st.time_input("Demo Time", datetime.now().time())

        st.markdown("### 📝 Demo Details")

        col1, col2 = st.columns(2)

        with col1:
            quantity_provided = st.number_input(
                "Quantity Provided",
                min_value=0,
                value=1,
                help="Number of units provided for demo",
            )
            demo_location = st.selectbox(
                "Demo Location",
                ["Customer Home", "Distributor Office", "Public Place", "Other"],
            )

        with col2:
            follow_up_date = st.date_input(
                "Follow-up Date", datetime.now().date() + timedelta(days=7)
            )
            conversion_status = st.selectbox(
                "Initial Status", ["Scheduled", "Completed", "Cancelled"]
            )

        notes = st.text_area(
            "Demo Notes",
            placeholder="Any special instructions, customer requirements, or observations...",
        )

        # Submit button
        submitted = st.form_submit_button(
            "🎯 Schedule Demo",
            type="primary",
        )

    # Handle form submission OUTSIDE the form to prevent resubmission
    if submitted:
        # Create unique submission ID to prevent duplicates
        submission_id = f"{customer_id}_{product_id}_{demo_date}_{demo_time}_{int(time.time())}"
        
        # Initialize submission tracking if not exists
        if "processed_submissions" not in st.session_state:
            st.session_state.processed_submissions = set()
        
        # Check if this exact submission was already processed in this session
        if submission_id in st.session_state.processed_submissions:
            st.warning("⚠️ This demo was already submitted. Showing previously created demo.")
            # Don't rerun, just show the existing demo
        else:
            # Validation
            errors = []
            if not customer_id:
                errors.append("Customer selection is required")
            if not product_id:
                errors.append("Product selection is required")
            if not demo_date:
                errors.append("Demo date is required")

            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                # Check if a similar demo already exists in database (within last 5 minutes)
                try:
                    recent_demos = db.get_dataframe(
                        "demos",
                        """
                        SELECT demo_id FROM demos 
                        WHERE customer_id = ? 
                        AND product_id = ? 
                        AND demo_date = ?
                        AND created_date >= datetime('now', '-5 minutes')
                        ORDER BY demo_id DESC LIMIT 1
                        """,
                        params=(customer_id, product_id, demo_date)
                    )
                    
                    if not recent_demos.empty:
                        existing_demo_id = recent_demos.iloc[0]['demo_id']
                        st.warning(f"⚠️ A similar demo (ID: {existing_demo_id}) was already created recently. Showing that demo instead.")
                        st.session_state.last_demo_id = existing_demo_id
                        st.session_state.processed_submissions.add(submission_id)
                        st.rerun()
                        return
                except Exception as check_error:
                    st.warning(f"Could not check for existing demos: {check_error}")
                
                try:
                    # Ensure demo_date is a single date object (not tuple)
                    if isinstance(demo_date, tuple):
                        demo_date = demo_date[0] if demo_date else datetime.now().date()
                    
                    # Ensure follow_up_date is a single date object
                    if isinstance(follow_up_date, tuple):
                        follow_up_date = follow_up_date[0] if follow_up_date else datetime.now().date() + timedelta(days=7)

                    # Combine date and time for notification
                    demo_datetime = datetime.combine(demo_date, demo_time)

                    # Add demo to database
                    demo_id = add_demo_to_database(
                        db,
                        {
                            "customer_id": customer_id,
                            "distributor_id": distributor_id,
                            "product_id": product_id,
                            "demo_date": demo_date,
                            "demo_time": demo_time,
                            "quantity_provided": quantity_provided,
                            "follow_up_date": follow_up_date,
                            "conversion_status": conversion_status,
                            "notes": notes,
                            "demo_location": demo_location,
                        },
                    )

                    if demo_id and demo_id > 0:
                        # Mark this submission as processed
                        st.session_state.processed_submissions.add(submission_id)
                        
                        st.success(
                            f"✅ Demo scheduled successfully! Demo ID: {demo_id}"
                        )

                        # Send notification if WhatsApp available
                        if whatsapp_manager and customer_id:
                            send_demo_notification(
                                whatsapp_manager,
                                db,
                                customer_id,
                                demo_datetime,
                                product_id,
                            )

                        # Store demo_id in session state to show summary outside form
                        st.session_state.last_demo_id = demo_id

                        # Set flag for dashboard notification
                        st.session_state.demo_created_notification = demo_id

                        # Update refresh time to ensure dashboard shows latest demos
                        st.session_state.demo_refresh_time = time.time()

                        # Rerun to show summary
                        st.rerun()

                    else:
                        st.error("❌ Failed to schedule demo. Please try again.")

                except Exception as e:
                    st.error(f"❌ Error scheduling demo: {e}")
                    import traceback
                    st.code(traceback.format_exc())


def add_demo_to_database(db, demo_data):
    """Add demo record to database"""
    try:
        # Insert the demo - execute_query returns [(lastrowid,)] for INSERT
        result = db.execute_query(
            """
        INSERT INTO demos (customer_id, distributor_id, product_id, demo_date, demo_time,
                          quantity_provided, follow_up_date, conversion_status, notes, demo_location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                demo_data["customer_id"],
                demo_data["distributor_id"],
                demo_data["product_id"],
                demo_data["demo_date"],
                demo_data["demo_time"].strftime("%H:%M:%S")
                if demo_data.get("demo_time")
                else None,
                demo_data["quantity_provided"],
                demo_data["follow_up_date"],
                demo_data["conversion_status"],
                demo_data["notes"],
                demo_data["demo_location"],
            ),
            log_action=False,
        )
        
        # The execute_query method returns [(lastrowid,)] for INSERT queries
        demo_id = result[0][0] if result and len(result) > 0 and result[0][0] else None
        
        if demo_id:
            return demo_id
        else:
            st.error("❌ Failed to get demo_id after insertion")
            return -1

    except Exception as e:
        st.error(f"Database error: {e}")
        import traceback
        st.code(traceback.format_exc())
        return -1


def send_demo_notification(
    whatsapp_manager, db, customer_id, demo_datetime, product_id
):
    """Send demo notification to customer"""
    try:
        # Get customer and product details
        customer = db.get_dataframe(
            "customers", f"SELECT * FROM customers WHERE customer_id = {customer_id}"
        )
        product = db.get_dataframe(
            "products", f"SELECT * FROM products WHERE product_id = {product_id}"
        )

        if not customer.empty and not product.empty:
            customer_data = customer.iloc[0]
            product_data = product.iloc[0]

            if customer_data.get("mobile"):
                # Format time safely
                time_str = demo_datetime.strftime("%I:%M %p")
                
                message = f"""Hello {customer_data["name"]}! 🎉

We're excited to confirm your product demo!

📅 Date: {demo_datetime.strftime("%d %b %Y")}
⏰ Time: {time_str}
📦 Product: {product_data["product_name"]}

Our team will demonstrate the product features and answer any questions you may have.

We look forward to meeting you!

Best regards,
Sales Team"""

                success = whatsapp_manager.send_message(
                    customer_data["mobile"], message
                )
                if success:
                    st.success("📱 Demo notification sent to customer!")
                else:
                    st.warning("⚠️ Could not send demo notification")

    except Exception as e:
        st.warning(f"Could not send demo notification: {e}")


def show_demo_summary(db, demo_id):
    """Show summary of scheduled demo"""
    try:
        demo_data = db.get_dataframe(
            "demos",
            f"""
        SELECT d.*, c.name as customer_name, c.village, p.product_name,
               dist.name as distributor_name
        FROM demos d
        LEFT JOIN customers c ON d.customer_id = c.customer_id
        LEFT JOIN products p ON d.product_id = p.product_id
        LEFT JOIN distributors dist ON d.distributor_id = dist.distributor_id
        WHERE d.demo_id = {demo_id}
        """,
        )

        if not demo_data.empty:
            demo = demo_data.iloc[0]

            st.markdown("## 🎉 Demo Scheduled Successfully!")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("👥 Demo Details")
                st.write(f"**Demo ID:** {demo_id}")
                st.write(f"**Customer:** {demo['customer_name']}")
                st.write(f"**Village:** {demo['village']}")
                st.write(f"**Product:** {demo['product_name']}")
                if demo.get("distributor_name"):
                    st.write(f"**Distributor:** {demo['distributor_name']}")

            with col2:
                st.subheader("📅 Schedule")
                st.write(f"**Demo Date:** {demo['demo_date']}")
                if demo.get("demo_time"):
                    st.write(f"**Demo Time:** {demo['demo_time']}")
                st.write(f"**Follow-up Date:** {demo['follow_up_date']}")
                st.write(f"**Status:** {demo['conversion_status']}")

            # Quick actions
            st.markdown("### ⚡ Quick Actions")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("🏠 Go to Dashboard"):
                    st.session_state.current_page = "dashboard"
                    st.rerun()

            with col2:
                if st.button("📋 View All Demos"):
                    st.session_state.current_tab = "📋 Demo Calendar"
                    st.rerun()

            with col3:
                if st.button("➕ Schedule Another"):
                    st.rerun()

            with col4:
                if st.button("📊 View Analytics"):
                    st.session_state.current_tab = "📊 Demo Analytics"
                    st.rerun()

    except Exception as e:
        st.error(f"Error displaying demo summary: {e}")


def show_demo_calendar_tab(db):
    """Show demo calendar and upcoming demos"""
    st.subheader("📋 Demo Calendar & Schedule")

    try:
        # Date range filter
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.now().date())
        with col2:
            end_date = st.date_input("End Date", datetime.now().date() + timedelta(days=30))

        # Status filter
        status_filter = st.multiselect(
            "Filter by Status",
            ["Scheduled", "Completed", "Cancelled", "Converted", "Not Converted"],
            default=["Scheduled", "Completed"],
        )

        # Get demos data
        demos_data = get_demos_data(db, start_date, end_date, status_filter)

        if not demos_data.empty:
            # Convert demo_date to datetime for comparison
            demos_data["demo_date"] = pd.to_datetime(demos_data["demo_date"]).dt.date

            st.write(f"**📅 Showing {len(demos_data)} demos**")

            # Upcoming demos (next 7 days)
            upcoming_demos = demos_data[
                (demos_data["demo_date"] <= datetime.now().date() + timedelta(days=7))
                & (demos_data["conversion_status"] == "Scheduled")
            ]

            if not upcoming_demos.empty:
                st.subheader("🚀 Upcoming Demos (Next 7 Days)")
                display_upcoming = upcoming_demos[
                    [
                        "demo_date",
                        "customer_name",
                        "village",
                        "product_name",
                        "distributor_name",
                    ]
                ].copy()
                display_upcoming.columns = [
                    "Date",
                    "Customer",
                    "Village",
                    "Product",
                    "Distributor",
                ]
                st.dataframe(display_upcoming, use_container_width=True)

            # All demos in date range
            st.subheader("📋 All Demos")
            display_all = demos_data[
                [
                    "demo_date",
                    "customer_name",
                    "village",
                    "product_name",
                    "conversion_status",
                    "distributor_name",
                ]
            ].copy()
            display_all.columns = [
                "Date",
                "Customer",
                "Village",
                "Product",
                "Status",
                "Distributor",
            ]
            display_all = display_all.sort_values("Date", ascending=False)
            st.dataframe(display_all, use_container_width=True)

            # Demo statistics
            st.subheader("📊 Demo Statistics")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                total_demos = len(demos_data)
                st.metric("Total Demos", total_demos)

            with col2:
                scheduled = len(
                    demos_data[demos_data["conversion_status"] == "Scheduled"]
                )
                st.metric("Scheduled", scheduled)

            with col3:
                completed = len(
                    demos_data[demos_data["conversion_status"] == "Completed"]
                )
                st.metric("Completed", completed)

            with col4:
                converted = len(
                    demos_data[demos_data["conversion_status"] == "Converted"]
                )
                st.metric("Converted", converted)

        else:
            st.info("No demos found for the selected criteria.")

    except Exception as e:
        st.error(f"Error loading demo calendar: {e}")
        import traceback
        st.code(traceback.format_exc())


def get_demos_data(db, start_date, end_date, status_filter):
    """Get demos data with filters"""
    try:
        query = """
        SELECT d.*, c.name as customer_name, c.village, c.mobile,
               p.product_name, dist.name as distributor_name
        FROM demos d
        LEFT JOIN customers c ON d.customer_id = c.customer_id
        LEFT JOIN products p ON d.product_id = p.product_id
        LEFT JOIN distributors dist ON d.distributor_id = dist.distributor_id
        WHERE d.demo_date BETWEEN ? AND ?
        """

        params = [start_date, end_date]

        if status_filter:
            placeholders = ",".join(["?" for _ in status_filter])
            query += f" AND d.conversion_status IN ({placeholders})"
            params.extend(status_filter)

        query += " ORDER BY d.demo_date, d.demo_time"

        return db.get_dataframe("demos", query, params=params)

    except Exception as e:
        st.error(f"Error getting demos data: {e}")
        return pd.DataFrame()


def show_demo_analytics_tab(db):
    """Show demo analytics and conversion rates"""
    st.subheader("📊 Demo Analytics")

    try:
        # Get demo conversion data
        demos_data = db.get_dataframe(
            "demos",
            """
        SELECT d.*, c.name as customer_name, c.village,
               p.product_name, dist.name as distributor_name
        FROM demos d
        LEFT JOIN customers c ON d.customer_id = c.customer_id
        LEFT JOIN products p ON d.product_id = p.product_id
        LEFT JOIN distributors dist ON d.distributor_id = dist.distributor_id
        ORDER BY d.demo_date DESC
        """,
        )

        if not demos_data.empty:
            # Convert demo_date to datetime for proper handling
            demos_data["demo_date"] = pd.to_datetime(demos_data["demo_date"])

            # Conversion statistics
            st.subheader("🎯 Conversion Analytics")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                total_demos = len(demos_data)
                st.metric("Total Demos", total_demos)

            with col2:
                converted = len(
                    demos_data[demos_data["conversion_status"] == "Converted"]
                )
                st.metric("Converted", converted)

            with col3:
                not_converted = len(
                    demos_data[demos_data["conversion_status"] == "Not Converted"]
                )
                st.metric("Not Converted", not_converted)

            with col4:
                conversion_rate = (
                    (converted / total_demos * 100) if total_demos > 0 else 0
                )
                st.metric("Conversion Rate", f"{conversion_rate:.1f}%")

            # Product-wise conversion
            st.subheader("📦 Product Performance")
            if "product_name" in demos_data.columns:
                product_stats = (
                    demos_data.groupby("product_name")
                    .agg(
                        {
                            "demo_id": "count",
                            "conversion_status": lambda x: (x == "Converted").sum(),
                        }
                    )
                    .reset_index()
                )
                product_stats.columns = ["Product", "Total Demos", "Converted"]
                product_stats["Conversion Rate"] = (
                    product_stats["Converted"] / product_stats["Total Demos"] * 100
                ).round(1)
                product_stats = product_stats.sort_values(
                    "Total Demos", ascending=False
                )

                st.dataframe(product_stats, use_container_width=True)

            # Monthly trend
            st.subheader("📈 Monthly Demo Trend")
            try:
                demos_data["demo_date"] = pd.to_datetime(demos_data["demo_date"])
                monthly_trend = demos_data.groupby(
                    demos_data["demo_date"].dt.to_period("M")
                ).size()
                monthly_trend.index = monthly_trend.index.astype(str)

                if not monthly_trend.empty:
                    fig = px.line(
                        x=monthly_trend.index,
                        y=monthly_trend.values,
                        title="Monthly Demo Trend",
                        labels={"x": "Month", "y": "Number of Demos"},
                    )
                    st.plotly_chart(fig, use_container_width=True)
            except:
                st.info("Could not generate monthly trend chart")

        else:
            st.info("No demo data available for analytics.")

    except Exception as e:
        st.error(f"Error loading demo analytics: {e}")


def show_follow_ups_tab(db, whatsapp_manager):
    """Show demo follow-ups and conversion tracking"""
    st.subheader("🔄 Demo Follow-ups")

    try:
        # Get demos needing follow-up
        follow_up_data = db.get_dataframe(
            "demos",
            """
        SELECT d.*, c.name as customer_name, c.mobile, c.village,
               p.product_name, dist.name as distributor_name
        FROM demos d
        LEFT JOIN customers c ON d.customer_id = c.customer_id
        LEFT JOIN products p ON d.product_id = p.product_id
        LEFT JOIN distributors dist ON d.distributor_id = dist.distributor_id
        WHERE d.follow_up_date <= date('now', '+7 days')
        AND d.conversion_status IN ('Completed', 'Not Converted')
        ORDER BY d.follow_up_date ASC
        """,
        )

        if not follow_up_data.empty:
            # Convert dates to datetime for comparison
            follow_up_data["follow_up_date"] = pd.to_datetime(
                follow_up_data["follow_up_date"]
            ).dt.date

            # Overdue follow-ups
            overdue = follow_up_data[
                follow_up_data["follow_up_date"] < datetime.now().date()
            ]
            if not overdue.empty:
                st.warning(f"🚨 {len(overdue)} Overdue Follow-ups!")
                display_overdue = overdue[
                    [
                        "follow_up_date",
                        "customer_name",
                        "village",
                        "product_name",
                        "conversion_status",
                    ]
                ].copy()
                display_overdue.columns = [
                    "Due Date",
                    "Customer",
                    "Village",
                    "Product",
                    "Status",
                ]
                st.dataframe(display_overdue, use_container_width=True)

            # Upcoming follow-ups
            upcoming = follow_up_data[
                follow_up_data["follow_up_date"] >= datetime.now().date()
            ]
            if not upcoming.empty:
                st.subheader("📅 Upcoming Follow-ups")
                display_upcoming = upcoming[
                    [
                        "follow_up_date",
                        "customer_name",
                        "village",
                        "product_name",
                        "conversion_status",
                    ]
                ].copy()
                display_upcoming.columns = [
                    "Due Date",
                    "Customer",
                    "Village",
                    "Product",
                    "Status",
                ]
                st.dataframe(display_upcoming, use_container_width=True)

            # Follow-up actions
            st.subheader("🔄 Follow-up Actions")
            selected_demo = st.selectbox(
                "Select Demo for Follow-up",
                options=[
                    f"{row['customer_name']} - {row['product_name']} ({row['follow_up_date']})"
                    for _, row in follow_up_data.iterrows()
                ],
            )

            if selected_demo:
                demo_index = [
                    f"{row['customer_name']} - {row['product_name']} ({row['follow_up_date']})"
                    for _, row in follow_up_data.iterrows()
                ].index(selected_demo)
                selected_demo_data = follow_up_data.iloc[demo_index]

                col1, col2 = st.columns(2)

                with col1:
                    new_status = st.selectbox(
                        "Update Conversion Status",
                        ["Converted", "Not Converted", "Follow-up Required", "Lost"],
                    )

                    if st.button("🔄 Update Status"):
                        update_demo_status(
                            db, selected_demo_data["demo_id"], new_status
                        )
                        st.success("✅ Status updated successfully!")
                        st.rerun()

                with col2:
                    if whatsapp_manager and st.button("📱 Send Follow-up Message"):
                        send_follow_up_message(whatsapp_manager, selected_demo_data)
                        st.success("✅ Follow-up message sent!")

        else:
            st.success("🎉 No pending follow-ups! All demos are up to date.")

    except Exception as e:
        st.error(f"Error loading follow-ups: {e}")


def update_demo_status(db, demo_id, new_status):
    """Update demo conversion status"""
    try:
        db.execute_query(
            """
        UPDATE demos SET conversion_status = ?, updated_date = CURRENT_TIMESTAMP
        WHERE demo_id = ?
        """,
            (new_status, demo_id),
            log_action=False,
        )
    except Exception as e:
        st.error(f"Error updating demo status: {e}")


def send_follow_up_message(whatsapp_manager, demo_data):
    """Send follow-up message for demo"""
    try:
        if demo_data.get("mobile"):
            message = f"""Hello {demo_data["customer_name"]}! 👋

Following up on your {demo_data["product_name"]} demo from {demo_data["demo_date"]}.

We'd love to hear about your experience and answer any questions you may have.

Would you be interested in placing an order or scheduling another demo?

Best regards,
Sales Team"""

            success = whatsapp_manager.send_message(demo_data["mobile"], message)
            return success
        return False
    except Exception as e:
        st.error(f"Error sending follow-up message: {e}")
        return False
