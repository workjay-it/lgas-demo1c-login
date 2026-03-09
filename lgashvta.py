import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="Domestic Gas Logistics Portal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    [data-testid="stMetric"] { background-color: #1e2129; padding: 20px; border-radius: 10px; border: 1px solid #31333f; }
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stSidebar"] { background-color: #1a2a3a; color: white; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #007bff; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session States
if 'role' not in st.session_state:
    st.session_state.role = None
if 'company_link' not in st.session_state:
    st.session_state.company_link = None

# Initialize Connection
@st.cache_resource
def init_connection():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_connection()

# --- 1.5 LOGIN & REGISTRATION LOGIC ---
def login():
    with st.container():
        st.subheader("Gas Logistics Portal")
        tab_login, tab_reg = st.tabs(["🔑 Login", "📝 Create Account"])
        
        with tab_login:
            user = st.text_input("Username (Full Name)")
            pwd = st.text_input("Password", type="password")
            if st.button("Login"):
                res = supabase.table("profiles").select("*").eq("full_name", user).execute()
                if res.data:
                    user_info = res.data[0]
                    # Note: In production, use hashed password comparison
                    st.session_state.role = user_info['role']
                    st.session_state.company_link = user_info['Client_link']
                    st.success(f"Welcome back, {user}")
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please try again.")

        with tab_reg:
            st.info("📝 Register a new Account")
            reg_role = st.selectbox("I am registering as a:", ["Gas Company", "Test Center"])
            
            col_a, col_b = st.columns(2)
            with col_a:
                new_user = st.text_input("Full Name (Username)")
                new_pwd = st.text_input("Choose Password", type="password")
                confirm_pwd = st.text_input("Verify Password", type="password")
            
            with col_b:
                if reg_role == "Gas Company":
                    new_link = st.selectbox("Select Your Company", ["Indane", "Bharat Gas", "HP Gas", "Industrial Solutions", "LPG Hub Hyderabad"])
                else:
                    new_link = st.text_input("Facility/Yard Name (e.g., North Yard)")
                contact_info = st.text_input("Email or Phone Number")

            if st.button("Register & Create Account"):
                if new_pwd != confirm_pwd:
                    st.error("❌ Passwords do not match.")
                elif not (new_user and new_pwd and new_link):
                    st.warning("⚠️ Please fill in all required fields.")
                else:
                    try:
                        supabase.table("profiles").insert({
                            "full_name": new_user,
                            "role": reg_role,
                            "Client_link": new_link,
                            "updated_at": str(datetime.now())
                        }).execute()
                        st.success("✅ Registration successful! Please switch to Login tab.")
                    except Exception as e:
                        st.error(f"Error: {e}")

if st.session_state.role is None:
    login()
    st.stop()

# --- 2. GLOBAL DATA FETCHING ---
@st.cache_data(ttl=300)
def get_unified_data():
    try:
        b_res = supabase.table("batches").select("*").execute()
        c_res = supabase.table("cylinders").select("*").execute()
        b_df = pd.DataFrame(b_res.data)
        c_df = pd.DataFrame(c_res.data)
        if b_df.empty: return pd.DataFrame()
        if "Batch_ID" in c_df.columns: c_df = c_df.rename(columns={"Batch_ID": "batch_id"})
        b_df["batch_id"] = b_df["batch_id"].astype(str).str.strip().str.upper()
        if not c_df.empty:
            c_df["batch_id"] = c_df["batch_id"].astype(str).str.strip().str.upper()
        return pd.merge(b_df, c_df, on="batch_id", how="left")
    except Exception as e:
        st.error(f"Sync error: {e}")
        return pd.DataFrame()

full_df = get_unified_data()

# --- 3. DYNAMIC NAVIGATION (GOD MODE) ---
st.sidebar.title(f"👤 {st.session_state.role}")
if st.session_state.company_link:
    st.sidebar.caption(f"🏢 {st.session_state.company_link}")

