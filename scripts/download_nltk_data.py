#!/usr/bin/env python3
"""Setup script to download required NLTK data."""

import os

import nltk

if __name__ == "__main__":
    download_dir = os.environ.get("NLTK_DATA")
    nltk.download("stopwords", quiet=True, download_dir=download_dir)
    print("NLTK data downloaded successfully")
