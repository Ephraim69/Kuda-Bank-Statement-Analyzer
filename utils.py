import pandas as pd
import numpy as np
import re
from datetime import datetime

def process_kuda_excel(excel_file):
    """
    Process a Kuda Bank Excel file and extract the transaction data.
    
    Args:
        excel_file: The uploaded Excel file or file path
        
    Returns:
        pandas.DataFrame: A clean dataframe with standardized columns
    """
    try:
        # Read the Excel file
        # Print debug info
        print(f"Reading Excel file...")
        
        # Try to read with different engines
        try:
            df_raw = pd.read_excel(excel_file, header=None, engine='openpyxl')
            print(f"Successfully read Excel file with openpyxl engine")
        except Exception as e1:
            print(f"Error reading with openpyxl: {str(e1)}")
            try:
                df_raw = pd.read_excel(excel_file, header=None, engine='xlrd')
                print(f"Successfully read Excel file with xlrd engine")
            except Exception as e2:
                print(f"Error reading with xlrd: {str(e2)}")
                raise ValueError(f"Failed to read Excel file with both engines. Original error: {str(e1)}")
        
        # Debug info - Print first few rows to help diagnose
        print("First 20 rows of Excel file:")
        for i in range(min(20, len(df_raw))):
            print(f"Row {i}: {df_raw.iloc[i].values}")
        
        # Find the row where the actual transaction data begins
        # First, look for 'Date/Time' exactly at cell C16 (index 2, row 15)
        header_row_idx = None
        
        print("Searching for transaction headers...")
        # Look specifically at row 15 (0-indexed) first as mentioned by the user
        if len(df_raw) > 15:  # Ensure we have enough rows
            row_15 = df_raw.iloc[15]
            row_15_str = [str(x).lower() for x in row_15.values]
            
            # Check if 'date/time' is at position 2 (column C)
            if len(row_15) > 2 and 'date/time' in str(row_15.iloc[2]).lower():
                header_row_idx = 15
                print(f"Found 'Date/Time' header at row 15 (cell C16)")
        
        # If we didn't find it at the expected position, do a general search
        if header_row_idx is None:
            for i, row in df_raw.iterrows():
                # Convert row to string and print for debugging
                row_str = [str(x).lower() for x in row.values]
                if i < 20:  # Only print first 20 rows to avoid clutter
                    print(f"Row {i} checking: {row_str}")
                
                # Check different possible header indicators
                if any(x.lower() == 'date/time' for x in row_str):
                    header_row_idx = i
                    print(f"Found 'Date/Time' header at row {i}")
                    break
                
                # Alternative headers
                if (any('date' in str(x).lower() for x in row_str) and 
                    any('money' in str(x).lower() for x in row_str)):
                    header_row_idx = i
                    print(f"Found alternative headers (date & money) at row {i}")
                    break
                    
        if header_row_idx is None:
            # Could not find the header row, search using partial match
            print("Trying partial matching for headers...")
            for i, row in df_raw.iterrows():
                row_values = [str(x).lower() for x in row.values if pd.notna(x)]
                if 'date' in row_values or 'time' in row_values or 'date/time' in ' '.join(row_values):
                    if 'money' in ' '.join(row_values) or 'balance' in ' '.join(row_values):
                        header_row_idx = i
                        print(f"Found partial match for headers at row {i}: {row.values}")
                        break
            
        if header_row_idx is None:
            # Print detailed debug info about the Excel structure
            print("\nDetailed Excel structure:")
            for i, row in df_raw.iterrows():
                if i < 30:  # Only check first 30 rows
                    non_empty = sum(1 for x in row if pd.notna(x) and str(x).strip() != '')
                    if non_empty > 0:
                        print(f"Row {i} (non-empty cells: {non_empty}): {[str(x) for x in row if pd.notna(x)]}")
            
            raise ValueError("Could not find the transaction data header in the Excel file. Looking for 'Date/Time' or similar headers in row 15 at cell C16.")
        
        # Extract the transaction data
        print(f"Extracting transaction data from row {header_row_idx}")
        df_transactions = df_raw.iloc[header_row_idx:].reset_index(drop=True)
        
        # Get the header row for column names
        header_row = df_transactions.iloc[0]
        
        # Create a dictionary of cleaned column names
        # We'll look for the required columns and map them to standard names
        clean_columns = []
        required_columns = {'date/time': 'Date/Time', 'money in': 'Money In', 'money out': 'Money out', 
                           'category': 'Category', 'to / from': 'To / From', 'description': 'Description', 
                           'balance': 'Balance'}
        
        # Find the required columns in the header row
        column_indices = {}
        
        # First, make a pass to identify where the required headers are in the row
        for i, cell in enumerate(header_row):
            cell_str = str(cell).strip().lower()
            for key in required_columns:
                if key == cell_str:
                    column_indices[required_columns[key]] = i
                    break
        
        # If we didn't find all required columns, try again with more flexible matching
        if len(column_indices) < len(required_columns):
            for i, cell in enumerate(header_row):
                if pd.isna(cell):
                    continue
                    
                cell_str = str(cell).strip().lower()
                for key in required_columns:
                    if key in cell_str:
                        column_indices[required_columns[key]] = i
                        break
        
        # Create a list to store the final DataFrame columns
        final_columns = []
        for i in range(len(header_row)):
            matched = False
            for col_name, col_index in column_indices.items():
                if i == col_index:
                    final_columns.append(col_name)
                    matched = True
                    break
            if not matched:
                final_columns.append(f"column_{i}")  # Use generic name for unidentified columns
        
        # Create a new DataFrame with the identified columns
        print(f"Identified standard columns at positions: {column_indices}")
        
        # Add the column names to the DataFrame
        df_transactions.columns = final_columns
        
        # Skip the header row
        df_transactions = df_transactions.iloc[1:].reset_index(drop=True)
        
        # Extract account info and summary if available
        account_number = None
        closing_balance = None
        summary_in = None
        summary_out = None
        
        print("Searching for account and summary information...")
        for i, row in df_raw.iterrows():
            if i >= header_row_idx:
                break
                
            row_str = [str(x) for x in row.values if pd.notna(x)]
            row_text = ' '.join(row_str).lower()
            
            # Look for account number
            if 'account' in row_text:
                print(f"Found 'account' mention in row {i}: {row.values}")
                for j, cell in enumerate(row):
                    if pd.notna(cell) and 'account' in str(cell).lower():
                        if j+1 < len(row) and pd.notna(row.iloc[j+1]):
                            account_number = str(row.iloc[j+1])
                            print(f"Found account number: {account_number}")
                            break
                        elif j-1 >= 0 and pd.notna(row.iloc[j-1]) and str(row.iloc[j-1]).isdigit():
                            account_number = str(row.iloc[j-1])
                            print(f"Found account number: {account_number}")
                            break
            
            # Look for closing balance
            if 'balance' in row_text or 'closing' in row_text:
                print(f"Found balance mention in row {i}: {row.values}")
                for j, cell in enumerate(row):
                    if pd.notna(cell) and ('balance' in str(cell).lower() or 'closing' in str(cell).lower()):
                        for k in range(j+1, min(j+3, len(row))):
                            if k < len(row) and pd.notna(row.iloc[k]) and (
                                '₦' in str(row.iloc[k]) or 
                                'n' in str(row.iloc[k]).lower() or 
                                str(row.iloc[k]).replace(',', '').replace('.', '').isdigit()):
                                closing_balance = str(row.iloc[k])
                                print(f"Found closing balance: {closing_balance}")
                                break
            
            # Look for summary data
            if 'summary' in row_text:
                print(f"Found summary mention in row {i}: {row.values}")
                summary_row = i
                
                # Find Money In and Money Out in summary
                for j in range(summary_row + 1, min(summary_row + 5, header_row_idx)):
                    if j >= len(df_raw):
                        break
                    
                    row_data = df_raw.iloc[j]
                    row_data_text = ' '.join([str(x) for x in row_data if pd.notna(x)]).lower()
                    
                    print(f"Checking summary data in row {j}: {row_data.values}")
                    
                    if 'money in' in row_data_text:
                        for k, cell in enumerate(row_data):
                            if pd.notna(cell) and 'money in' in str(cell).lower():
                                if k+1 < len(row_data) and pd.notna(row_data.iloc[k+1]):
                                    summary_in = str(row_data.iloc[k+1])
                                    print(f"Found Money In summary: {summary_in}")
                    
                    if 'money out' in row_data_text:
                        for k, cell in enumerate(row_data):
                            if pd.notna(cell) and 'money out' in str(cell).lower():
                                if k+1 < len(row_data) and pd.notna(row_data.iloc[k+1]):
                                    summary_out = str(row_data.iloc[k+1])
                                    print(f"Found Money Out summary: {summary_out}")
        
        # Store metadata in the DataFrame
        df_transactions.attrs['account_number'] = account_number
        df_transactions.attrs['closing_balance'] = closing_balance
        df_transactions.attrs['summary_in'] = summary_in
        df_transactions.attrs['summary_out'] = summary_out
        
        print(f"Extracted metadata - Account: {account_number}, Balance: {closing_balance}, In: {summary_in}, Out: {summary_out}")
        
        # Clean up the DataFrame - ensure we have the required columns or add them if missing
        required_columns_list = ['Date/Time', 'Money In', 'Money out', 'Category', 'To / From', 'Description', 'Balance']
        
        # Make sure we have all the required columns, add empty ones if missing
        for col in required_columns_list:
            if col not in df_transactions.columns:
                print(f"Adding missing column: {col}")
                df_transactions[col] = np.nan
                
        # Keep only the required columns plus any custom ones we want to preserve
        columns_to_keep = required_columns_list.copy()
        df_final = df_transactions[columns_to_keep]
        
        print(f"Final transaction data columns: {df_final.columns.tolist()}")
        print(f"Final data shape: {df_final.shape}")
        
        return df_final
        
    except Exception as e:
        print(f"ERROR in process_kuda_excel: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Error processing Kuda Bank Excel file: {str(e)}")

