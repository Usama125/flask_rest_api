from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

app = Flask(__name__)
CORS(app)

API_KEY = 'e609a0e7-8a14-4ebf-9ca9-d5ba6e6a3336'
BASE_URL = 'https://api.company-information.service.gov.uk'

def get_company_number(company_name):
    try:
        response = requests.get(f'{BASE_URL}/search/companies', params={'q': company_name}, auth=(API_KEY, ''))
        response.raise_for_status()
        data = response.json()
        if 'items' in data and len(data['items']) > 0:
            return data['items'][0]['company_number']
        return None
    except requests.RequestException as e:
        print(f"Error fetching company number: {e}")
        return None

def get_company_profile(company_number):
    try:
        response = requests.get(f'{BASE_URL}/company/{company_number}', auth=(API_KEY, ''))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching company profile: {e}")
        return None

def get_filing_history(company_number):
    try:
        response = requests.get(f'{BASE_URL}/company/{company_number}/filing-history', auth=(API_KEY, ''))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching filing history: {e}")
        return None

def get_officers(company_number):
    try:
        response = requests.get(f'{BASE_URL}/company/{company_number}/officers', auth=(API_KEY, ''))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching officers: {e}")
        return None

def get_psc(company_number):
    try:
        response = requests.get(f'{BASE_URL}/company/{company_number}/persons-with-significant-control', auth=(API_KEY, ''))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching PSC: {e}")
        return None

def get_document_metadata(document_url):
    try:
        response = requests.get(document_url, auth=(API_KEY, ''))
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching document metadata: {e}")
        return None

def download_document(document_url, filename, accept_header):
    try:
        response = requests.get(document_url, headers={'Accept': accept_header}, auth=(API_KEY, ''), stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        return filename
    except requests.RequestException as e:
        print(f"Error downloading document: {e}")
        return None

def extract_financial_data_xbrl(xbrl_path):
    try:
        with open(xbrl_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, features="xml")
        extracted_data = defaultdict(list)
        non_fraction_elements = soup.find_all(["ix:nonFraction", "ix:nonNumeric"])
        for element in non_fraction_elements:
            name = element.get("name", "Unnamed")
            value = element.text.strip()
            if value.replace(",", "").replace(".", "").isdigit():
                context_ref = element.get("contextRef", "NoContextRef")
                extracted_data[name].append((context_ref, value))
        return extracted_data
    except Exception as e:
        print(f"Error extracting data from XBRL: {e}")
        return {}

@app.route('/company', methods=['POST'])
def get_company_data():
    data = request.get_json()
    company_name = data.get('company_name')
    if not company_name:
        return jsonify({'error': 'company_name is required'}), 400

    company_number = get_company_number(company_name)
    if not company_number:
        return jsonify({'error': 'Company number not found'}), 404

    company_profile = get_company_profile(company_number) or {}
    filing_history = get_filing_history(company_number) or {}
    officers = get_officers(company_number) or {}
    psc = get_psc(company_number) or {}

    account_files = [file for file in filing_history.get('items', []) if file.get('category') == 'accounts']
    financial_data = {}
    if account_files:
        metadata = get_document_metadata(account_files[0].get('links', {}).get('document_metadata'))
        if metadata and metadata.get('resources', {}).get('application/xhtml+xml'):
            filename = f"/tmp/{company_number}_account.xhtml"
            downloaded_file = download_document(metadata['links']['document'], filename, 'application/xhtml+xml')
            if downloaded_file:
                financial_data = extract_financial_data_xbrl(downloaded_file)
                os.remove(downloaded_file)

    response_data = {
        'financialData': financial_data,
        'companyId': company_number,
        'companyName': company_name,
        'companyProfile': company_profile,
        'officers': officers,
        'psc': psc
    }

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
