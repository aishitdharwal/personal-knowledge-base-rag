# Quick OCR Disable Script
# Use this to test if OCR is causing the crash

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import *

print("=" * 60)
print("Quick OCR Configuration")
print("=" * 60)
print()

choice = input("Choose mode:\n1. Disable OCR (test uploads)\n2. Enable with Tesseract only (fast)\n3. Enable with EasyOCR only (quality)\n4. Enable both (full)\n\nChoice (1-4): ")

if choice == "1":
    print("\n✅ Disabling OCR...")
    print("\nAdd to app/config.py:")
    print("OCR_ENABLED = False")
    
elif choice == "2":
    print("\n✅ Enabling Tesseract only...")
    print("\nAdd to app/config.py:")
    print("OCR_ENABLED = True")
    print("OCR_PRIMARY = 'tesseract'")
    print("OCR_FALLBACK = None")
    
elif choice == "3":
    print("\n✅ Enabling EasyOCR only...")
    print("\nAdd to app/config.py:")
    print("OCR_ENABLED = True")
    print("OCR_PRIMARY = 'easyocr'")
    print("OCR_FALLBACK = None")
    
elif choice == "4":
    print("\n✅ Enabling both OCR engines...")
    print("\nAdd to app/config.py:")
    print("OCR_ENABLED = True")
    print("OCR_PRIMARY = 'easyocr'")
    print("OCR_FALLBACK = 'tesseract'")
else:
    print("Invalid choice")

print("\nThen restart: python run.py")
