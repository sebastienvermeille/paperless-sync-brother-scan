import datetime
import glob
import json
import os
import time
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth

import requests
import uuid as uuid

scanner_url = os.environ['SCANNER_URL']
scanner_username = os.environ['SCANNER_USERNAME']
scanner_password = os.environ['SCANNER_PASSWORD']

paperless_url = os.environ['PAPERLESS_URL']
paperless_login = os.environ['PAPERLESS_LOGIN']
paperless_password = os.environ['PAPERLESS_PASSWORD']

headers = {
    'Content-type': 'application/json',
}
auth = HTTPBasicAuth(scanner_username, scanner_password)


pdfsToDownload = []
checkScannerInterval: int = 60
downloadDir = "./temp"


def is_scanner_available():
    try:
        response = requests.get(scanner_url, auth=auth, timeout=3)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.exceptions.HTTPError:
        return False
    except requests.exceptions.ConnectTimeout:
        return False
    except requests.exceptions.ConnectionRefusedError:
        return False


def download_pdf_file(url):
    date = datetime.date.today()
    local_filename = f"{downloadDir}/{date}_{uuid.uuid4()}.pdf"
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename


def download_available_pdfs():
    response = requests.get(scanner_url + '/:sda1/DCIM:.xml:Document:Sub', auth=auth)
    string_xml = response.content
    try:
        root = ElementTree.fromstring(string_xml)
        for pdf in root.iter('ALLFile'):
            for doc in pdf.iter('Document'):
                for attr in doc.iter('FPATH'):
                    pdfsToDownload.append(attr.text)

        counter = len(pdfsToDownload)
        if counter > 0:
            print(f"{counter} new file(s) being synced...", flush=True)
            for dl in pdfsToDownload:
                download_pdf_file(scanner_url + dl)
        else:
            print("Nothing new to sync", flush=True)
    except ElementTree.ParseError:
        print("Invalid content received from API ignoring it for now", flush=True)


# delete docs
def delete_file(document_name):
    multipart_form_data = {
        'multiDelete': 'Delete Select File',
        'currentPage': 'Current_page=[1]',
        'multiUploadToFB': '',
        document_name: 'on'
    }

    r = requests.post(scanner_url + '/.xmlpdf.page_index=1.chipsipcmd', files=multipart_form_data, auth=auth)
    if r.status_code == 200:
        print(f"Success ({document_name})", flush=True)


def delete_all_pdfs():
    for dl in pdfsToDownload:
        delete_file(dl)


def upload_downloaded_documents(client):
    directory = os.fsencode(downloadDir)

    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        print(filename, flush=True)
        if filename.endswith(".pdf") or filename.endswith(".jpg"):
            full_filename = "" + downloadDir + "/" + filename
            print(f"Sending {full_filename} to Paperless...", flush=True)
            multipart_form_data = {
                'document': open(full_filename, 'rb')
            }

            headers_paperless = {
                "X-CSRFToken": client.cookies['csrftoken']
            }

            auth_paperless = {
                "username": paperless_login,
                "password": paperless_password
            }

            r = client.post(paperless_url + '/api/token/', headers=headers_paperless, data=auth_paperless)

            body = json.loads(r.text)
            api_token = body['token']

            header_token = {
                'Authorization': f"Token {api_token}",
                "X-CSRFToken": client.cookies['csrftoken']
            }

            client.post(paperless_url + '/api/documents/post_document/', files=multipart_form_data, headers=header_token)
            print("done")
        else:
            continue


def delete_downloaded_documents():
    files = glob.glob(f"{downloadDir}/*")
    for f in files:
        os.remove(f)


def authenticate_paperless():
    client = requests.session()
    # # Retrieve the CSRF token first
    client.get(paperless_url)  # sets cookie
    if 'csrftoken' in client.cookies:
        # Django 1.6 and up
        csrftoken = client.cookies['csrftoken']
    else:
        # older versions
        csrftoken = client.cookies['csrf']

    login_data = dict(username=paperless_login, password=paperless_password, csrfmiddlewaretoken=csrftoken, next='/')
    client.post(paperless_url + '/login', data=login_data, headers=dict(Referer=paperless_url + '/login'))
    return client

while True:
    if is_scanner_available():
        print("Scanner is available", flush=True)
        download_available_pdfs()
        created_client = authenticate_paperless()
        upload_downloaded_documents(created_client)
        delete_downloaded_documents()
        delete_all_pdfs()
        pdfsToDownload = []
        time.sleep(30)
    else:
        print(
            f"Scanner not available at {scanner_url}. Will check again automatically in {checkScannerInterval} seconds.\n", flush=True)
        time.sleep(checkScannerInterval)
