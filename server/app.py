import os
import json
import pandas as pd
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import openai
import tempfile
import fitz   # PyMuPDF


# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

class W7FormFiller:
    """Real W-7 PDF form filler using PyMuPDF"""
    
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = None
        
    def open_form(self):
        """Open the PDF form."""
        try:
            self.doc = fitz.open(self.pdf_path)
            return True
        except Exception as e:
            print(f"Error opening form: {e}")
            return False
    
    def fill_fields(self, field_data):
        """Fill form fields with provided data."""
        if not self.doc:
            print("No document loaded. Call open_form() first.")
            return False
            
        filled_count = 0
        
        try:
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                widgets = list(page.widgets())
                
                for field in widgets:
                    field_name = field.field_name
                    
                    if field_name in field_data:
                        try:
                            value = field_data[field_name]
                            
                            if field.field_type == fitz.PDF_WIDGET_TYPE_TEXT:
                                field.field_value = str(value)
                                field.update()
                                filled_count += 1
                                print(f"Filled text field '{field_name}': '{value}'")
                                
                            elif field.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                                field.field_value = bool(value)
                                field.update()
                                filled_count += 1
                                print(f"Filled checkbox '{field_name}': {value}")
                                
                        except Exception as e:
                            print(f"Error updating field '{field_name}': {e}")
                            continue
            
            print(f"Successfully filled {filled_count} fields")
            return filled_count > 0
            
        except Exception as e:
            print(f"Error filling fields: {e}")
            return False
    
    def save_form(self, output_path):
        """Save the filled form to a new file."""
        if not self.doc:
            print("No document loaded.")
            return False
            
        try:
            self.doc.save(output_path, garbage=4, deflate=True)
            print(f"Form saved successfully to: {output_path}")
            return True
        except Exception as e:
            print(f"Error saving form: {e}")
            return False
    
    def close(self):
        """Close the document."""
        if self.doc:
            self.doc.close()

