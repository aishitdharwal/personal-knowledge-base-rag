# Python Stops Working - Diagnostic Guide 🔍

## Quick Diagnosis

The most likely causes when Python stops working on upload:

### 1. **EasyOCR Memory Issue** (Most Likely)
EasyOCR loads large models into memory which can crash Python on systems with limited RAM.

### 2. **PDF Conversion Hanging**
pdf2image might hang on certain PDFs.

### 3. **Missing Dependencies**
Some OCR library isn't properly installed.

## 🚨 Quick Fix - Disable OCR Temporarily

**Step 1**: Edit `app/config.py`
```python
# Change this line:
OCR_ENABLED = False  # Temporarily disable OCR

# Comment out or leave other OCR settings as-is
```

**Step 2**: Restart
```bash
python run.py
```

**Step 3**: Try uploading again
- If it works → OCR is the problem
- If it still crashes → Different issue

## 🔍 Detailed Diagnostics

### Check Console Output

When you upload, watch the console for:

```
[PDF] Processing: /path/to/file.pdf
[PDF] Extracted X characters via PyPDF2
[OCR] Minimal text found (X chars), triggering OCR
[OCR] Converting PDF to images...
[OCR] Converting with DPI=200...
```

**Where does it stop?**

#### Stops at "Converting PDF to images"
**Problem**: pdf2image/poppler issue
**Solution**:
```bash
# Reinstall poppler
brew reinstall poppler  # macOS
# or
sudo apt-get install --reinstall poppler-utils  # Linux
```

#### Stops at "Loading EasyOCR model"
**Problem**: EasyOCR downloading/loading models
**Solutions**:
1. **Wait**: First download takes 5-10 minutes
2. **Check internet**: Models download from GitHub
3. **Check disk space**: Models are ~500MB

#### Stops at "EasyOCR processing page X"
**Problem**: Out of memory
**Solutions**:
1. Use Tesseract instead (lighter)
2. Add more RAM
3. Process smaller PDFs

### Memory Check

```bash
# Check available memory
free -h  # Linux
top      # macOS (press 'q' to quit)
```

**EasyOCR needs:**
- Minimum: 2GB free RAM
- Recommended: 4GB+ free RAM

## 🛠️ Solution Options

### Option 1: Use Tesseract (Lighter, Faster)

Edit `app/config.py`:
```python
OCR_ENABLED = True
OCR_PRIMARY = "tesseract"
OCR_FALLBACK = None  # Disable fallback
OCR_LANGUAGES = ['en']
```

**Pros**: Fast, low memory (~200MB)
**Cons**: Lower quality than EasyOCR

### Option 2: Disable OCR for Scanned PDFs

Edit `app/config.py`:
```python
OCR_ENABLED = False
```

**Pros**: No crashes, very fast
**Cons**: Scanned PDFs won't work

### Option 3: Increase Trigger Threshold

Edit `app/config.py`:
```python
OCR_MIN_TEXT_LENGTH = 1000  # Only trigger OCR if <1000 chars
```

**Pros**: Most text PDFs skip OCR
**Cons**: Some scanned PDFs might skip OCR

### Option 4: Process One Page at a Time (Advanced)

Edit `app/document_processor.py`, line ~171:
```python
# Change:
images = convert_from_path(file_path, dpi=200)

# To:
images = convert_from_path(file_path, dpi=150, first_page=1, last_page=1)
```

**Pros**: Lower memory usage
**Cons**: Only processes first page

## 🧪 Step-by-Step Testing

### Test 1: Disable OCR
```bash
# Edit app/config.py
OCR_ENABLED = False

# Restart
python run.py

# Upload a text PDF
# Should work ✅
```

### Test 2: Enable Tesseract Only
```bash
# Edit app/config.py
OCR_ENABLED = True
OCR_PRIMARY = "tesseract"
OCR_FALLBACK = None

# Restart
python run.py

# Upload a PDF
# Watch console
```

### Test 3: Enable EasyOCR (if Test 2 works)
```bash
# Edit app/config.py
OCR_PRIMARY = "easyocr"

# Restart
python run.py

# Upload a SMALL PDF (1-2 pages)
# Watch memory usage
```

## 📊 What to Tell Me

If it still crashes, please share:

1. **Where it stops** (exact console message)
2. **PDF details** (pages, size, scanned or text)
3. **System specs** (RAM, OS)
4. **Error message** (if any)

For example:
```
Console output:
[PDF] Processing: document.pdf
[PDF] Extracted 25 characters via PyPDF2
[OCR] Minimal text found, triggering OCR
[OCR] Converting PDF to images...
[OCR] Converting with DPI=200...
<Python stops here>

PDF: 10 pages, 5MB, scanned
RAM: 8GB total, 2GB free
OS: Ubuntu 22.04
Error: None, just hangs
```

## 🚀 Quick Fix Commands

### Disable OCR (Fastest)
```bash
# Edit app/config.py, set:
OCR_ENABLED = False

# Restart
python run.py
```

### Use Tesseract (Lighter)
```bash
# Edit app/config.py, set:
OCR_ENABLED = True
OCR_PRIMARY = "tesseract"
OCR_FALLBACK = None

# Restart
python run.py
```

### Check Dependencies
```bash
# Run diagnostic
python troubleshoot_ocr.py

# Should show what's available
```

## 💡 Common Solutions

### "Python hangs at EasyOCR loading"
**Cause**: Downloading models
**Solution**: Wait 5-10 minutes, check internet

### "Python crashes immediately"
**Cause**: Missing dependencies
**Solution**: 
```bash
pip install --upgrade easyocr torch numpy
```

### "Out of memory error"
**Cause**: Not enough RAM
**Solution**: Use Tesseract or disable OCR

### "PDF conversion fails"
**Cause**: Poppler not installed
**Solution**:
```bash
brew install poppler  # macOS
sudo apt-get install poppler-utils  # Linux
```

## 🎯 Recommended Configuration

For most systems:
```python
# app/config.py
OCR_ENABLED = True
OCR_PRIMARY = "tesseract"  # Fast and stable
OCR_FALLBACK = None        # Don't use EasyOCR unless needed
OCR_MIN_TEXT_LENGTH = 100
OCR_LANGUAGES = ['en']
```

This gives you:
- ✅ OCR support for scanned PDFs
- ✅ Low memory usage
- ✅ Fast processing
- ✅ Stable (no crashes)

Trade-off:
- ❌ Slightly lower quality than EasyOCR (90-95% vs 95-98%)

## 📞 Need More Help?

Share the output of:
```bash
# 1. Check OCR status
python troubleshoot_ocr.py

# 2. Check system memory
free -h  # Linux
# or
top  # macOS

# 3. Try uploading with verbose output
python run.py
# Then upload and copy ALL console output
```

---

**Most likely fix**: Switch to Tesseract or disable OCR
