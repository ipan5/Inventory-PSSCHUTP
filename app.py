import streamlit as st
import database as db
import pandas as pd

# Initialize database
db.create_tables()

st.set_page_config(page_title="Inventory Portal", layout="wide")

# --- ADMIN LOGIN SIDEBAR ---
with st.sidebar:
    st.header("Admin Access")
    admin_password = st.text_input("Enter Password", type="password")

# --- INVENTORY CALCULATION ---
items_df = db.get_all_items()
pending_df = db.get_requests('Pending')
approved_df = db.get_requests('Approved')

display_df = pd.DataFrame()
if not items_df.empty:
    dashboard_df = items_df.copy()
    
    out_qty = approved_df.groupby('item_id')['quantity'].sum() if not approved_df.empty else pd.Series(dtype=int)
    pending_qty = pending_df.groupby('item_id')['quantity'].sum() if not pending_df.empty else pd.Series(dtype=int)
    
    dashboard_df['out'] = dashboard_df['id'].map(out_qty).fillna(0)
    dashboard_df['pending'] = dashboard_df['id'].map(pending_qty).fillna(0)
    dashboard_df['Available'] = dashboard_df['total_quantity'] - dashboard_df['out'] - dashboard_df['pending']
    
    display_df = dashboard_df[['id', 'item_name', 'category', 'location', 'Available', 'total_quantity']]

# ==========================================
# VIEW 1: ADMIN DASHBOARD
# ==========================================
if admin_password == "admin123": 
    st.title("🛡️ Admin Dashboard")
    
    # Notification Banner if there are pending requests
    if not pending_df.empty:
        st.warning(f"🔔 **Notification:** You have {len(pending_df)} pending visitor request(s) waiting for your approval in the 'Action Required' tab!")

    tab1, tab2, tab3, tab4 = st.tabs(["Action Required", "Active Inventory", "Existing Inventory", "Settings & Add Items"])
    
    with tab1:
        st.subheader("Pending Requests")
        if not pending_df.empty:
            for index, row in pending_df.iterrows():
                with st.container(border=True):
                    st.write(f"⏱️ **Requested at:** {row['request_time']}")
                    st.write(f"👤 **Borrower:** {row['borrower_name']} | 📞 **Phone:** {row['phone_number']}")
                    st.write(f"📦 **Requested:** {row['quantity']}x **{row['item_name']}** (Location: {row['location']})")
                    
                    col1, col2 = st.columns([1, 10])
                    with col1:
                        if st.button("✅ Approve", key=f"app_{row['request_id']}"):
                            db.approve_request(row['request_id'])
                            st.rerun()
                    with col2:
                        if st.button("❌ Reject", key=f"rej_{row['request_id']}"):
                            db.reject_request(row['request_id'])
                            st.rerun()
        else:
            st.info("No pending requests.")

    with tab2:
        st.subheader("Items Currently Picked Up (Grouped by Category)")
        if not approved_df.empty:
            # Group active checkouts by category
            approved_categories = approved_df['category'].unique()
            for cat in approved_categories:
                with st.expander(f"📁 {cat}", expanded=True):
                    cat_approved = approved_df[approved_df['category'] == cat]
                    for index, row in cat_approved.iterrows():
                        with st.container(border=True):
                            st.write(f"⏱️ **Picked up at:** {row['approved_time']}")
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.write(f"**{row['borrower_name']}** (📞 {row['phone_number']}) has **{row['quantity']}x {row['item_name']}** | *Location: {row['location']}*")
                            with col2:
                                if st.button("Mark Returned", key=f"ret_{row['request_id']}"):
                                    db.return_request(row['request_id'])
                                    st.success("Returned!")
                                    st.rerun()
        else:
            st.info("All items are currently in storage.")
            
    with tab3:
        st.subheader("Master Inventory List & Quick Management")
        if not display_df.empty:
            master_categories = display_df['category'].unique()
            for cat in master_categories:
                with st.expander(f"📁 {cat}", expanded=True):
                    cat_data = display_df[display_df['category'] == cat]
                    
                    for index, row in cat_data.iterrows():
                        cols = st.columns([3, 1, 1, 1, 1, 1])
                        with cols[0]:
                            st.write(f"**{row['item_name']}** (Loc: *{row['location']}*)")
                        with cols[1]:
                            st.write(f"Total: {row['total_quantity']}")
                        with cols[2]:
                            st.write(f"Avail: {row['Available']}")
                        with cols[3]:
                            if st.button("➕ Add 1", key=f"add_{row['id']}"):
                                db.update_item_quantity(row['id'], 1)
                                st.rerun()
                        with cols[4]:
                            if st.button("➖ Red. 1", key=f"sub_{row['id']}"):
                                db.update_item_quantity(row['id'], -1)
                                st.rerun()
                        with cols[5]:
                            if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                                db.delete_item(row['id'])
                                st.success(f"Deleted {row['item_name']}")
                                st.rerun()
                                
                        # --- NEW: Location Move / Split Sub-form ---
                        with st.expander(f"📍 Change location for {row['item_name']} ({row['location']})"):
                            with st.form(key=f"move_form_{row['id']}"):
                                m_col1, m_col2, m_col3 = st.columns(3)
                                with m_col1:
                                    target_loc = st.selectbox("New Location", ["MAR", "Rumah Abg Meor", "Office"], key=f"tloc_{row['id']}")
                                with m_col2:
                                    # Limit max quantity to what's currently owned
                                    move_qty = st.number_input("Quantity to Move", min_value=1, max_value=int(row['total_quantity']), value=1, key=f"mqty_{row['id']}")
                                with m_col3:
                                    st.write("") # spacing
                                    st.write("")
                                    submit_move = st.form_submit_button("Confirm Move")
                                    
                                if submit_move:
                                    if target_loc == row['location']:
                                        st.warning("The item is already at this location!")
                                    else:
                                        db.split_or_move_item_location(row['id'], target_loc, move_qty)
                                        st.success(f"Successfully moved {move_qty}x {row['item_name']} to {target_loc}!")
                                        st.rerun()
                        st.divider()
        else:
            st.info("No items in database.")
            
    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Register New Item")
            with st.form("new_item"):
                name = st.text_input("Item Name")
                cat = st.selectbox("Category", db.get_categories())
                loc = st.selectbox("Location", ["MAR", "Rumah Abg Meor", "Office"])
                qty = st.number_input("Total Quantity", min_value=1)
                
                if st.form_submit_button("Add to Database") and name:
                    db.add_item(name, cat, loc, qty)
                    st.success(f"'{name}' added to {loc}!")
                    st.rerun()
                    
        with col2:
            st.subheader("Add New Category")
            with st.form("new_category"):
                new_cat_name = st.text_input("New Category Name")
                if st.form_submit_button("Create Category") and new_cat_name:
                    db.add_category(new_cat_name)
                    st.success(f"Category '{new_cat_name}' created!")
                    st.rerun()

