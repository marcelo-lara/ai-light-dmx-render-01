import logging

from src.app import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()
