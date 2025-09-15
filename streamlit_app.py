import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
from fb_mapper import transform, VALID, OBJ_DEFAULTS

# Page configuration
st.set_page_config(
    page_title="Meta Ads Bulk Upload Builder", 
    page_icon="📱", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1877f2 0%, #42a5f5 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .campaign-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1877f2;
        margin: 1rem 0;
    }
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
    }
    .error-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        padding: 1rem;
        border-radius: 8px;
        color: #856404;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 1rem;
        border-radius: 8px;
        color: #155724;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>🚀 Meta Ads Bulk Upload Builder</h1>
    <p>Transform your campaign data into Meta-ready bulk upload files with smart defaults and validation</p>
</div>
""", unsafe_allow_html=True)

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Quick Settings")
    
    # Campaign defaults
    st.subheader("Campaign Defaults")
    default_objective = st.selectbox(
        "Default Objective",
        options=list(VALID["objectives"]),
        index=list(VALID["objectives"]).index("Conversions")
    )
    
    default_budget = st.number_input(
        "Default Daily Budget (£)",
        min_value=1,
        value=50,
        step=5
    )
    
    default_bid_strategy = st.selectbox(
        "Default Bid Strategy",
        options=list(VALID["bid_strategies"]),
        index=0
    )
    
    # Special ad categories
    st.subheader("Compliance")
    special_ad_category = st.selectbox(
        "Special Ad Category",
        options=[""] + list(VALID["special_categories"]),
        help="Required for credit, employment, housing, social issues, or political ads"
    )
    
    if special_ad_category:
        special_ad_country = st.text_input("Special Ad Country", value="GB")
    else:
        special_ad_country = ""
    
    # Default audience
    st.subheader("Default Targeting")
    default_country = st.text_input("Default Country", value="GB")
    default_age_min = st.number_input("Min Age", min_value=13, max_value=65, value=18)
    default_age_max = st.number_input("Max Age", min_value=13, max_value=65, value=65)
    default_gender = st.selectbox("Gender", options=list(VALID["gender"]), index=0)
    
    # UTM defaults
    st.subheader("UTM Defaults")
    utm_source = st.text_input("UTM Source", value="meta")
    utm_medium = st.text_input("UTM Medium", value="cpc")
    utm_campaign = st.text_input("UTM Campaign", value="{{campaign.name}}", 
                                help="Meta dynamic parameter for campaign name")
    utm_content = st.text_input("UTM Content", value="{{adset.name}}", 
                               help="Meta dynamic parameter for ad set name")
    
    st.caption("Full UTM string: utm_source=meta&utm_medium=cpc&utm_campaign={{campaign.name}}&utm_content={{adset.name}}")

# Main content area
col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("📊 Quick Stats")
    if 'processed_data' in st.session_state:
        stats = st.session_state.processed_data
        
        st.markdown(f"""
        <div class="metric-container">
            <h3>{stats.get('campaigns', 0)}</h3>
            <p>Campaigns</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="metric-container">
            <h3>{stats.get('adsets', 0)}</h3>
            <p>Ad Sets</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="metric-container">
            <h3>£{stats.get('total_budget', 0):,.0f}</h3>
            <p>Total Daily Budget</p>
        </div>
        """, unsafe_allow_html=True)

with col1:
    # Input methods
    st.subheader("📁 Input Your Campaign Data")
    
    input_method = st.radio(
        "Choose input method:",
        ["Upload CSV File", "Paste Data", "Use Template Builder"],
        horizontal=True
    )
    
    df_input = None
    
    if input_method == "Upload CSV File":
        uploaded_file = st.file_uploader(
            "Upload your CSV file", 
            type=["csv"],
            help="Upload a CSV with your campaign structure"
        )
        if uploaded_file is not None:
            try:
                df_input = pd.read_csv(uploaded_file)
                st.success(f"✅ File uploaded successfully! {len(df_input)} rows found.")
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
    
    elif input_method == "Paste Data":
        st.info("💡 Paste your CSV data including headers. First column should be 'Input Level'")
        pasted_data = st.text_area(
            "Paste CSV data:",
            height=200,
            placeholder="Input Level,Campaign Name,Campaign Objective,Ad Set Name...\ncampaign,My Campaign,Conversions,\nadset,My Campaign,Conversions,My Ad Set..."
        )
        if pasted_data.strip():
            try:
                df_input = pd.read_csv(StringIO(pasted_data))
                st.success(f"✅ Data parsed successfully! {len(df_input)} rows found.")
            except Exception as e:
                st.error(f"❌ Error parsing data: {e}")
    
    else:  # Template Builder
        st.info("🔧 Quick campaign builder - create campaigns on the fly")
        
        with st.expander("➕ Add Campaign", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                camp_name = st.text_input("Campaign Name", value="My Campaign")
                camp_obj = st.selectbox("Objective", options=list(VALID["objectives"]), 
                                       index=list(VALID["objectives"]).index(default_objective))
            with col_b:
                camp_budget = st.number_input("Daily Budget (£)", min_value=1, value=default_budget)
                camp_status = st.selectbox("Status", options=list(VALID["status"]), index=0)
        
        # Ad Sets builder
        st.subheader("Ad Sets")
        num_adsets = st.number_input("Number of Ad Sets", min_value=1, max_value=10, value=2)
        
        adset_data = []
        for i in range(num_adsets):
            with st.expander(f"Ad Set {i+1}", expanded=i==0):
                col_c, col_d = st.columns(2)
                with col_c:
                    as_name = st.text_input(f"Ad Set Name", value=f"{camp_name} - AdSet {i+1}", key=f"as_name_{i}")
                    as_budget = st.number_input(f"Daily Budget (£)", min_value=1, value=25, key=f"as_budget_{i}")
                    audience = st.text_input(f"Custom Audiences", placeholder="ca_lookalike_1pct", key=f"audience_{i}")
                with col_d:
                    ad_headline = st.text_input(f"Ad Headline", value=f"Great offer {i+1}", key=f"ad_headline_{i}")
                    ad_primary_text = st.text_area(f"Primary Text", value="Discover amazing products", height=60, key=f"ad_primary_{i}")
                    ad_description = st.text_input(f"Description", value="Limited time offer", key=f"ad_desc_{i}")
                    landing_url = st.text_input(f"Landing Page URL", value="https://example.com", key=f"url_{i}")
                
                adset_data.append({
                    'name': as_name, 'budget': as_budget, 'audience': audience,
                    'headline': ad_headline, 'primary_text': ad_primary_text, 
                    'description': ad_description, 'url': landing_url
                })
        
        if st.button("🚀 Generate Campaign Data", type="primary"):
            # Create DataFrame from builder
            rows = []
            # Campaign row
            rows.append({
                'Input Level': 'campaign',
                'Campaign Name': camp_name,
                'Campaign Status': camp_status,
                'Campaign Objective': camp_obj,
                'Campaign Daily Budget': camp_budget,
                'Special Ad Categories': special_ad_category,
                'Special Ad Category Country': special_ad_country,
            })
            
            # Ad set rows
            for i, adset in enumerate(adset_data):
                utm_params = f"utm_source={utm_source}&utm_medium={utm_medium}&utm_campaign={utm_campaign}&utm_content={utm_content}"
                
                rows.append({
                    'Input Level': 'adset',
                    'Campaign Name': camp_name,
                    'Ad Set Name': adset['name'],
                    'Ad Set Daily Budget': adset['budget'],
                    'Countries': default_country,
                    'Age Min': default_age_min,
                    'Age Max': default_age_max,
                    'Gender': default_gender,
                    'Custom Audiences': adset['audience'],
                    'Ad Name': f"{adset['name']} - Ad",
                    'Headline': adset['headline'],
                    'Primary Text': adset['primary_text'],
                    'Description': adset['description'],
                    'Link': adset['url'],
                    'URL Tags': utm_params,
                    'Call to Action': OBJ_DEFAULTS.get(camp_obj, {}).get('cta', 'LEARN_MORE')
                })
            
            df_input = pd.DataFrame(rows)
            st.success("✅ Campaign data generated!")

# Processing section
if df_input is not None:
    st.markdown("---")
    st.subheader("📋 Data Preview & Validation")
    
    # Show input preview
    with st.expander("👀 Input Data Preview", expanded=False):
        st.dataframe(df_input, use_container_width=True)
    
    # Apply defaults to missing fields
    if st.checkbox("🔧 Apply sidebar defaults to empty fields", value=True):
        df_enhanced = df_input.copy()
        
        # Apply defaults where fields are empty
        if 'Campaign Objective' in df_enhanced.columns:
            df_enhanced['Campaign Objective'] = df_enhanced['Campaign Objective'].fillna(default_objective)
        if 'Campaign Daily Budget' in df_enhanced.columns:
            df_enhanced['Campaign Daily Budget'] = df_enhanced['Campaign Daily Budget'].fillna(default_budget)
        if 'Campaign Bid Strategy' in df_enhanced.columns:
            df_enhanced['Campaign Bid Strategy'] = df_enhanced['Campaign Bid Strategy'].fillna(default_bid_strategy)
        if 'Countries' in df_enhanced.columns:
            df_enhanced['Countries'] = df_enhanced['Countries'].fillna(default_country)
        if 'Age Min' in df_enhanced.columns:
            df_enhanced['Age Min'] = df_enhanced['Age Min'].fillna(default_age_min)
        if 'Age Max' in df_enhanced.columns:
            df_enhanced['Age Max'] = df_enhanced['Age Max'].fillna(default_age_max)
        if 'Gender' in df_enhanced.columns:
            df_enhanced['Gender'] = df_enhanced['Gender'].fillna(default_gender)
        if 'Special Ad Categories' in df_enhanced.columns:
            df_enhanced['Special Ad Categories'] = df_enhanced['Special Ad Categories'].fillna(special_ad_category)
        if 'Special Ad Category Country' in df_enhanced.columns:
            df_enhanced['Special Ad Category Country'] = df_enhanced['Special Ad Category Country'].fillna(special_ad_country)
        
        df_input = df_enhanced
    
    # Process the data
    try:
        with st.spinner("🔄 Processing your data..."):
            output_df, errors_df = transform(df_input)
        
        # Calculate stats
        campaigns = len(output_df[output_df['Campaign Name'] != '']['Campaign Name'].unique()) if not output_df.empty else 0
        adsets = len(output_df[output_df['Ad Set Name'] != '']) if not output_df.empty else 0
        total_budget = 0
        
        if not output_df.empty:
            campaign_budgets = pd.to_numeric(output_df['Campaign Daily Budget'].replace('', 0), errors='coerce').sum()
            adset_budgets = pd.to_numeric(output_df['Ad Set Daily Budget'].replace('', 0), errors='coerce').sum()
            total_budget = max(campaign_budgets, adset_budgets)  # Avoid double counting
        
        st.session_state.processed_data = {
            'campaigns': campaigns,
            'adsets': adsets, 
            'total_budget': total_budget
        }
        
        # Show validation results
        if not errors_df.empty:
            st.markdown("""
            <div class="error-box">
                <h4>⚠️ Validation Issues Found</h4>
                <p>Please fix the following issues before exporting:</p>
            </div>
            """, unsafe_allow_html=True)
            st.dataframe(errors_df, use_container_width=True)
        else:
            st.markdown("""
            <div class="success-box">
                <h4>✅ Validation Successful</h4>
                <p>Your data is ready for Meta Ads Manager upload!</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Show output preview
        st.subheader("📤 Meta Ads Manager Output")
        
        if not output_df.empty:
            # Key metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Campaigns", campaigns)
            with col2:
                st.metric("Ad Sets", adsets)
            with col3:
                st.metric("Total Budget", f"£{total_budget:,.0f}/day")
            
            # Output preview
            st.dataframe(output_df, use_container_width=True)
            
            # Download section
            st.subheader("💾 Download Options")
            
            col_dl1, col_dl2, col_dl3 = st.columns(3)
            
            with col_dl1:
                # Main download
                csv_output = output_df.to_csv(index=False).encode('utf-8-sig')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                filename = f"meta_ads_upload_{timestamp}.csv"
                
                st.download_button(
                    label="📁 Download Meta Ads CSV",
                    data=csv_output,
                    file_name=filename,
                    mime="text/csv",
                    type="primary"
                )
            
            with col_dl2:
                # Debug download
                if not errors_df.empty:
                    errors_csv = errors_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="🐛 Download Errors Report",
                        data=errors_csv,
                        file_name=f"validation_errors_{timestamp}.csv",
                        mime="text/csv"
                    )
            
            with col_dl3:
                # Template download
                template_data = {
                    'Input Level': ['campaign', 'adset', 'adset'],
                    'Campaign Name': ['Example Campaign', 'Example Campaign', 'Example Campaign'],
                    'Campaign Status': ['ACTIVE', '', ''],
                    'Campaign Objective': ['Conversions', '', ''],
                    'Campaign Daily Budget': [100, '', ''],
                    'Ad Set Name': ['', 'Prospecting', 'Remarketing'],
                    'Ad Set Daily Budget': ['', 50, 30],
                    'Countries': ['', 'GB', 'GB'],
                    'Age Min': ['', 25, 25],
                    'Age Max': ['', 55, 55],
                    'Custom Audiences': ['', '', 'ca_website_visitors'],
                    'Saved Audiences': ['', 'interested_in_cars', ''],
                    'Ad Name': ['', 'Prospecting Ad', 'Remarketing Ad'],
                    'Headline': ['', 'Great Product!', 'Come Back!'],
                    'Primary Text': ['', 'Amazing offer for you', 'Complete your purchase'],
                    'Description': ['', 'Limited time only', 'Don\'t miss out'],
                    'Link': ['', 'https://example.com', 'https://example.com'],
                    'URL Tags': ['', 'utm_source=meta&utm_medium=cpc&utm_campaign={{campaign.name}}&utm_content={{adset.name}}', 'utm_source=meta&utm_medium=cpc&utm_campaign={{campaign.name}}&utm_content={{adset.name}}'],
                    'Call to Action': ['', 'SHOP_NOW', 'SHOP_NOW']
                }
                template_df = pd.DataFrame(template_data)
                template_csv = template_df.to_csv(index=False).encode('utf-8-sig')
                
                st.download_button(
                    label="📋 Download Template",
                    data=template_csv,
                    file_name="meta_ads_template.csv",
                    mime="text/csv",
                    help="Download a sample template to get started"
                )
        
    except Exception as e:
        st.error(f"❌ Processing failed: {e}")
        st.info("💡 Check your input data format and try again")