class W7FormProcessor:
    def __init__(self):
        self.form_data = {}
        self.excel_data = None  # Store full Excel data
        self.client_list = []   # Store list of available clients
        self.w7_template_path = "w7.pdf"  # Your local W-7 PDF file
        self.filled_pdf_path = None
        self.create_w7_field_mapping()
        
    def create_w7_field_mapping(self):
        """Create mapping from user-friendly field names to actual W-7 PDF field names"""
        self.field_mapping = {
            # Application type
            'application_type_new': 'topmostSubform[0].Page1[0].c1_1[0]',
            'application_type_renew': 'topmostSubform[0].Page1[0].c1_1[1]',
            
            # Reason codes
            'reason_a': 'topmostSubform[0].Page1[0].c1_2[0]',  # Treaty benefit
            'reason_b': 'topmostSubform[0].Page1[0].c1_3[0]',  # Nonresident alien filing tax return
            'reason_c': 'topmostSubform[0].Page1[0].c1_4[0]',  # U.S. resident alien
            'reason_d': 'topmostSubform[0].Page1[0].c1_5[0]',  # Dependent
            'reason_e': 'topmostSubform[0].Page1[0].c1_6[0]',  # Spouse
            'reason_f': 'topmostSubform[0].Page1[0].c1_7[0]',  # Student/professor/researcher
            'reason_g': 'topmostSubform[0].Page1[0].c1_8[0]',  # Dependent/spouse of nonresident
            'reason_h': 'topmostSubform[0].Page1[0].c1_9[0]',  # Other
            
            # Additional reason fields
            'reason_d_relationship': 'topmostSubform[0].Page1[0].f1_01[0]',
            'reason_de_name1': 'topmostSubform[0].Page1[0].f1_02[0]',  # Name field 1 for d/e
            'reason_de_name2': 'topmostSubform[0].Page1[0].f1_03[0]',  # Name field 2 for d/e
            'reason_h_other': 'topmostSubform[0].Page1[0].f1_04[0]',
            'treaty_country1': 'topmostSubform[0].Page1[0].f1_05[0]',
            'treaty_country2': 'topmostSubform[0].Page1[0].f1_06[0]',
            
            # Name fields
            'first_name': 'topmostSubform[0].Page1[0].f1_07[0]',
            'middle_name': 'topmostSubform[0].Page1[0].f1_08[0]',
            'last_name': 'topmostSubform[0].Page1[0].f1_09[0]',
            
            # Name at birth (if different)
            'first_name_birth': 'topmostSubform[0].Page1[0].f1_10[0]',
            'middle_name_birth': 'topmostSubform[0].Page1[0].f1_11[0]',
            'last_name_birth': 'topmostSubform[0].Page1[0].f1_12[0]',
            
            # Addresses
            'mailing_address': 'topmostSubform[0].Page1[0].f1_13[0]',
            'mailing_city_state_zip': 'topmostSubform[0].Page1[0].f1_14[0]',
            'foreign_address': 'topmostSubform[0].Page1[0].f1_15[0]',
            'foreign_city_state_country': 'topmostSubform[0].Page1[0].f1_16[0]',
            
            # Birth information
            'date_of_birth': 'topmostSubform[0].Page1[0].Line4_ReadOrder[0].f1_17[0]',
            'country_of_birth': 'topmostSubform[0].Page1[0].f1_18[0]',
            'city_state_birth': 'topmostSubform[0].Page1[0].f1_19[0]',
            
            # Gender
            'gender_male': 'topmostSubform[0].Page1[0].c1_10[0]',
            'gender_female': 'topmostSubform[0].Page1[0].c1_10[1]',
            
            # Other information
            'country_of_citizenship': 'topmostSubform[0].Page1[0].f1_20[0]',
            'foreign_tax_id': 'topmostSubform[0].Page1[0].f1_21[0]',
            'visa_info': 'topmostSubform[0].Page1[0].f1_22[0]',
            
            # ID Documents
            'id_passport': 'topmostSubform[0].Page1[0].c1_11[0]',
            'id_drivers_license': 'topmostSubform[0].Page1[0].c1_11[1]',
            'id_uscis': 'topmostSubform[0].Page1[0].c1_11[2]',
            'id_other': 'topmostSubform[0].Page1[0].c1_11[3]',
            'id_other_type': 'topmostSubform[0].Page1[0].f1_23[0]',
            
            # Document details
            'doc_issued_by': 'topmostSubform[0].Page1[0].Issued_ReadOrder[0].f1_24[0]',
            'doc_number': 'topmostSubform[0].Page1[0].Issued_ReadOrder[0].f1_25[0]',
            'doc_expiration': 'topmostSubform[0].Page1[0].Issued_ReadOrder[0].f1_26[0]',
            'date_of_entry': 'topmostSubform[0].Page1[0].f1_27[0]',
            
            # 6e: Previous ITIN question (FIXED AND COMPLETE)
            'previous_itin_no': 'topmostSubform[0].Page1[0].c1_12[0]',      # No/Don't know
            'previous_itin_yes': 'topmostSubform[0].Page1[0].c1_12[1]',     # Yes
            
            # 6f: Previous ITIN/IRSN details (ADDED MISSING FIELDS)
            'previous_itin_first_3': 'topmostSubform[0].Page1[0].ITIN[0].f1_28[0]',     # ITIN first 3 digits
            'previous_itin_middle_2': 'topmostSubform[0].Page1[0].ITIN[0].f1_29[0]',    # ITIN middle 2 digits
            'previous_itin_last_3': 'topmostSubform[0].Page1[0].ITIN[0].f1_30[0]',      # ITIN last 3 digits
            'previous_irsn_first_3': 'topmostSubform[0].Page1[0].IRSN[0].f1_31[0]',     # IRSN first 3 digits
            'previous_irsn_middle_2': 'topmostSubform[0].Page1[0].IRSN[0].f1_32[0]',    # IRSN middle 2 digits
            'previous_irsn_last_3': 'topmostSubform[0].Page1[0].IRSN[0].f1_33[0]',      # IRSN last 3 digits
            'previous_itin_name_first': 'topmostSubform[0].Page1[0].f1_34[0]',          # Name under which ITIN was issued - First
            'previous_itin_name_middle': 'topmostSubform[0].Page1[0].f1_35[0]',         # Name under which ITIN was issued - Middle
            'previous_itin_name_last': 'topmostSubform[0].Page1[0].f1_36[0]',           # Name under which ITIN was issued - Last
            
            # 6g: College/University or Company info (ADDED MISSING FIELDS)
            'college_company_name': 'topmostSubform[0].Page1[0].f1_37[0]',              # Name of college/university or company
            'college_company_city_state': 'topmostSubform[0].Page1[0].f1_38[0]',        # City and state
            'length_of_stay': 'topmostSubform[0].Page1[0].f1_39[0]',                    # Length of stay
            
            # Contact and signature section
            'phone_number': 'topmostSubform[0].Page1[0].f1_40[0]',
            'delegate_name': 'topmostSubform[0].Page1[0].f1_41[0]',
            'delegate_parent': 'topmostSubform[0].Page1[0].c1_13[0]',
            'delegate_power_attorney': 'topmostSubform[0].Page1[0].c1_13[1]',
            'delegate_court_guardian': 'topmostSubform[0].Page1[0].c1_13[2]',
            
            # Acceptance Agent section
            'agent_phone': 'topmostSubform[0].Page1[0].f1_42[0]',
            'agent_fax': 'topmostSubform[0].Page1[0].f1_43[0]',
            'agent_name_title': 'topmostSubform[0].Page1[0].f1_44[0]',
            'agent_company': 'topmostSubform[0].Page1[0].f1_45[0]',
            'agent_ein': 'topmostSubform[0].Page1[0].f1_46[0]',
            'agent_ptin': 'topmostSubform[0].Page1[0].f1_47[0]',
            'agent_office_code': 'topmostSubform[0].Page1[0].f1_48[0]',
        }
        
    def process_excel_data(self, file_path):
        """Read and extract data from Excel file - now handles multiple clients"""
        try:
            df = pd.read_excel(file_path)
            if df.empty:
                return None
                
            # Store the full dataframe for later client selection
            self.excel_data = df
            
            # Create a list of available clients
            self.client_list = []
            
            # Try to find name columns (handle various naming conventions)
            first_name_cols = [col for col in df.columns if 'first' in col.lower() and 'name' in col.lower()]
            last_name_cols = [col for col in df.columns if 'last' in col.lower() and 'name' in col.lower()]
            
            if not first_name_cols or not last_name_cols:
                # Fallback: try to find any column with "name" 
                name_cols = [col for col in df.columns if 'name' in col.lower()]
                print(f"Available columns with 'name': {name_cols}")
                return None
                
            first_name_col = first_name_cols[0]
            last_name_col = last_name_cols[0]
            
            # Extract client names
            for idx, row in df.iterrows():
                first_name = str(row[first_name_col]).strip() if pd.notna(row[first_name_col]) else ""
                last_name = str(row[last_name_col]).strip() if pd.notna(row[last_name_col]) else ""
                
                if first_name and last_name:  # Only add if both names exist
                    self.client_list.append({
                        'first_name': first_name,
                        'last_name': last_name,
                        'full_name': f"{first_name} {last_name}",
                        'row_index': idx
                    })
            
            print(f"Found {len(self.client_list)} clients in Excel file")
            return self.client_list
            
        except Exception as e:
            print(f"Error processing Excel: {e}")
            return None
    
    def get_client_data(self, first_name, last_name):
        """Get data for a specific client by name"""
        try:
            if self.excel_data is None:
                return None
                
            # Find the matching client
            matching_client = None
            for client in self.client_list:
                if (client['first_name'].lower() == first_name.lower() and 
                    client['last_name'].lower() == last_name.lower()):
                    matching_client = client
                    break
            
            if not matching_client:
                return None
                
            # Get the row data for this client
            row_data = self.excel_data.iloc[matching_client['row_index']].to_dict()
            
            # Clean and standardize column names
            cleaned_data = {}
            for key, value in row_data.items():
                clean_key = str(key).strip().lower().replace(' ', '_').replace('/', '_')
                cleaned_data[clean_key] = str(value) if pd.notna(value) else ""
                
            return cleaned_data
            
        except Exception as e:
            print(f"Error getting client data: {e}")
            return None
    
    def create_gpt_prompt(self, excel_data):
        """Create prompt for GPT to map Excel data to W-7 form fields"""
        available_fields = list(self.field_mapping.keys())
        
        system_prompt = f"""You are an expert in IRS Form W-7 (Application for IRS Individual Taxpayer Identification Number). 
        Your task is to map user data from Excel columns to the appropriate W-7 form fields.
        
        Available form fields: {', '.join(available_fields)}
        
        Key W-7 Form fields and their purposes:
        - first_name, middle_name, last_name: Current legal name
        - first_name_birth, middle_name_birth, last_name_birth: Name at birth if different
        - mailing_address: Street address (e.g., "123 Main St, Apt 5")
        - mailing_city_state_zip: City, state, ZIP and country (e.g., "Austin, TX 78701, USA")
        - foreign_address: Foreign street address
        - foreign_city_state_country: Foreign city, state/province, country
        - date_of_birth: Format as MMDDYYYY (e.g., "03151985")
        - country_of_birth: Country where person was born
        - city_state_birth: City and state/province of birth
        - gender_male, gender_female: Set one to true based on gender
        - country_of_citizenship: Citizenship country
        - foreign_tax_id: Foreign tax identification number
        - phone_number: Contact phone number
        
        Application type (choose one):
        - application_type_new: true for new ITIN application
        - application_type_renew: true for ITIN renewal
        
        Reason for application (choose one):
        - reason_a: Nonresident alien claiming tax treaty benefit
        - reason_b: Nonresident alien filing U.S. tax return
        - reason_c: U.S. resident alien filing tax return
        - reason_d: Dependent of U.S. citizen/resident alien
        - reason_e: Spouse of U.S. citizen/resident alien
        - reason_f: Nonresident alien student/professor/researcher
        - reason_g: Dependent/spouse of nonresident alien
        - reason_h: Other
        
        ID Document type (choose one):
        - id_passport: true if using passport
        - id_drivers_license: true if using driver's license/state ID
        - id_uscis: true if using USCIS document
        - id_other: true if using other document type
        
        IMPORTANT: Previous ITIN/IRSN Information (Section 6e/6f):
        - previous_itin_no: true if person has NOT previously received ITIN/IRSN
        - previous_itin_yes: true if person HAS previously received ITIN/IRSN
        
        If previous_itin_yes is true, you MUST also fill these fields:
        - previous_itin_first_3: First 3 digits of previous ITIN (e.g., "900")
        - previous_itin_middle_2: Middle 2 digits of previous ITIN (e.g., "70")  
        - previous_itin_last_3: Last 3 digits of previous ITIN (e.g., "1234")
        - previous_itin_name_first: First name under which ITIN was issued
        - previous_itin_name_middle: Middle name under which ITIN was issued  
        - previous_itin_name_last: Last name under which ITIN was issued
        
        For IRSN (if applicable):
        - previous_irsn_first_3, previous_irsn_middle_2, previous_irsn_last_3: IRSN number parts
        
        College/University Information (Section 6g - for students/researchers):
        - college_company_name: Name of educational institution or company
        - college_company_city_state: City and state of institution
        - length_of_stay: Duration of stay (e.g., "2 years", "Fall 2023 - Spring 2024")
        
        CRITICAL INSTRUCTION FOR ITIN PROCESSING:
        - Look for any column that contains "ITIN", "itin", "tax_id", "previous_itin", or similar
        - If you find an ITIN number, parse it carefully:
        * Format is typically XXX-XX-XXXX (9 digits total)
        * Split into: first_3 (XXX), middle_2 (XX), last_3 (XXXX)
        * Set previous_itin_yes = true
        * Set previous_itin_no = false
        - If no ITIN found or ITIN field is empty, set previous_itin_no = true and previous_itin_yes = false
        
        CRITICAL: Your response must contain ONLY a valid JSON object. Do not include any explanatory text, markdown formatting, or additional commentary. Return ONLY the JSON object with the mapped fields."""
        
        user_prompt = f"""Map this Excel data to W-7 form fields:
        {json.dumps(excel_data, indent=2)}
        
        IMPORTANT: Respond with ONLY a JSON object. Do not include any explanatory text or markdown formatting.
        
        Pay special attention to:
        1. Any ITIN-related data in the Excel - if found, make sure to set previous_itin_yes=true and fill the ITIN number fields
        2. Educational institution information for students/researchers  
        3. Proper date formatting for date_of_birth (MMDDYYYY)
        4. Gender field mapping (set either gender_male or gender_female to true)
        
        Required JSON format example:
        {{
            "first_name": "string",
            "middle_name": "string", 
            "last_name": "string",
            "mailing_address": "string",
            "mailing_city_state_zip": "string",
            "date_of_birth": "MMDDYYYY",
            "country_of_birth": "string",
            "country_of_citizenship": "string",
            "gender_male": boolean,
            "gender_female": boolean,
            "application_type_new": boolean,
            "reason_b": boolean,
            "id_passport": boolean,
            "phone_number": "string",
            "previous_itin_yes": boolean,
            "previous_itin_no": boolean,
            "previous_itin_first_3": "string",
            "previous_itin_middle_2": "string", 
            "previous_itin_last_3": "string",
            "previous_itin_name_first": "string",
            "previous_itin_name_middle": "string",
            "previous_itin_name_last": "string"
        }}"""
        
        return system_prompt, user_prompt
    
    def call_openai_api(self, system_prompt, user_prompt):
        """Call OpenAI API to process the data"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            print(f"Raw OpenAI response: {content}")
            
            # Extract JSON from response - handle various formats
            json_content = content
            
            # Remove markdown code blocks
            if '```json' in json_content:
                start_idx = json_content.find('```json') + 7
                end_idx = json_content.find('```', start_idx)
                if end_idx != -1:
                    json_content = json_content[start_idx:end_idx].strip()
            elif '```' in json_content:
                start_idx = json_content.find('```') + 3
                end_idx = json_content.find('```', start_idx)
                if end_idx != -1:
                    json_content = json_content[start_idx:end_idx].strip()
            
            # Find JSON object by looking for { and }
            start_brace = json_content.find('{')
            end_brace = json_content.rfind('}')
            
            if start_brace != -1 and end_brace != -1 and start_brace < end_brace:
                json_content = json_content[start_brace:end_brace + 1]
            
            print(f"Extracted JSON: {json_content}")
            
            # Parse the JSON
            parsed_json = json.loads(json_content)
            return parsed_json
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Content that failed to parse: {json_content}")
            return None
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None
    
    def transform_data_to_pdf_format(self, form_data):
        """Transform JSON form data to PDF field format"""
        pdf_data = {}
        
        for user_field, value in form_data.items():
            if user_field in self.field_mapping:
                pdf_field_name = self.field_mapping[user_field]
                
                # Handle special formatting for certain fields
                if user_field == 'date_of_birth' and value:
                    # Ensure date is in MMDDYYYY format
                    try:
                        # Try to parse various date formats and convert to MMDDYYYY
                        if '/' in str(value):
                            parts = str(value).split('/')
                            if len(parts) == 3:
                                month, day, year = parts[0].zfill(2), parts[1].zfill(2), parts[2]
                                value = f"{month}{day}{year}"
                        elif '-' in str(value):
                            # Handle YYYY-MM-DD format
                            parts = str(value).split('-')
                            if len(parts) == 3:
                                year, month, day = parts[0], parts[1].zfill(2), parts[2].zfill(2)
                                value = f"{month}{day}{year}"
                    except:
                        pass  # Keep original value if parsing fails
                
                pdf_data[pdf_field_name] = value
                print(f"Mapped {user_field} -> {pdf_field_name}: {value}")
        
        return pdf_data
    
    def fill_w7_pdf(self, form_data):
        """Fill the W-7 PDF using the real form filler"""
        try:
            # Check if template file exists
            if not os.path.exists(self.w7_template_path):
                print(f"Error: {self.w7_template_path} not found")
                return None
            
            # Transform data to PDF field format
            pdf_data = self.transform_data_to_pdf_format(form_data)
            
            # Create temporary file for filled PDF
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.close()  # Close the file handle so PyMuPDF can write to it
            
            # Initialize form filler
            form_filler = W7FormFiller(self.w7_template_path)
            
            try:
                # Open the form
                if not form_filler.open_form():
                    print("Failed to open PDF form")
                    return None
                
                print(f"✓ Opened PDF form: {self.w7_template_path}")
                
                # Fill the form
                if form_filler.fill_fields(pdf_data):
                    # Save the filled form
                    if form_filler.save_form(temp_file.name):
                        print(f"✓ Filled PDF saved to: {temp_file.name}")
                        self.filled_pdf_path = temp_file.name
                        return temp_file.name
                    else:
                        print("Failed to save filled PDF")
                        return None
                else:
                    print("Failed to fill PDF fields")
                    return None
                    
            finally:
                form_filler.close()
                
        except Exception as e:
            print(f"Error filling PDF: {e}")
            return None

# Initialize processor
processor = W7FormProcessor()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload and return list of available clients"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Please upload an Excel file (.xlsx or .xls)'}), 400
        
        # Save uploaded file temporarily
        temp_path = tempfile.mktemp(suffix='.xlsx')
        file.save(temp_path)
        
        # Process Excel data to get list of clients
        client_list = processor.process_excel_data(temp_path)
        if not client_list:
            return jsonify({'error': 'Failed to process Excel file or no clients found'}), 400
        
        # Clean up temporary file
        os.unlink(temp_path)
        
        return jsonify({
            'success': True,
            'client_list': client_list,
            'total_clients': len(client_list),
            'message': f'File processed successfully. Found {len(client_list)} clients.'
        })
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/process-client', methods=['POST'])
def process_client():
    """Process a specific client by name and generate form data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
            
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        
        if not first_name or not last_name:
            return jsonify({'error': 'Both first_name and last_name are required'}), 400
        
        # Get client data
        client_data = processor.get_client_data(first_name, last_name)
        if not client_data:
            return jsonify({'error': f'Client "{first_name} {last_name}" not found'}), 404
        
        # Create GPT prompt
        system_prompt, user_prompt = processor.create_gpt_prompt(client_data)
        
        # Call OpenAI API
        gpt_response = processor.call_openai_api(system_prompt, user_prompt)
        if not gpt_response:
            return jsonify({'error': 'Failed to process data with OpenAI'}), 500
        
        # Store form data in session/memory
        processor.form_data = gpt_response
        
        return jsonify({
            'success': True,
            'client_name': f'{first_name} {last_name}',
            'excel_data': client_data,
            'mapped_data': gpt_response,
            'message': 'Client processed successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/generate-pdf', methods=['POST'])
def generate_pdf():
    """Generate W-7 PDF with form data"""
    try:
        if not processor.form_data:
            return jsonify({'error': 'No form data available. Please process a client first.'}), 400
        
        # Fill the PDF
        pdf_path = processor.fill_w7_pdf(processor.form_data)
        if not pdf_path:
            return jsonify({'error': 'Failed to generate PDF'}), 500
        
        return jsonify({
            'success': True,
            'message': 'PDF generated successfully',
            'pdf_ready': True
        })
        
    except Exception as e:
        return jsonify({'error': f'PDF generation error: {str(e)}'}), 500

@app.route('/api/download-pdf', methods=['GET'])
def download_pdf():
    """Download the generated PDF"""
    try:
        if not processor.filled_pdf_path or not os.path.exists(processor.filled_pdf_path):
            return jsonify({'error': 'No PDF available. Please generate PDF first.'}), 400
        
        return send_file(
            processor.filled_pdf_path,
            as_attachment=True,
            download_name='form_w7_filled.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'Download error: {str(e)}'}), 500

@app.route('/api/debug-form', methods=['GET'])
def debug_form():
    """Debug endpoint to check form fields and PDF structure"""
    try:
        debug_info = {
            'template_exists': os.path.exists(processor.w7_template_path),
            'field_mapping_count': len(processor.field_mapping),
            'sample_field_mapping': dict(list(processor.field_mapping.items())[:10]),
            'clients_loaded': len(processor.client_list) if processor.client_list else 0,
            'excel_data_loaded': processor.excel_data is not None
        }
        
        # Try to open PDF and get field information
        if os.path.exists(processor.w7_template_path):
            try:
                doc = fitz.open(processor.w7_template_path)
                all_fields = []
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    widgets = page.widgets()
                    
                    for widget in widgets:
                        all_fields.append({
                            'page': page_num + 1,
                            'field_name': widget.field_name,
                            'field_type': widget.field_type,
                            'field_type_name': {
                                0: 'Unknown',
                                1: 'Button', 
                                2: 'Text',
                                3: 'Choice',
                                4: 'Checkbox',
                                5: 'Radio'
                            }.get(widget.field_type, f'Type_{widget.field_type}')
                        })
                
                doc.close()
                
                debug_info.update({
                    'pdf_form_fields_sample': all_fields[:20],  # First 20 fields
                    'total_pdf_fields': len(all_fields),
                    'pdf_pages': len(doc)
                })
                
            except Exception as e:
                debug_info['pdf_error'] = str(e)
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'W-7 Form Processor API is running'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)