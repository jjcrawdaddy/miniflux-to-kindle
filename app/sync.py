import logging
from datetime import date

from epub_builder import build_epub
from email_sender import send_epub
from miniflux_client import MinifluxClient

logger = logging.getLogger(__name__)