# Define base menu
if st.session_state.role == "Admin":
    st.sidebar.warning("⚡ GOD MODE ACTIVE")
    menu = ["Dashboard", "Bulk Processing (Workers)", "Financial & Billing", "Truck Intake", "Search Unit", "Gas Co Upload"]
elif st.session_state.role == "Gas Company":
    menu = ["Dashboard", "Gas Co Upload", "Search Unit"]
else: # Test Center
    menu = ["Dashboard", "Bulk Processing (Workers)", "Search Unit"]

choice = st.sidebar.radio("Navigation", menu)

if st.sidebar.button("Logout"):
    st.session_state.role = None
    st.session_state.company_link = None
    st.rerun()

# --- PAGE: DASHBOARD ---
if choice == "Dashboard":
    st.header("Fleet Intelligence & Batch Analytics")

    if full_df.empty:
        st.warning("No data found.")
    else:
        # --- GOD MODE LOGIC ---
        if st.session_state.role == "Admin":
            all_companies = ["All Companies"] + sorted([str(c) for c in full_df["company"].unique() if c])
            target_company = st.selectbox("Switch View (God Mode)", all_companies)
            display_df = full_df if target_company == "All Companies" else full_df[full_df["company"] == target_company]
        elif st.session_state.role == "Gas Company":
            target_company = st.session_state.company_link
            display_df = full_df[full_df["company"] == target_company]
            st.info(f"Viewing secure data for: {target_company}")
        else: # Test Center
            display_df = full_df
            st.info(f"📍 Operational View: {st.session_state.company_link}")

        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Trucks in Yard", display_df["batch_id"].nunique())
        m2.metric("Total Cylinders", display_df["Cylinder_ID"].count())
        m3.metric("Damaged Found", (display_df["Status"].astype(str).str.upper() == "DAMAGED").sum())

        # Professional Export Center
        with st.expander("📥 Professional Report Export Center"):
            if st.session_state.role == "Test Center":
                c1, c2 = st.columns(2)
                with c1:
                    todo_df = full_df[full_df["Status"] == "Empty"]
                    st.download_button("📋 Download Job Sheet (Pending)", todo_df.to_csv(index=False).encode('utf-8'), "job_sheet.csv")
                with c2:
                    today_str = str(datetime.now().date())
                    done_df = full_df[full_df["Last_Test_Date"] == today_str]
                    st.download_button("✅ Download Completion Log (Today)", done_df.to_csv(index=False).encode('utf-8'), f"production_{today_str}.csv")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    data_range = st.radio("Select Range", ["Complete", "New (Last 7 Days)", "Historical"], horizontal=True)
                with col2:
                    file_ext = st.selectbox("Format", ["CSV", "Excel", "PDF"])

                # Filtering for range
                if data_range == "New (Last 7 Days)":
                    cutoff = datetime.now() - timedelta(days=7)
                    export_df = display_df[pd.to_datetime(display_df["arrival_time"]) >= cutoff]
                elif data_range == "Historical":
                    cutoff = datetime.now() - timedelta(days=7)
                    export_df = display_df[pd.to_datetime(display_df["arrival_time"]) < cutoff]
                else:
                    export_df = display_df

                if not export_df.empty:
                    st.download_button(f"Download {file_ext} Report", export_df.to_csv(index=False).encode('utf-8'), "report.csv")

        st.markdown("---")
        st.subheader("Summary Table")
        st.dataframe(display_df.head(20), use_container_width=True)


