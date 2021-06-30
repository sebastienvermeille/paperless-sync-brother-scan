import logging

from decouple import config, Choices

# scanner
scanner_url = config('SCANNER_URL', default='localhost')
scanner_username = config('SCANNER_USERNAME', default='admin')
scanner_password = config('SCANNER_PASSWORD', default='1234')

# paperless-ng
paperless_url = config('PAPERLESS_URL', default='localhost')
paperless_username = config('PAPERLESS_USERNAME', default='admin')
paperless_password = config('PAPERLESS_PASSWORD', default='1234')