def clean_money_columns(df):
    """
    Clean the money columns by removing the currency symbol and converting to float.
    
    Args:
        df (pandas.DataFrame): The bank statement dataframe
        
    Returns:
        pandas.DataFrame: The dataframe with cleaned money columns
    """
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    # Process Money In column
    if 'Money In' in df.columns:
        # Replace empty strings and 'nan' values with NaN
        df['Money In'] = df['Money In'].replace('', np.nan)
        df['Money In'] = df['Money In'].replace('nan', np.nan)
        
        # Handle numeric values that might already be floats
        def clean_money_in(x):
            if pd.isna(x):
                return 0
            
            # If already a numeric type, return as is
            if isinstance(x, (int, float)):
                return float(x)
                
            # Convert to string and clean
            x_str = str(x)
            if x_str.strip() == '' or x_str.lower() == 'nan':
                return 0
            
            try:
                # Remove currency symbol and any non-numeric characters except decimal point
                return float(re.sub(r'[^\d.]', '', x_str))
            except:
                print(f"Error converting Money In value: {x_str}")
                return 0
                
        # Apply the cleaning function
        df['Money In'] = df['Money In'].apply(clean_money_in)
    
    # Process Money out column
    if 'Money out' in df.columns:
        # Replace empty strings and 'nan' values with NaN
        df['Money out'] = df['Money out'].replace('', np.nan)
        df['Money out'] = df['Money out'].replace('nan', np.nan)
        
        # Handle numeric values that might already be floats
        def clean_money_out(x):
            if pd.isna(x):
                return 0
            
            # If already a numeric type, return as is
            if isinstance(x, (int, float)):
                return float(x)
                
            # Convert to string and clean
            x_str = str(x)
            if x_str.strip() == '' or x_str.lower() == 'nan':
                return 0
            
            try:
                # Remove currency symbol and any non-numeric characters except decimal point
                return float(re.sub(r'[^\d.]', '', x_str))
            except:
                print(f"Error converting Money out value: {x_str}")
                return 0
                
        # Apply the cleaning function
        df['Money out'] = df['Money out'].apply(clean_money_out)
    
    # Process Balance column
    if 'Balance' in df.columns:
        # Replace empty strings and 'nan' values with NaN
        df['Balance'] = df['Balance'].replace('', np.nan)
        df['Balance'] = df['Balance'].replace('nan', np.nan)
        
        # Handle numeric values that might already be floats
        def clean_balance(x):
            if pd.isna(x):
                return 0
            
            # If already a numeric type, return as is
            if isinstance(x, (int, float)):
                return float(x)
                
            # Convert to string and clean
            x_str = str(x)
            if x_str.strip() == '' or x_str.lower() == 'nan':
                return 0
            
            try:
                # Remove currency symbol and any non-numeric characters except decimal point
                return float(re.sub(r'[^\d.]', '', x_str))
            except:
                print(f"Error converting Balance value: {x_str}")
                return 0
                
        # Apply the cleaning function
        df['Balance'] = df['Balance'].apply(clean_balance)
    
    return df

