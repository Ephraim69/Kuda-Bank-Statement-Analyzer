import streamlit as st
import traceback
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import numpy as np
import os
from utils import clean_money_columns, parse_dates, filter_out_savings, process_kuda_excel

# Set page configuration
st.set_page_config(
    page_title="Kuda Bank Statement Analyzer",
    page_icon="💰",
    layout="wide"
)

# Title and description
st.title("Kuda Bank Statement Analyzer")
st.markdown("Upload your Kuda Bank Excel statement to visualize and analyze your financial data.")

# Check if there's a file in attached_assets directory
sample_file_path = ""
has_sample_file = os.path.exists(sample_file_path)

# File uploader or use sample file
uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])

# Add a button to use the sample file
if has_sample_file:
    use_sample = st.checkbox("Use pre-loaded sample statement", value=True)
else:
    use_sample = False

# Main function to process and display data
def process_bank_statement(df):
    # Data cleaning
    df = clean_money_columns(df)
    df = parse_dates(df)
    df = filter_out_savings(df)
    
    # Create a sidebar for filters
    st.sidebar.header("Filters")
    
    # Date range filter
    if not df.empty and 'Date/Time' in df.columns:
        # Filter out NaT values for date operations
        date_df = df[df['Date/Time'].notna()]
        
        if not date_df.empty and hasattr(date_df['Date/Time'].iloc[0], 'date'):
            try:
                min_date = date_df['Date/Time'].min().date()
                max_date = date_df['Date/Time'].max().date()
                
                date_range = st.sidebar.date_input(
                    "Select Date Range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
            except AttributeError as e:
                st.sidebar.warning(f"Could not create date filter: {str(e)}")
                # Create a fallback date range
                today = datetime.datetime.now().date()
                date_range = (today - datetime.timedelta(days=30), today)
        else:
            st.sidebar.warning("Date filtering not available - date formatting issue detected")
            # Create a fallback date range
            today = datetime.datetime.now().date()
            date_range = (today - datetime.timedelta(days=30), today)
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            try:
                # Convert dates to datetime objects for comparison
                # Handle possible NaT and non-datetime values
                mask = df['Date/Time'].notna()  # Start with rows that have valid dates
                
                # Apply date filtering only on rows with valid datetime values
                # Check if each value has a date attribute first
                for i, val in enumerate(df.loc[mask, 'Date/Time']):
                    idx = df.loc[mask].iloc[i].name  # Get the actual index
                    if hasattr(val, 'date'):
                        row_date = val.date()
                        # Update mask with date comparison
                        mask.at[idx] = mask.at[idx] and (row_date >= start_date and row_date <= end_date)
                    else:
                        # If not a valid datetime object, exclude from results
                        mask.at[idx] = False
                
                # Apply the mask
                df_filtered = df.loc[mask]
            except Exception as e:
                st.error(f"Error during date filtering: {str(e)}")
                # If date filtering fails, return all data
                df_filtered = df
        else:
            df_filtered = df
    else:
        df_filtered = df
        
    # Category filter
    if not df_filtered.empty and 'Category' in df_filtered.columns:
        # Convert categories to string to avoid type comparison errors
        df_filtered['Category'] = df_filtered['Category'].fillna('Unknown').astype(str)
        categories = ['All'] + sorted(df_filtered['Category'].unique().tolist())
        selected_category = st.sidebar.selectbox("Select Category", categories)
        
        if selected_category != 'All':
            df_filtered = df_filtered[df_filtered['Category'] == selected_category]
    
    # Display key metrics
    st.header("Key Financial Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    if not df_filtered.empty:
        # Money In Total
        money_in_total = df_filtered['Money In'].sum()
        col1.metric("Total Money In", f"₦{money_in_total:.2f}")
        
        # Money Out Total
        money_out_total = df_filtered['Money out'].sum()
        col2.metric("Total Money Out", f"₦{money_out_total:.2f}")
        
        # Net Balance Change
        net_change = money_in_total - money_out_total
        col3.metric("Net Change", f"₦{net_change:.2f}", 
                   delta=f"{(net_change/money_in_total)*100:.1f}%" if money_in_total > 0 else "0%")
        
        # Current Balance (assuming last entry is most recent)
        if 'Balance' in df_filtered.columns:
            current_balance = df_filtered.iloc[-1]['Balance']
            col4.metric("Current Balance", f"₦{current_balance:.2f}")
    
    # Top Recipients Analysis
    st.header("Top Recipients")
    
    if not df_filtered.empty and 'To / From' in df_filtered.columns:
        # Group by recipient and calculate total money out
        recipients = df_filtered[df_filtered['Money out'] > 0].groupby('To / From').agg({
            'Money out': 'sum', 
            'Category': 'first'
        }).reset_index()
        
        # Sort by total money out and get top 20
        top_recipients = recipients.sort_values('Money out', ascending=False).head(100)
        
        # Plot top recipients
        fig = px.bar(
            top_recipients,
            y='To / From',
            x='Money out',
            color='Category',
            orientation='h',
            title='Top 100 Recipients by Transaction Value',
            labels={'Money out': 'Total Money Out (₦)', 'To / From': 'Recipient'},
            height=600
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Monthly Spending/Income Patterns
    st.header("Monthly Financial Patterns")
    
    if not df_filtered.empty and 'Date/Time' in df_filtered.columns:
        # Extract month and year from date - handle potential NaT values
        try:
            # Filter out NaT values first
            date_filtered = df_filtered[df_filtered['Date/Time'].notna()]
            
            if not date_filtered.empty:
                # Apply strftime only on valid datetime values
                df_filtered['Month-Year'] = df_filtered['Date/Time'].apply(
                    lambda x: x.strftime('%b %Y') if pd.notna(x) and hasattr(x, 'strftime') else 'Unknown'
                )
            else:
                st.warning("No valid dates found for monthly patterns")
                return
        except Exception as e:
            st.error(f"Error creating monthly patterns: {str(e)}")
            return
        
        # Group by month-year and calculate total money in and out
        monthly_data = df_filtered.groupby('Month-Year').agg({
            'Money In': 'sum',
            'Money out': 'sum',
            'Date/Time': 'min'  # To sort chronologically
        }).reset_index()
        
        # Sort by date
        monthly_data = monthly_data.sort_values('Date/Time')
        
        # Create a line chart for money in and out by month
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=monthly_data['Month-Year'],
            y=monthly_data['Money In'],
            mode='lines+markers',
            name='Money In',
            line=dict(color='green')
        ))
        
        fig.add_trace(go.Scatter(
            x=monthly_data['Month-Year'],
            y=monthly_data['Money out'],
            mode='lines+markers',
            name='Money Out',
            line=dict(color='red')
        ))
        
        fig.update_layout(
            title='Monthly Income vs Spending',
            xaxis_title='Month',
            yaxis_title='Amount (₦)',
            legend_title='Type',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Category Distribution
    st.header("Transaction Categories")
    
    if not df_filtered.empty and 'Category' in df_filtered.columns:
        # Create two columns for different charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Group by category for money out
            category_out = df_filtered[df_filtered['Money out'] > 0].groupby('Category').agg({
                'Money out': 'sum'
            }).reset_index()
            
            # Create a pie chart for spending by category
            fig = px.pie(
                category_out, 
                values='Money out', 
                names='Category',
                title='Spending by Category',
                hole=0.4
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Group by category for money in
            category_in = df_filtered[df_filtered['Money In'] > 0].groupby('Category').agg({
                'Money In': 'sum'
            }).reset_index()
            
            # Create a pie chart for income by category
            fig = px.pie(
                category_in, 
                values='Money In', 
                names='Category',
                title='Income by Category',
                hole=0.4
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Interactive data table
    st.header("Transaction Details")
    
    if not df_filtered.empty:
        # Allow user to select columns to display
        all_columns = df_filtered.columns.tolist()
        default_columns = ['Date/Time', 'Money In', 'Money out', 'Category', 'To / From', 'Description', 'Balance']
        selected_columns = st.multiselect("Select columns to display", all_columns, default=default_columns)
        
        if selected_columns:
            # Display the data with selected columns
            st.dataframe(df_filtered[selected_columns], use_container_width=True)
            
            # Download button for filtered data
            csv = df_filtered[selected_columns].to_csv(index=False)
            st.download_button(
                label="Download data as CSV",
                data=csv,
                file_name="bank_statement_filtered.csv",
                mime="text/csv",
            )
    
# Display account information section
def display_account_info(account_number=None, summary_in=None, summary_out=None, closing_balance=None):
    st.header("Account Information")
    
    col1, col2 = st.columns(2)
    
    # Account holder information
    with col1:
        if account_number:
            st.info(f"**Account Number:** {account_number}")
        else:
            st.info("Account information not available")
    
    # Summary information
    with col2:
        if closing_balance:
            st.success(f"**Closing Balance:** {closing_balance}")
        
        if summary_in and summary_out:
            st.info(f"**Total Money In:** {summary_in}  \n**Total Money Out:** {summary_out}")

# Display debugging info in a collapsible section
def display_debug_info(error_message, debug_data=None):
    with st.expander("Debug Information (Click to expand)"):
        st.error(f"Error Details: {error_message}")
        if debug_data:
            st.code(debug_data)
        st.info("The app is trying to find the 'Date/Time' header row in your Excel file. Make sure your Kuda Bank statement follows the format shown in the example below.")

# Process the bank statement based on user selection
if uploaded_file is not None:
    try:
        # Add info about file being processed
        st.info(f"Processing uploaded file: {uploaded_file.name}", icon="ℹ️")
        
        # Process Kuda bank statement format
        try:
            # Capture stdout for debugging
            import io
            import sys
            debug_output = io.StringIO()
            original_stdout = sys.stdout
            sys.stdout = debug_output
            
            # Try to process the file with detailed logging
            df = process_kuda_excel(uploaded_file)
            
            # Restore stdout
            sys.stdout = original_stdout
            debug_text = debug_output.getvalue()
            
            # Get metadata from the DataFrame
            account_number = df.attrs.get('account_number')
            closing_balance = df.attrs.get('closing_balance')
            summary_in = df.attrs.get('summary_in')
            summary_out = df.attrs.get('summary_out')
            
            # Display account info if available
            if account_number or closing_balance or summary_in or summary_out:
                display_account_info(account_number, summary_in, summary_out, closing_balance)
            
            # Process the transaction data
            process_bank_statement(df)
            
            # Show debug info in a collapsible section if we want to see the parsing details
            with st.expander("Show Processing Details", expanded=False):
                st.code(debug_text)
            
        except ValueError as ve:
            # If Kuda format processing fails, show detailed error
            # Make sure we restore stdout properly
            try:
                sys.stdout = original_stdout
                debug_text = debug_output.getvalue()
            except UnboundLocalError:
                debug_text = "Debug output not available"
                
            st.error(f"Error processing file as Kuda Bank statement: {str(ve)}")
            display_debug_info(str(ve), debug_text)
            
            # Offer alternative parsing
            st.warning("Attempting to process as a standard Excel file...")
            
            try:
                # Try standard Excel format
                df = pd.read_excel(uploaded_file)
                
                # Check if data is loaded correctly
                if df.empty:
                    st.error("The uploaded file is empty. Please upload a valid bank statement.")
                else:
                    # Check expected columns
                    expected_columns = ['Date/Time', 'Money In', 'Money out', 'Category', 'To / From', 'Description', 'Balance']
                    available_columns = df.columns.tolist()
                    
                    st.info(f"Detected columns: {', '.join(available_columns)}")
                    
                    missing_columns = [col for col in expected_columns if col not in df.columns]
                    
                    if missing_columns:
                        st.error(f"The uploaded file is missing the following expected columns: {', '.join(missing_columns)}")
                    else:
                        process_bank_statement(df)
            except Exception as inner_e:
                st.error(f"Failed to process as standard Excel file as well: {str(inner_e)}")
    
    except Exception as e:
        # exc_type, exc_value, exc_traceback = sys.exc_info()
        # print(f"Exception Type: {exc_type.__name__}")
        # print(f"Exception Message: {exc_value}")
        st.error(f"An error occurred while processing the file: { traceback.print_exc() }")
        st.error("Please ensure you're uploading a valid Excel bank statement with the expected format.")
        
        # Show help for fixing file format
        st.warning("The app is looking for a specific format with a row containing 'Date/Time', 'Money In', 'Money out', etc. as headers. Please check that your Excel file matches the expected format shown below.")
        
        # Display expected format
        st.subheader("Expected Kuda Bank Statement Format:")
        
        # Create a two-column layout for the sample
        col1, col2 = st.columns([2, 3])
        
        with col1:
            st.markdown("""
            **Account Information:**
            - Account Number: 1100050449
            - Closing Balance: ₦30,019.54
            
            **Summary:**
            - Money In: ₦63,689,925.09
            - Money Out: ₦63,659,905.55
            """)
        
        with col2:
            example_data = {
                'Date/Time': ['10/01/20 21:12:38', '16/01/20 09:22:35', '07/02/21 13:11:26'],
                'Money In': ['₦100.00', '', '₦100.00'],
                'Money out': ['', '₦100.00', ''],
                'Category': ['inward transfer', 'outward transfer', 'inward transfer'],
                'To / From': ['Osadebamwen Ephraim', 'Osadebamwen Ephraim', 'Osadebamwen Ephraim'],
                'Description': ['kip:zenith/osadebamwen', 'what all do you want from me?', 'kip:zenith/osadebamwen'],
                'Balance': ['₦100.00', '₦0.00', '₦100.00']
            }
            
            st.dataframe(pd.DataFrame(example_data), use_container_width=True)
        
elif use_sample and has_sample_file:
    try:
        # Add info about file being processed
        st.info(f"Processing sample file: {sample_file_path}", icon="ℹ️")
        
        # Capture stdout for debugging
        import io
        import sys
        debug_output = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = debug_output
        
        # Try to process as Kuda statement first
        try:
            df = process_kuda_excel(sample_file_path)
            
            # Restore stdout
            sys.stdout = original_stdout
            debug_text = debug_output.getvalue()
            
            # Get metadata from the DataFrame
            account_number = df.attrs.get('account_number')
            closing_balance = df.attrs.get('closing_balance')
            summary_in = df.attrs.get('summary_in')
            summary_out = df.attrs.get('summary_out')
            
            # Display account info if available
            if account_number or closing_balance or summary_in or summary_out:
                display_account_info(account_number, summary_in, summary_out, closing_balance)
            
            st.success("Using sample bank statement data.")
            process_bank_statement(df)
            
            # Show debug info in a collapsible section
            with st.expander("Show Processing Details", expanded=False):
                st.code(debug_text)
            
        except ValueError as ve:
            # If Kuda format processing fails, show detailed error
            # Make sure we restore stdout properly
            try:
                sys.stdout = original_stdout
                debug_text = debug_output.getvalue()
            except UnboundLocalError:
                debug_text = "Debug output not available"
            
            st.error(f"Error processing sample file as Kuda Bank statement: {str(ve)}")
            display_debug_info(str(ve), debug_text)
            
            # Offer alternative parsing
            st.warning("Attempting to process as a standard Excel file...")
            
            try:
                # Try standard Excel format
                df = pd.read_excel(sample_file_path)
                
                # Check if data is loaded correctly
                if df.empty:
                    st.error("The sample file is empty.")
                else:
                    # Check expected columns
                    expected_columns = ['Date/Time', 'Money In', 'Money out', 'Category', 'To / From', 'Description', 'Balance']
                    available_columns = df.columns.tolist()
                    
                    st.info(f"Detected columns: {', '.join(available_columns)}")
                    
                    missing_columns = [col for col in expected_columns if col not in df.columns]
                    
                    if missing_columns:
                        st.error(f"The sample file is missing the following expected columns: {', '.join(missing_columns)}")
                    else:
                        st.success("Using sample bank statement data.")
                        process_bank_statement(df)
            except Exception as inner_e:
                st.error(f"Failed to process sample as standard Excel file as well: {str(inner_e)}")
    
    except Exception as e:
        st.error(f"An error occurred while processing the sample file: {e}")
else:
    # Display a sample layout or instructions
    st.info("Please upload your Kuda Bank statement Excel file to get started or use the pre-loaded sample.")
    
    # Show the expected format
    st.subheader("Sample Kuda Bank Statement Format:")
    
    # Create a two-column layout for the sample
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.markdown("""
        **Account Information:**
        - Account Number: 1100043512
        - Closing Balance: $20,029,500.00
        
        **Summary:**
        - Money In: $100,000,000.00
        - Money Out: $50,000,500.00
        """)
    
    with col2:
        example_data = {
            'Date/Time': ['10/01/20 21:12:38', '16/01/20 09:22:35', '07/02/21 13:11:26'],
            'Money In': ['$30,000.00', '', ''],
            'Money out': ['', '$50,000,000.00', '$500.00'],
            'Category': ['Inward transfer', 'Outward transfer', 'Outward transfer'],
            'To / From': ['Ephraim Igbinosa', 'John Wick', 'Iyamu Idahosa'],
            'Description': ['Here you go', 'Eliminate target 007', 'Stop Begging me'],
            'Balance': ['$70,030,000', '$20,030,000.00', '$20,029,500.00']
        }
        
        st.dataframe(pd.DataFrame(example_data), use_container_width=True)
    
    st.markdown("""
    ## Features:
    - Upload and analyze your bank statement Excel file
    - View top 20 recipients by transaction value
    - Visualize spending and income patterns
    - Filter transactions by date range and category
    - Exclude transactions with "savings" in the description
    - Interactive and sortable data tables
    - Download filtered data as CSV
    """)
