import datetime
import glob
import json
import logging
import os
import time
from xml.etree import ElementTree
from requests.auth import HTTPBasicAuth
import requests
import uuid as uuid
import settings
import logger

log = logging.getLogger('syncScanLogger')

headers = {
    'Content-type': 'application/json',
}
auth = HTTPBasicAuth(settings.scanner_username, settings.scanner_password)

pdfs_to_download = []
jpgs_to_download = []
check_scanner_interval: int = 60
download_dir = "./temp"


def is_scanner_available():
    try:
        response = requests.get(settings.scanner_url, auth=auth, timeout=3)
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
    local_filename = f"{download_dir}/{date}_{uuid.uuid4()}.pdf"
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename


def download_available_pdfs():
    response = requests.get(settings.scanner_url + '/:sda1/DCIM:.xml:Document:Sub', auth=auth)
    string_xml = response.content
    try:
        root = ElementTree.fromstring(string_xml)
        for pdf in root.iter('ALLFile'):
            for doc in pdf.iter('Document'):
                for attr in doc.iter('FPATH'):
                    pdfs_to_download.append(attr.text)

        counter = len(pdfs_to_download)
        if counter > 0:
            log.info(f"{counter} new PDF file(s) being synced...")
            for dl in pdfs_to_download:
                download_pdf_file(settings.scanner_url + dl)
    except ElementTree.ParseError:
        log.debug("Invalid content received from API ignoring it for now")

def download_available_jpgs():
    response = requests.get(settings.scanner_url + '/:sda1/DCIM:.xml:Picture:Sub', auth=auth)
    string_xml = response.content
    try:
        root = ElementTree.fromstring(string_xml)
        for pdf in root.iter('ALLFile'):
            for doc in pdf.iter('Picture'):
                for attr in doc.iter('FPATH'):
                    jpgs_to_download.append(attr.text)

        counter = len(jpgs_to_download)
        if counter > 0:
            log.info(f"{counter} new JPG file(s) being synced...")
            for dl in jpgs_to_download:
                download_jpg_file(settings.scanner_url + dl)
    except ElementTree.ParseError:
        log.debug("Invalid content received from API ignoring it for now")

def download_jpg_file(url):
    date = datetime.date.today()
    local_filename = f"{download_dir}/{date}_{uuid.uuid4()}.jpg"
    # NOTE the stream=True parameter below
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

# delete docs
def delete_file(document_name, type):
    multipart_form_data = {
        'multiDelete': 'Delete Select File',
        'currentPage': 'Current_page=[1]',
        'multiUploadToFB': '',
        document_name: 'on'
    }

    if type == 'PDF':
        urlSuffix = '/.xmlpdf.page_index=1.chipsipcmd'
    else:
        urlSuffix = '/.xmljpg.page_index=1.chipsipcmd'

    r = requests.post(settings.scanner_url + urlSuffix, files=multipart_form_data, auth=auth)
    if r.status_code == 200:
        log.info(f"Success ({document_name})")


def delete_all_pdfs_from_scanner_sd_card():
    for dl in pdfs_to_download:
        delete_file(dl, 'PDF')


def delete_all_jpgs_from_scanner_sd_card():
    for dl in jpgs_to_download:
        delete_file(dl, 'JPG')


def upload_downloaded_documents_to_paperless(client):
    directory = os.fsencode(download_dir)

    for file in os.listdir(directory):
        filename = os.fsdecode(file)

        if filename.endswith(".pdf") or filename.endswith(".jpg"):
            log.info(filename)
            full_filename = "" + download_dir + "/" + filename
            log.info(f"Sending {full_filename} to Paperless...")
            multipart_form_data = {
                'document': open(full_filename, 'rb')
            }

            headers_paperless = {
                "X-CSRFToken": client.cookies['csrftoken']
            }

            auth_paperless = {
                "username": settings.paperless_username,
                "password": settings.paperless_password
            }
            r = client.post(settings.paperless_url + '/api/token/', headers=headers_paperless, data=auth_paperless)

            body = json.loads(r.text)
            api_token = body['token']
            header_token = {
                'Authorization': f"Token {api_token}",
                "X-CSRFToken": client.cookies['csrftoken']
            }

            client.post(settings.paperless_url + '/api/documents/post_document/', files=multipart_form_data,
                        headers=header_token)
            log.info("done")
        else:
            continue


def delete_downloaded_documents_from_disk():
    files = glob.glob(f"{download_dir}/*")
    for f in files:
        if not f.endswith(".gitkeep"):
            os.remove(f)


def authenticate_paperless():
    client = requests.session()
    # # Retrieve the CSRF token first
    client.get(settings.paperless_url)  # sets cookie
    if 'csrftoken' in client.cookies:
        # Django 1.6 and up
        csrftoken = client.cookies['csrftoken']
    else:
        # older versions
        csrftoken = client.cookies['csrf']

    login_data = dict(username=settings.paperless_username, password=settings.paperless_password,
                      csrfmiddlewaretoken=csrftoken, next='/')
    client.post(settings.paperless_url + '/login', data=login_data,
                headers=dict(Referer=settings.paperless_url + '/login'))
    return client


def sync_pdfs():
    download_available_pdfs()
    created_client = authenticate_paperless()
    upload_downloaded_documents_to_paperless(created_client)
    delete_downloaded_documents_from_disk()
    delete_all_pdfs_from_scanner_sd_card()
    global pdfs_to_download
    pdfs_to_download = []


def sync_jpgs():
    download_available_jpgs()
    created_client = authenticate_paperless()
    upload_downloaded_documents_to_paperless(created_client)
    delete_downloaded_documents_from_disk()
    delete_all_jpgs_from_scanner_sd_card()
    global jpgs_to_download
    jpgs_to_download = []


try:
    log.info("Starting sync brother scan")
    while True:
        if is_scanner_available():
            log.info("Scanner is available")
            sync_pdfs()
            sync_jpgs()
            time.sleep(30)
        else:
            log.info(
                f"Scanner not available at {settings.scanner_url}. Will check again automatically in {check_scanner_interval} seconds.\n")
            time.sleep(check_scanner_interval)
except KeyboardInterrupt:
    log.warning('Application stopped by user')
