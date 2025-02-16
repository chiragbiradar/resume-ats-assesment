#!/bin/bash
# post_install.sh

# Install Python dependencies
pip install -r requirements.txt

# Download NLTK data
python -m nltk.downloader punkt
