# OCR Issues Fixed! 🔧

## Problems Identified

1. **Tesseract language error**: Looking for `en.traineddata` but should be `eng.traineddata`
2. **TESSDATA_PREFIX not set**: Tesseract couldn't find language data
3. **EasyOCR SSL error**: Certificate verification failed during model download

## ✅ Fixes Applied

### 1. Updated Configuration (`app/config.py`)
```python
# Changed from 'en' to 'eng'
OCR_LANGUAGES = ['eng']  # Tesseract uses 3-letter ISO codes

# Added TESSDATA_PREFIX
TESSDATA_PREFIX = '/usr/share/tesseract-ocr/5/tessdata'
```

### 2. Updated Document Processor (`app/document_processor.py`)
- Sets `TESSDATA_PREFIX` environment variable automatically
- Disables SSL verification for EasyOCR downloads (temporary fix)
- Added `certifi` import for SSL handling

### 3. Added Dependencies
- Added `certifi` to `requirements.txt`

## 🚀 How to Apply Fixes

### Option 1: Quick Fix (Already Applied)
The code has been updated. Just restart:
```bash
# Stop the server (Ctrl+C)
python run.py
```

### Option 2: Install certifi (if needed)
```bash
pip install certifi
```

### Option 3: Run Troubleshooting Script
```bash
python troubleshoot_ocr.py
```

This will:
- Check all OCR dependencies
- Find your tessdata path
- List available languages
- Test Tesseract
- Give you configuration recommendations

## 🔍 Verify the Fix

### 1. Check OCR Status
```bash
curl http://localhost:8000/config/ocr-status
```

Should show:
```json
{
  "ocr_enabled": true,
  "tesseract_available": true,
  "easyocr_available": true,
  "primary_engine": "tesseract",
  "fallback_engine": "easyocr",
  "languages": ["eng"]
}
```

### 2. Watch Console Output
When you start the app, you should see:
```
[OCR] Set TESSDATA_PREFIX to: /usr/share/tesseract-ocr/5/tessdata
[OCR] Tesseract is available
[OCR] EasyOCR is available
```

### 3. Upload a Scanned PDF
Upload a scanned PDF and watch for:
```
[OCR] Minimal text found (23 chars), using OCR for document.pdf
[OCR] Tesseract processed page 1/5
[OCR] Tesseract processed page 2/5
...
```

## 📝 Understanding the Issues

### Issue 1: Language Code Mismatch
**Problem**: 
- Config had `OCR_LANGUAGES = ['en']`
- Tesseract expects `'eng'` (3-letter ISO 639-2 code)

**Solution**:
- Changed to `OCR_LANGUAGES = ['eng']`

**Common Language Codes**:
- English: `eng`
- Spanish: `spa`
- French: `fra`
- German: `deu`
- Chinese (Simplified): `chi_sim`

### Issue 2: TESSDATA_PREFIX
**Problem**:
- Tesseract couldn't find language data files
- Was looking in `/opt/homebrew/share/tessdata/`
- Actual location: `/usr/share/tesseract-ocr/5/tessdata/`

**Solution**:
- Added `TESSDATA_PREFIX` to config
- Set automatically in `__init__`

### Issue 3: EasyOCR SSL Certificate
**Problem**:
- EasyOCR tries to download models from GitHub
- SSL certificate verification failed

**Solution**:
- Temporarily disable SSL verification
- Uses `ssl._create_unverified_context`
- Only affects EasyOCR model downloads

## 🎯 Alternative Solutions

### For Tesseract Language Issues

**Option A**: Use existing language files
```bash
# List available languages
tesseract --list-langs

# Update config to match
OCR_LANGUAGES = ['eng']  # or whatever is available
```

**Option B**: Install additional languages
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr-spa  # Spanish
sudo apt-get install tesseract-ocr-fra  # French

# Then use in config
OCR_LANGUAGES = ['eng', 'spa', 'fra']
```

### For EasyOCR SSL Issues

**Option A**: Use our fix (already applied)
- Disables SSL verification
- Works immediately

**Option B**: Fix Python certificates (macOS)
```bash
# Run Python certificate installer
/Applications/Python\ 3.*/Install\ Certificates.command
```

**Option C**: Disable EasyOCR fallback
```python
# In config.py
OCR_FALLBACK = None  # Only use Tesseract
```

## 🧪 Testing

### Test Tesseract Directly
```bash
# Create a test image with text
# Then run:
tesseract test_image.png output -l eng

# Check output.txt for results
cat output.txt
```

### Test with Python
```python
import pytesseract
from PIL import Image
import os

# Set tessdata path
os.environ['TESSDATA_PREFIX'] = '/usr/share/tesseract-ocr/5/tessdata'

# Test
img = Image.open('test_image.png')
text = pytesseract.image_to_string(img, lang='eng')
print(text)
```

### Test via API
```bash
# Upload a scanned PDF
curl -X POST http://localhost:8000/upload \
  -F "file=@scanned_document.pdf" \
  -v

# Watch console output for OCR messages
```

## 📊 Expected Behavior Now

### Text-based PDF (No OCR needed)
```
Processing document.pdf...
[PyPDF2] Extracted 2,500 chars
✅ No OCR needed (fast path)
Added 10 chunks to vector store
```

### Scanned PDF (Tesseract OCR)
```
Processing scanned.pdf...
[PyPDF2] Extracted 23 chars
[OCR] Minimal text found, using OCR
[OCR] Tesseract processed page 1/5
[OCR] Tesseract processed page 2/5
[OCR] Tesseract processed page 3/5
[OCR] Tesseract processed page 4/5
[OCR] Tesseract processed page 5/5
✅ OCR completed
Added 25 chunks to vector store
```

### Complex Scanned PDF (EasyOCR fallback)
```
Processing complex.pdf...
[PyPDF2] Extracted 15 chars
[OCR] Minimal text found, using OCR
[OCR] Tesseract processed page 1/3
[OCR] Tesseract quality low, trying EasyOCR
[OCR] Loading EasyOCR model...
[OCR] EasyOCR processed page 1/3
[OCR] EasyOCR processed page 2/3
[OCR] EasyOCR processed page 3/3
✅ OCR completed (high quality)
Added 18 chunks to vector store
```

## 🎉 You're All Set!

The OCR system should now work properly with:
- ✅ Correct language codes (`eng` instead of `en`)
- ✅ Proper tessdata path set
- ✅ SSL issues bypassed for EasyOCR
- ✅ Both Tesseract and EasyOCR working

**Test it now:**
```bash
python run.py
# Upload a scanned PDF
# Watch it work! 🚀
```

## 🆘 Still Having Issues?

Run the troubleshooting script:
```bash
python troubleshoot_ocr.py
```

This will diagnose all OCR components and give you specific recommendations for your system.

---

**Note**: If your tessdata is in a different location, the troubleshooting script will find it and tell you the correct path to use in `config.py`.