def parse_dates(df):
    """
    Parse the Date/Time column to datetime format.
    
    Args:
        df (pandas.DataFrame): The bank statement dataframe
        
    Returns:
        pandas.DataFrame: The dataframe with properly formatted dates
    """
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    if 'Date/Time' in df.columns:
        # Convert to string first (in case it's not already)
        df['Date/Time'] = df['Date/Time'].astype(str)
        
        # Handle 'nan' and empty strings
        df['Date/Time'] = df['Date/Time'].replace('nan', pd.NA)
        df['Date/Time'] = df['Date/Time'].replace('', pd.NA)
        
        # Try to parse dates with multiple formats
        parsed_dates = []
        
        for date_str in df['Date/Time']:
            try:
                # Skip NaN values
                if pd.isna(date_str) or date_str == 'NaT':
                    parsed_dates.append(pd.NaT)
                    continue
                    
                # Try different date formats
                date_formats = [
                    '%d/%m/%Y %H:%M',      # 10/1/2020 21:12
                    '%d/%m/%y %H:%M:%S',   # 16/01/20 09:22:35
                    '%d/%m/%Y %H:%M:%S',   # 16/01/2020 09:22:35
                    '%Y-%m-%d %H:%M:%S',   # 2020-01-10 21:12:00
                    '%d/%m/%y %H:%M',      # 19/10/22 14:12
                    '%d-%m-%Y',            # 15-01-2020
                    '%d/%m/%Y',            # 15/01/2020
                    '%d/%m/%y',            # 15/01/20
                ]
                
                # Try each format until one works
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_str, fmt)
                        parsed_dates.append(parsed_date)
                        break
                    except ValueError:
                        continue
                else:
                    # If none of the formats work, append NaT
                    parsed_dates.append(pd.NaT)
                    
            except Exception as e:
                print(f"Error parsing date '{date_str}': {str(e)}")
                # If any other error occurs, append NaT
                parsed_dates.append(pd.NaT)
        
        # Replace the original Date/Time column with parsed dates
        df['Date/Time'] = parsed_dates
    
    return df

def filter_out_savings(df):
    """
    Filter out transactions with "savings" in the description.
    
    Args:
        df (pandas.DataFrame): The bank statement dataframe
        
    Returns:
        pandas.DataFrame: The dataframe without savings transactions
    """
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    if 'Description' in df.columns:
        # Handle missing or null values first
        df['Description'] = df['Description'].fillna('')
        
        # Convert to string (in case it's not already)
        df['Description'] = df['Description'].astype(str)
        
        # Replace 'nan' strings with empty strings
        df['Description'] = df['Description'].replace('nan', '')
        
        # Filter out transactions with "savings" in the description (case insensitive)
        try:
            mask = ~df['Description'].str.lower().str.contains('savings', na=False)
            df = df[mask]
        except Exception as e:
            print(f"Error filtering savings transactions: {str(e)}")
            print(f"Description column data types: {df['Description'].apply(type).unique()}")
            # Fallback method if the above fails
            filtered_rows = []
            for i, row in df.iterrows():
                desc = str(row.get('Description', '')).lower()
                if 'savings' not in desc:
                    filtered_rows.append(row)
            if filtered_rows:
                df = pd.DataFrame(filtered_rows)
    
    return df
