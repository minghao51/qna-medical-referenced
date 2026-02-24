#!/usr/bin/env python3
"""Setup script to download required NLTK data."""

import nltk

if __name__ == "__main__":
    nltk.download("stopwords", quiet=True)
    print("NLTK data downloaded successfully")
