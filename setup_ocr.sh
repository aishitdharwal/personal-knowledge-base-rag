#!/bin/bash

# OCR Setup Script for Personal Knowledge Base
# This script helps install OCR dependencies on different platforms

echo "🔍 OCR Setup Script for Personal Knowledge Base"
echo "================================================"
echo ""

# Detect OS
OS="Unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="Windows"
fi

echo "Detected OS: $OS"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Tesseract
echo "Checking Tesseract OCR..."
if command_exists tesseract; then
    VERSION=$(tesseract --version 2>&1 | head -n 1)
    echo "✅ Tesseract found: $VERSION"
else
    echo "❌ Tesseract not found"
    
    if [ "$OS" = "macOS" ]; then
        echo "   Install with: brew install tesseract"
    elif [ "$OS" = "Linux" ]; then
        echo "   Install with: sudo apt-get install tesseract-ocr"
    elif [ "$OS" = "Windows" ]; then
        echo "   Install with: choco install tesseract"
        echo "   Or download from: https://github.com/UB-Mannheim/tesseract/wiki"
    fi
fi

echo ""

# Check Poppler
echo "Checking Poppler (PDF to image)..."
if command_exists pdftoppm; then
    echo "✅ Poppler found"
else
    echo "❌ Poppler not found"
    
    if [ "$OS" = "macOS" ]; then
        echo "   Install with: brew install poppler"
    elif [ "$OS" = "Linux" ]; then
        echo "   Install with: sudo apt-get install poppler-utils"
    elif [ "$OS" = "Windows" ]; then
        echo "   Install with: choco install poppler"
        echo "   Or download from: https://github.com/oschwartz10612/poppler-windows/releases/"
    fi
fi

echo ""

# Check Python packages
echo "Checking Python OCR packages..."

if python3 -c "import pytesseract" 2>/dev/null; then
    echo "✅ pytesseract installed"
else
    echo "❌ pytesseract not installed"
    echo "   Install with: pip install pytesseract"
fi

if python3 -c "import pdf2image" 2>/dev/null; then
    echo "✅ pdf2image installed"
else
    echo "❌ pdf2image not installed"
    echo "   Install with: pip install pdf2image"
fi

if python3 -c "import PIL" 2>/dev/null; then
    echo "✅ Pillow installed"
else
    echo "❌ Pillow not installed"
    echo "   Install with: pip install pillow"
fi

if python3 -c "import easyocr" 2>/dev/null; then
    echo "✅ EasyOCR installed"
else
    echo "⚠️  EasyOCR not installed (optional, but recommended)"
    echo "   Install with: pip install easyocr"
fi

echo ""
echo "================================================"
echo "Summary:"
echo ""

# Installation instructions based on OS
if [ "$OS" = "macOS" ]; then
    echo "To install all dependencies on macOS:"
    echo ""
    echo "1. System dependencies:"
    echo "   brew install tesseract poppler"
    echo ""
    echo "2. Python packages:"
    echo "   pip install -r requirements.txt"
    
elif [ "$OS" = "Linux" ]; then
    echo "To install all dependencies on Linux:"
    echo ""
    echo "1. System dependencies:"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install tesseract-ocr poppler-utils"
    echo ""
    echo "2. Optional: Additional language packs:"
    echo "   sudo apt-get install tesseract-ocr-spa  # Spanish"
    echo "   sudo apt-get install tesseract-ocr-fra  # French"
    echo ""
    echo "3. Python packages:"
    echo "   pip install -r requirements.txt"
    
elif [ "$OS" = "Windows" ]; then
    echo "To install all dependencies on Windows:"
    echo ""
    echo "1. System dependencies (using Chocolatey):"
    echo "   choco install tesseract poppler"
    echo ""
    echo "2. Python packages:"
    echo "   pip install -r requirements.txt"
fi

echo ""
echo "After installation, test OCR with:"
echo "  python run.py"
echo "  Open http://localhost:8000"
echo "  Upload a scanned PDF"
echo ""
echo "Check OCR status at: http://localhost:8000/config/ocr-status"
echo ""