else:
    st.info("👆 Choose an input method above to get started")

# Footer
st.markdown("---")
with st.expander("ℹ️ Help & Documentation"):
    st.markdown("""
    ### 📖 How to Use This Tool
    
    **Input Format Requirements:**
    - First column must be 'Input Level' with values 'campaign' or 'adset'
    - Campaign rows define campaign-level settings
    - Adset rows inherit campaign settings and define targeting + creative
    
    **Key Fields:**
    - **Required**: Input Level, Campaign Name, Campaign Objective
    - **Recommended**: Ad Set Name (for adset rows), Countries, Age Min/Max
    - **Creative**: Headline, Primary Text, Description, Link, Call to Action
    - **Audiences**: Custom Audiences, Saved Audiences (use one or both)
    
    **UTM Parameters:**
    - Use Meta's dynamic parameters: `{{campaign.name}}` and `{{adset.name}}`
    - Default format: `utm_source=meta&utm_medium=cpc&utm_campaign={{campaign.name}}&utm_content={{adset.name}}`
    - Avoid putting UTMs directly in the Link field
    
    **Age Targeting:**
    - Minimum age is 13 (18 for special ad categories)
    - Maximum age is 65
    - Tool automatically enforces Meta's age restrictions
    
    **Budget Handling:**
    - If both campaign and ad set budgets are specified, ad set budget takes priority
    - Budgets are converted to whole numbers (Meta requirement)
    
    ### 🚨 Common Issues
    - **Age errors**: Check minimum age is 13+ (18+ for special categories)
    - **UTM format**: Use key=value pairs separated by &
    - **Missing objectives**: Ensure campaign rows have valid objectives
    - **Budget conflicts**: Don't specify both campaign and ad set budgets
    """)

st.markdown("""
<div style="text-align: center; color: #666; margin-top: 2rem;">
    <p>Built for Meta Ads Manager bulk uploads • Version 2.0</p>
</div>
""", unsafe_allow_html=True)