# --- PAGE: BULK PROCESSING ---
elif choice == "Bulk Processing (Workers)":
    st.header("Production Line Triage")
    
    if full_df.empty:
        st.warning("No data found. Register a Batch in 'Truck Intake' first.")
    else:
        # Get unique batch IDs from the master data
        available_batches = sorted(full_df["batch_id"].unique().tolist())
        selected_b = st.selectbox("Select Batch to Work On", available_batches)
        
        # Filter master data for the selected batch
        batch_cyls = full_df[full_df["batch_id"] == selected_b].dropna(subset=["Cylinder_ID"]).copy()
        
        if batch_cyls.empty:
            st.info("No cylinders linked to this batch yet.")
        else:
            edited_df = st.data_editor(
                batch_cyls[["Cylinder_ID", "Status", "Condition_Notes"]],
                column_config={
                    "Status": st.column_config.SelectboxColumn("Result", options=["Full", "Damaged", "Under Maintenance"]),
                    "Condition_Notes": st.column_config.SelectboxColumn("Damage Type", options=[
                        "Good / No Repair", "Valve Leak (Minor)", "Valve Replacement", 
                        "Body Dent Repair", "Re-painting Required", "Foot Ring Straightening", "Condemned"
                    ]),
                    "Cylinder_ID": st.column_config.TextColumn("Cylinder ID", disabled=True),
                },
                hide_index=True, use_container_width=True, key="worker_editor"
            )

            if st.button("Submit Production Data"):
                for _, row in edited_df.iterrows():
                    supabase.table("cylinders").update({
                        "Status": row["Status"],
                        "Condition_Notes": row["Condition_Notes"],
                        "Last_Test_Date": str(datetime.now().date())
                    }).eq("Cylinder_ID", row["Cylinder_ID"]).execute()
                st.success("Cloud Updated Successfully!")
                st.cache_data.clear()
                st.rerun()


# --- PAGE: FINANCIAL & BILLING ---
elif choice == "Financial & Billing":
    st.header("Batch Billing & Cost Analysis")
    RATE_CARD = {
        "Good / No Repair": 0, "Valve Leak (Minor)": 150, "Valve Replacement": 450,
        "Body Dent Repair": 300, "Re-painting Required": 200, "Foot Ring Straightening": 250, "Condemned": 0
    }
    
    if not full_df.empty:
        # Get unique batch IDs from master data
        available_batches = sorted(full_df["batch_id"].unique().tolist())
        target_b = st.selectbox("Select Batch for Billing", available_batches)
        
        # Filter and calculate costs
        batch_data = full_df[full_df["batch_id"] == target_b].dropna(subset=["Cylinder_ID"]).copy()
        batch_data["Cost"] = batch_data["Condition_Notes"].map(RATE_CARD).fillna(0)
        
        c1, c2 = st.columns(2)
        c1.metric("Batch Total Units", len(batch_data))
        c2.metric("Total Repair Bill", f"₹{batch_data['Cost'].sum():,.2f}")
        
        st.dataframe(batch_data[batch_data["Cost"] > 0][["Cylinder_ID", "Condition_Notes", "Cost"]], 
                     use_container_width=True, hide_index=True)
    else:
        st.info("No data available for billing.")