# ==========================================
# VIEW 2: TEAM REQUEST PAGE
# ==========================================
else:
    st.title("📦 Equipment Request Portal")
    
    if not display_df.empty:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Available Items by Category")
            unique_categories = display_df['category'].unique()
            
            for category in unique_categories:
                with st.expander(f"📁 {category}", expanded=True):
                    category_data = display_df[display_df['category'] == category]
                    st.dataframe(
                        category_data[['item_name', 'location', 'Available']], 
                        hide_index=True, 
                        use_container_width=True
                    )
            
        with col2:
            st.subheader("Submit a Request")
            with st.form("request_form"):
                # Clean dropdown showing ONLY item names (with location mapping in the backend)
                options_dict = {}
                for index, row in display_df.iterrows():
                    # If multiple items share the same name, we distinguish them or list them cleanly
                    label = f"{row['item_name']} ({row['location']} - {row['Available']} left)"
                    options_dict[label] = (row['id'], row['Available'])
                
                selected_label = st.selectbox("Select Item", list(options_dict.keys()))
                req_name = st.text_input("Your Name")
                req_phone = st.text_input("Phone Number")
                req_qty = st.number_input("Quantity Needed", min_value=1)
                
                if st.form_submit_button("Request Item"):
                    item_id, available_qty = options_dict[selected_label]
                    
                    if req_name == "":
                        st.error("Please enter your name.")
                    elif req_phone == "":
                        st.error("Please enter your phone number.")
                    elif req_qty > available_qty:
                        st.error(f"Only {available_qty} available. Please reduce quantity.")
                    else:
                        db.log_request(item_id, req_name, req_phone, req_qty)
                        st.success("Request submitted successfully! Waiting for admin approval.")
    else:
        st.warning("The inventory is currently empty. Please contact the administrator.")