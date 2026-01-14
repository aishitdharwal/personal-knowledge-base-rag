#!/usr/bin/env python3
"""
OCR Troubleshooting Script
Tests and fixes common OCR issues
"""

import os
import sys
import subprocess

def check_command(cmd):
    """Check if a command is available"""
    try:
        subprocess.run([cmd, '--version'], capture_output=True, check=True)
        return True
    except:
        return False

def find_tessdata():
    """Find tessdata directory"""
    possible_paths = [
        '/usr/share/tesseract-ocr/5/tessdata',
        '/usr/share/tesseract-ocr/4/tessdata',
        '/usr/share/tessdata',
        '/opt/homebrew/share/tessdata',
        '/usr/local/share/tessdata',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def list_tesseract_languages(tessdata_path):
    """List available Tesseract languages"""
    if not tessdata_path or not os.path.exists(tessdata_path):
        return []
    
    languages = []
    for file in os.listdir(tessdata_path):
        if file.endswith('.traineddata'):
            lang = file.replace('.traineddata', '')
            languages.append(lang)
    
    return sorted(languages)

def main():
    print("=" * 60)
    print("OCR Troubleshooting Script")
    print("=" * 60)
    print()
    
    # Check Tesseract
    print("1. Checking Tesseract...")
    if check_command('tesseract'):
        result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
        version = result.stdout.split('\n')[0]
        print(f"   ✅ Tesseract found: {version}")
        
        # Find tessdata
        tessdata_path = find_tessdata()
        if tessdata_path:
            print(f"   ✅ Tessdata found: {tessdata_path}")
            
            # List languages
            languages = list_tesseract_languages(tessdata_path)
            print(f"   ✅ Available languages: {', '.join(languages)}")
            
            if 'eng' not in languages:
                print("   ⚠️  WARNING: 'eng' language not found!")
                print("      Install with: sudo apt-get install tesseract-ocr-eng")
            
            # Generate config update
            print()
            print("   Suggested config.py update:")
            print(f"   TESSDATA_PREFIX = '{tessdata_path}'")
            print(f"   OCR_LANGUAGES = ['eng']  # Change to match your needs")
            
        else:
            print("   ❌ Tessdata directory not found!")
            print("      Tesseract may not be properly installed")
    else:
        print("   ❌ Tesseract not found")
        print("      Install with:")
        print("        macOS: brew install tesseract")
        print("        Ubuntu: sudo apt-get install tesseract-ocr")
    
    print()
    
    # Check Poppler
    print("2. Checking Poppler (PDF to image)...")
    if check_command('pdftoppm'):
        print("   ✅ Poppler found")
    else:
        print("   ❌ Poppler not found")
        print("      Install with:")
        print("        macOS: brew install poppler")
        print("        Ubuntu: sudo apt-get install poppler-utils")
    
    print()
    
    # Check Python packages
    print("3. Checking Python packages...")
    
    packages = {
        'pytesseract': 'pip install pytesseract',
        'pdf2image': 'pip install pdf2image',
        'PIL': 'pip install pillow',
        'easyocr': 'pip install easyocr',
        'certifi': 'pip install certifi'
    }
    
    for package, install_cmd in packages.items():
        try:
            if package == 'PIL':
                import PIL
            else:
                __import__(package)
            print(f"   ✅ {package} installed")
        except ImportError:
            print(f"   ❌ {package} not installed")
            print(f"      Install with: {install_cmd}")
    
    print()
    
    # Check environment variables
    print("4. Checking environment variables...")
    tessdata_env = os.environ.get('TESSDATA_PREFIX')
    if tessdata_env:
        print(f"   ✅ TESSDATA_PREFIX set: {tessdata_env}")
    else:
        print("   ⚠️  TESSDATA_PREFIX not set")
        print("      This will be set automatically by the app")
    
    print()
    
    # Test Tesseract
    print("5. Testing Tesseract OCR...")
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Create a simple test image
        img = Image.new('RGB', (200, 50), color='white')
        
        # Try OCR
        tessdata_path = find_tessdata()
        if tessdata_path:
            os.environ['TESSDATA_PREFIX'] = tessdata_path
        
        text = pytesseract.image_to_string(img, lang='eng')
        print("   ✅ Tesseract test successful")
        
    except Exception as e:
        print(f"   ❌ Tesseract test failed: {str(e)}")
    
    print()
    
    # Summary
    print("=" * 60)
    print("Summary:")
    print("=" * 60)
    
    tessdata_path = find_tessdata()
    if tessdata_path:
        print()
        print("Add this to your app/config.py:")
        print(f"TESSDATA_PREFIX = '{tessdata_path}'")
        print("OCR_LANGUAGES = ['eng']  # or ['eng', 'spa', etc.]")
        print()
        print("Then restart the application with: python run.py")
    else:
        print()
        print("Please install Tesseract first!")
    
    print()

if __name__ == '__main__':
    main()