# --- PAGE: TRUCK INTAKE ---
elif choice == "Truck Intake":
    st.header("New Truck Arrival")
    companies = ["Indane", "Bharat Gas", "HP Gas", "Industrial Solutions", "LPG Hub Hyderabad"]
    
    with st.form("truck_entry", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            new_batch = st.text_input("New Batch ID (e.g., BATCH017)")
            selected_company = st.selectbox("Company Name", companies)
        with col2:
            truck_no = st.text_input("Truck Plate Number")
            driver = st.text_input("Driver Name")
            
        if st.form_submit_button("Confirm Arrival"):
            clean_batch_id = new_batch.strip().upper()
            if clean_batch_id:
                try:
                    supabase.table("batches").insert({
                        "batch_id": clean_batch_id,
                        "company": selected_company,
                        "truck_number": truck_no.strip().upper(),
                        "driver_name": driver.strip().title(),
                        "arrival_time": str(datetime.now())
                    }).execute()
                    st.cache_data.clear()
                    st.success(f"Batch {clean_batch_id} registered successfully.")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Please enter a Batch ID.")


# --- PAGE: SEARCH ---
elif choice == "Search Unit":
    st.header("Search Inventory")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        search_type = st.selectbox("Search By", ["Cylinder ID", "Batch ID", "Truck Plate"])
    with col2:
        query = st.text_input(f"Enter {search_type}").strip().upper()

    if query:
        if full_df.empty:
            st.warning("No data available.")
        else:
            # Flexible searching using .str.contains()
            if search_type == "Cylinder ID":
                results = full_df[full_df["Cylinder_ID"].astype(str).str.upper().str.contains(query, na=False)]
            elif search_type == "Batch ID":
                results = full_df[full_df["batch_id"].astype(str).str.upper().str.contains(query, na=False)]
            elif search_type == "Truck Plate":
                results = full_df[full_df["truck_number"].astype(str).str.upper().str.contains(query, na=False)]

            if not results.empty:
                st.success(f"Found {len(results)} matching record(s).")
                
                if search_type != "Cylinder ID":
                    first = results.iloc[0]
                    st.info(f"Company: {first.get('company', 'N/A')} | Driver: {first.get('driver_name', 'N/A')}")
                
                st.dataframe(results, use_container_width=True, hide_index=True, height=400)
            else:
                st.info(f"No records found containing: {query}")

# --- PAGE: GAS CO UPLOAD ---
elif choice == "Gas Co Upload":
    st.header("📤 Add Cylinder Manifest")
    st.write("Choose your preferred method to add cylinders to the system.")

    # Create three tabs for the three different methods
    tab1, tab2, tab3 = st.tabs(["📄 CSV Bulk Upload", "⌨️ Manual Entry", "📸 Scan Barcode"])

    # --- TAB 1: CSV UPLOAD ---
    with tab1:
        st.subheader("Bulk Upload via CSV")
        uploaded_file = st.file_uploader("Upload Company CSV Manifest", type="csv", key="csv_up")
        if uploaded_file:
            upload_df = pd.read_csv(uploaded_file)
            if st.button("🚀 Confirm CSV Upload"):
                try:
                    upload_df["batch_id"] = upload_df["batch_id"].astype(str).str.strip().str.upper()
                    data_to_insert = upload_df.to_dict(orient='records')
                    supabase.table("cylinders").insert(data_to_insert).execute()
                    st.success(f"Successfully uploaded {len(upload_df)} cylinders!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- TAB 2: MANUAL ENTRY ---
    with tab2:
        st.subheader("Single Unit Entry")
        with st.form("manual_entry_form"):
            col1, col2 = st.columns(2)
            new_id = col1.text_input("Cylinder ID (Serial No)").strip().upper()
            new_batch = col2.text_input("Batch ID (Assignment)").strip().upper()
            test_due = st.date_input("Next Test Due Date")
            
            if st.form_submit_button("➕ Add Single Cylinder"):
                if new_id and new_batch:
                    try:
                        supabase.table("cylinders").insert({
                            "Cylinder_ID": new_id,
                            "batch_id": new_batch,
                            "Next_Test_Due": str(test_due),
                            "Status": "Empty" # Default status
                        }).execute()
                        st.success(f"Cylinder {new_id} added to Batch {new_batch}")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Please fill in both ID and Batch fields.")

    # --- TAB 3: SCANNING ---
    with tab3:
        st.subheader("Mobile Scanner")
        st.info("Point your camera at the cylinder's barcode or QR code.")
        
        # Streamlit's built-in camera input
        img_file = st.camera_input("Take a photo of the barcode")
        
        # Note: Professional barcode decoding usually requires an external library like 'pyzbar' 
        # or 'opencv', but you can manually type the ID here after seeing the photo 
        # as a 'visual verification' step for now.
        if img_file:
            st.success("Photo captured! Enter the ID seen in the photo below:")
            scanned_id = st.text_input("Verified ID from Photo").strip().upper()
            scanned_batch = st.text_input("Batch to Assign to", key="scan_batch").strip().upper()
            
            if st.button("Confirm Scanned Entry"):
                if scanned_id and scanned_batch:
                    supabase.table("cylinders").insert({
                        "Cylinder_ID": scanned_id,
                        "batch_id": scanned_batch,
                        "Status": "Empty"
                    }).execute()
                    st.success("Scanned unit registered!")
                    st.cache_data.clear()


























































































