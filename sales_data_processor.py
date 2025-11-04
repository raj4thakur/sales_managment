# sales_data_processor.py
import pandas as pd
import re
from datetime import datetime
import numpy as np
import sqlite3
import os
import streamlit as st

class SalesDataProcessor:
    def __init__(self, db):
        self.db = db
        self.setup_product_mapping()
        self.setup_location_mapping()
        self.setup_database_tables()
    
    def setup_database_tables(self):
        """Initialize database tables if they don't exist"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Create sales table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_sheet TEXT,
                sr_no TEXT,
                customer_name TEXT,
                village TEXT,
                taluka TEXT,
                district TEXT,
                invoice_no TEXT UNIQUE,
                reference TEXT,
                dispatch_date TEXT,
                product_type TEXT,
                quantity INTEGER,
                rate_per_unit REAL,
                amount REAL,
                final_amount REAL,
                total_liters REAL,
                payment_date TEXT,
                gpay_amount REAL,
                cash_amount REAL,
                cheque_amount REAL,
                rrn_number TEXT,
                sold_by TEXT,
                sale_type TEXT,
                payment_status TEXT,
                payment_method TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_file TEXT
            )
        ''')
        
        # Create customers table (aggregated from sales)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                village TEXT,
                taluka TEXT,
                district TEXT,
                total_purchases REAL DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                last_order_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def setup_product_mapping(self):
        """Standard product mapping for all packaging types"""
        self.PRODUCT_MAPPING = {
            '1 LTR PLASTIC JAR': '1L_PLASTIC_JAR',
            '2 LTR PLASTIC JAR': '2L_PLASTIC_JAR', 
            '5 LTR PLASTIC JAR': '5L_PLASTIC_JAR',
            '10 LTR PLASTIC JAR': '10L_PLASTIC_JAR',
            '5 LTR STEEL BARNI': '5L_STEEL_BARNI',
            '10 LTR STEEL BARNI': '10L_STEEL_BARNI',
            '20 LTR STEEL BARNI': '20L_STEEL_BARNI',
            '20 LTR PLASTIC CAN': '20L_PLASTIC_CAN',
            '1 LTR PET BOTTLE': '1L_PET_BOTTLE',
            '20 LTR CARBO': '20L_CARBO'
        }
    
    def setup_location_mapping(self):
        """Gujarati location name standardization"""
        self.GUJARATI_LOCALITIES = {
            'રામપુરા': 'RAMPURA',
            'શેખડી': 'SHEKHADI', 
            'સિંહોલ': 'SINHOL',
            'વનાદરા': 'VANADARA',
            'માવલી': 'MAVLI',
            'સિમરડા': 'SIMRADA',
            'બિલપડ': 'BILPAD',
            'વઘોડિયા': 'VAGHODIA',
            'સાકરિયા': 'SAKARIYA'
        }
    
    def safe_float(self, value):
        """Safely convert to float, handle errors"""
        if pd.isna(value) or value in ['', 'NOT_AVAILABLE', None, '_']:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def safe_int(self, value):
        """Safely convert to integer"""
        return int(self.safe_float(value))
    
    def parse_date(self, date_str):
        """Handle all date formats intelligently"""
        if pd.isna(date_str) or date_str in ['', 'NOT_AVAILABLE', None, '_']:
            return 'NOT_AVAILABLE'
        
        if isinstance(date_str, (int, float)):
            try:
                return (datetime(1899, 12, 30) + pd.Timedelta(days=date_str)).strftime('%Y-%m-%d')
            except:
                return 'INVALID_DATE'
        
        date_str = str(date_str).strip()
        
        date_formats = [
            '%Y-%m-%d %H:%M:%S', 
            '%d/%m/%Y', 
            '%Y-%m-%d', 
            '%d-%m-%Y',
            '%d/%m/%Y %H:%M:%S'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return 'INVALID_DATE'
    
    def clean_name(self, name):
        """Handle names, duplicates, variations"""
        if pd.isna(name) or name in ['', '-', '_', None]:
            return 'NOT_AVAILABLE'
        name = ' '.join(str(name).strip().split())
        return name
    
    def standardize_location(self, location):
        """Handle Gujarati location names"""
        if pd.isna(location) or location in ['', 'NOT_AVAILABLE', None]:
            return 'NOT_AVAILABLE'
        
        location_str = str(location).strip()
        
        if isinstance(location_str, str):
            for guj_name, eng_name in self.GUJARATI_LOCALITIES.items():
                if guj_name in location_str:
                    return eng_name
        
        return location_str.upper()
    
    def standardize_product(self, product_name):
        """Convert any product name to standard format"""
        if pd.isna(product_name) or product_name in ['', 'NOT_AVAILABLE', None]:
            return 'UNKNOWN_PRODUCT'
        
        product_str = str(product_name).strip()
        product_upper = product_str.upper()
        
        for key, value in self.PRODUCT_MAPPING.items():
            if key in product_upper:
                return value
        
        # Fuzzy matching
        if '1 LTR' in product_upper or '1L' in product_upper:
            if 'PLASTIC' in product_upper or 'JAR' in product_upper:
                return '1L_PLASTIC_JAR'
            elif 'PET' in product_upper or 'BOTTLE' in product_upper:
                return '1L_PET_BOTTLE'
        elif '2 LTR' in product_upper or '2L' in product_upper:
            return '2L_PLASTIC_JAR'
        elif '5 LTR' in product_upper or '5L' in product_upper:
            if 'STEEL' in product_upper or 'BARNI' in product_upper:
                return '5L_STEEL_BARNI'
            else:
                return '5L_PLASTIC_JAR'
        elif '10 LTR' in product_upper or '10L' in product_upper:
            if 'STEEL' in product_upper or 'BARNI' in product_upper:
                return '10L_STEEL_BARNI'
            else:
                return '10L_PLASTIC_JAR'
        elif '20 LTR' in product_upper or '20L' in product_upper:
            if 'STEEL' in product_upper or 'BARNI' in product_upper:
                return '20L_STEEL_BARNI'
            elif 'PLASTIC' in product_upper or 'CAN' in product_upper:
                return '20L_PLASTIC_CAN'
            elif 'CARBO' in product_upper:
                return '20L_CARBO'
        
        return f"UNKNOWN_{product_upper.replace(' ', '_')}"
    
    def detect_sale_type(self, row):
        """Detect if it's demo sale (single unit) or bulk sale"""
        quantity = self.safe_int(row.get('QTN', 0))
        reference = str(row.get('REF.', '')).upper()
        
        if reference == 'DEMO' or quantity == 1:
            return 'DEMO_SALE'
        else:
            return 'BULK_SALE'
    
    def calculate_payment_status(self, row):
        """Determine payment status intelligently"""
        final_amt = self.safe_float(row.get('FINAL AMT', 0))
        gpay = self.safe_float(row.get('G-PAY', 0))
        cash = self.safe_float(row.get('CASH', 0))
        cheque = self.safe_float(row.get('CHQ', 0))
        
        paid_amt = gpay + cash + cheque
        
        if paid_amt >= final_amt:
            return 'PAID'
        elif paid_amt > 0:
            return 'PARTIAL_PAID'
        elif self.parse_date(row.get('PAYMENT DATE')) not in ['NOT_AVAILABLE', 'INVALID_DATE']:
            return 'PENDING'
        else:
            return 'UNPAID'
    
    def detect_payment_method(self, row):
        """Intelligently detect payment method"""
        gpay = self.safe_float(row.get('G-PAY', 0))
        cash = self.safe_float(row.get('CASH', 0))
        cheque = self.safe_float(row.get('CHQ', 0))
        
        if gpay > 0:
            return 'GPAY'
        elif cash > 0:
            return 'CASH'
        elif cheque > 0:
            return 'CHEQUE'
        else:
            return 'NOT_PAID'
    
    def process_dataframe(self, df, sheet_name, source_file):
        """Process entire dataframe and standardize all records"""
        standardized_records = []
        
        for idx, row in df.iterrows():
            if (pd.isna(row.get('NAME', '')) and 
                pd.isna(row.get('PACKING', '')) and 
                pd.isna(row.get('INV NO', ''))):
                continue
            
            try:
                standardized_record = self.standardize_record(row, sheet_name, source_file)
                standardized_records.append(standardized_record)
            except Exception as e:
                st.error(f"⚠️ Error processing row {idx}: {e}")
                continue
        
        return standardized_records
    
    def standardize_record(self, row, sheet_name, source_file):
        """Standardize a single record"""
        record = {
            'source_sheet': sheet_name,
            'sr_no': self.clean_name(row.get('SR NO.', 'NOT_AVAILABLE')),
            'customer_name': self.clean_name(row.get('NAME', 'NOT_AVAILABLE')),
            'village': self.standardize_location(row.get('VILLAGE', 'NOT_AVAILABLE')),
            'taluka': self.standardize_location(row.get('TALUKA', 'NOT_AVAILABLE')),
            'district': self.standardize_location(row.get('DISTRICT', 'NOT_AVAILABLE')),
            'invoice_no': self.clean_name(row.get('INV NO', 'NOT_AVAILABLE')),
            'reference': self.clean_name(row.get('REF.', 'NOT_AVAILABLE')),
            'dispatch_date': self.parse_date(row.get('DISPATCH DATE')),
            'product_type': self.standardize_product(row.get('PACKING', 'NOT_AVAILABLE')),
            'quantity': self.safe_int(row.get('QTN', 0)),
            'rate_per_unit': self.safe_float(row.get('RATE', 0)),
            'amount': self.safe_float(row.get('AMT', 0)),
            'final_amount': self.safe_float(row.get('FINAL AMT', 0)),
            'total_liters': self.safe_float(row.get('TOTAL LTR', 0)),
            'payment_date': self.parse_date(row.get('PAYMENT DATE')),
            'gpay_amount': self.safe_float(row.get('G-PAY', 0)),
            'cash_amount': self.safe_float(row.get('CASH', 0)),
            'cheque_amount': self.safe_float(row.get('CHQ', 0)),
            'rrn_number': self.clean_name(row.get('RRN', 'NOT_AVAILABLE')),
            'sold_by': self.clean_name(row.get('BY', 'NOT_AVAILABLE')),
            'sale_type': self.detect_sale_type(row),
            'payment_status': self.calculate_payment_status(row),
            'payment_method': self.detect_payment_method(row),
            'source_file': os.path.basename(source_file)
        }
        
        # Auto-calculate missing amounts
        if record['amount'] == 0 and record['quantity'] > 0 and record['rate_per_unit'] > 0:
            record['amount'] = record['quantity'] * record['rate_per_unit']
        
        if record['final_amount'] == 0 and record['amount'] > 0:
            record['final_amount'] = record['amount']
        
        return record
    
    def insert_into_database(self, records):
        """Insert processed records into database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        inserted_count = 0
        updated_count = 0
        
        for record in records:
            try:
                # Check if invoice already exists
                cursor.execute('SELECT id FROM sales WHERE invoice_no = ?', (record['invoice_no'],))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    update_query = '''
                        UPDATE sales SET 
                        source_sheet=?, sr_no=?, customer_name=?, village=?, taluka=?, district=?,
                        reference=?, dispatch_date=?, product_type=?, quantity=?, rate_per_unit=?,
                        amount=?, final_amount=?, total_liters=?, payment_date=?, gpay_amount=?,
                        cash_amount=?, cheque_amount=?, rrn_number=?, sold_by=?, sale_type=?,
                        payment_status=?, payment_method=?, source_file=?
                        WHERE invoice_no=?
                    '''
                    cursor.execute(update_query, (
                        record['source_sheet'], record['sr_no'], record['customer_name'],
                        record['village'], record['taluka'], record['district'],
                        record['reference'], record['dispatch_date'], record['product_type'],
                        record['quantity'], record['rate_per_unit'], record['amount'],
                        record['final_amount'], record['total_liters'], record['payment_date'],
                        record['gpay_amount'], record['cash_amount'], record['cheque_amount'],
                        record['rrn_number'], record['sold_by'], record['sale_type'],
                        record['payment_status'], record['payment_method'], record['source_file'],
                        record['invoice_no']
                    ))
                    updated_count += 1
                else:
                    # Insert new record
                    insert_query = '''
                        INSERT INTO sales (
                            source_sheet, sr_no, customer_name, village, taluka, district,
                            invoice_no, reference, dispatch_date, product_type, quantity,
                            rate_per_unit, amount, final_amount, total_liters, payment_date,
                            gpay_amount, cash_amount, cheque_amount, rrn_number, sold_by,
                            sale_type, payment_status, payment_method, source_file
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                    cursor.execute(insert_query, (
                        record['source_sheet'], record['sr_no'], record['customer_name'],
                        record['village'], record['taluka'], record['district'],
                        record['invoice_no'], record['reference'], record['dispatch_date'],
                        record['product_type'], record['quantity'], record['rate_per_unit'],
                        record['amount'], record['final_amount'], record['total_liters'],
                        record['payment_date'], record['gpay_amount'], record['cash_amount'],
                        record['cheque_amount'], record['rrn_number'], record['sold_by'],
                        record['sale_type'], record['payment_status'], record['payment_method'],
                        record['source_file']
                    ))
                    inserted_count += 1
                    
            except Exception as e:
                st.error(f"❌ Database error for invoice {record['invoice_no']}: {e}")
                continue
        
        conn.commit()
        
        # Update customers table
        self.update_customers_table(conn)
        
        conn.close()
        
        return inserted_count, updated_count
    
    def update_customers_table(self, conn):
        """Update customers table from sales data"""
        cursor = conn.cursor()
        
        # Clear and rebuild customers table
        cursor.execute('DELETE FROM customers')
        
        # Insert aggregated customer data
        cursor.execute('''
            INSERT INTO customers (customer_name, village, taluka, district, total_purchases, total_orders, last_order_date)
            SELECT 
                customer_name,
                village,
                taluka,
                district,
                SUM(final_amount) as total_purchases,
                COUNT(*) as total_orders,
                MAX(dispatch_date) as last_order_date
            FROM sales 
            WHERE customer_name != 'NOT_AVAILABLE'
            GROUP BY customer_name, village, taluka, district
        ''')
        
        conn.commit()
    
    def process_excel_file(self, file_path):
        """Main method to process Excel file - called from Streamlit"""
        try:
            st.info(f"🔄 Processing: {os.path.basename(file_path)}")
            
            # Read the Excel file
            xl = pd.ExcelFile(file_path)
            
            # Process each sheet
            all_records = []
            
            for sheet_name in xl.sheet_names:
                with st.spinner(f"Processing sheet: {sheet_name}..."):
                    # Read sheet
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # Standardize data
                    standardized_records = self.process_dataframe(df, sheet_name, file_path)
                    all_records.extend(standardized_records)
            
            if not all_records:
                st.warning("⚠️ No valid records found in the file")
                return False
            
            # Insert into database
            with st.spinner("Inserting into database..."):
                inserted, updated = self.insert_into_database(all_records)
            
            # Show results
            if inserted > 0 or updated > 0:
                st.success(f"✅ Processed {len(all_records)} records from {os.path.basename(file_path)}")
                st.success(f"📊 New: {inserted}, Updated: {updated}")
                
                # Show quick summary
                self.show_import_summary(all_records)
                return True
            else:
                st.warning("⚠️ No records were inserted or updated")
                return False
            
        except Exception as e:
            st.error(f"❌ Error processing file: {e}")
            return False
    
    def show_import_summary(self, records):
        """Show summary of imported data"""
        if not records:
            return
        
        df = pd.DataFrame(records)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Records", len(records))
        with col2:
            demo_sales = len(df[df['sale_type'] == 'DEMO_SALE'])
            st.metric("Demo Sales", demo_sales)
        with col3:
            bulk_sales = len(df[df['sale_type'] == 'BULK_SALE'])
            st.metric("Bulk Sales", bulk_sales)
        with col4:
            total_amount = df['final_amount'].sum()
            st.metric("Total Amount", f"₹{total_amount:,.2f}")
        
        # Show top products
        st.subheader("📦 Products Imported")
        product_summary = df['product_type'].value_counts().head(5)
        for product, count in product_summary.items():
            st.write(f"- {product}: {count} records")
    
    def get_import_stats(self):
        """Get import statistics for dashboard"""
        conn = self.db.get_connection()
        
        try:
            # Total records
            total_records = pd.read_sql('SELECT COUNT(*) as count FROM sales', conn)['count'].iloc[0]
            
            # Files processed
            files_processed = pd.read_sql('SELECT COUNT(DISTINCT source_file) as count FROM sales', conn)['count'].iloc[0]
            
            # Recent imports
            recent_imports = pd.read_sql('''
                SELECT source_file, COUNT(*) as records, MAX(processed_at) as last_import
                FROM sales 
                GROUP BY source_file 
                ORDER BY last_import DESC 
                LIMIT 5
            ''', conn)
            
            return {
                'total_records': total_records,
                'files_processed': files_processed,
                'recent_imports': recent_imports.to_dict('records')
            }
        finally:
            conn.close()