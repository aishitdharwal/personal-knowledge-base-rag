# Quick Start Guide

## The Fastest Way to Get Running

### Step 1: Navigate to Project
```bash
cd /Users/aishitdharwal/Documents/personal-knowledge-assistant-v2
```

### Step 2: Install Dependencies (one time)
```bash
pip install -r requirements.txt
```

### Step 3: Set API Key
```bash
# Create .env file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-actual-key-here
```

### Step 4: Run the Application
```bash
python run.py
```

### Step 5: Open Browser
Go to: http://localhost:8000

---

## That's It! 🎉

You should see the Personal Knowledge Base interface.

### Common Issues

**Issue: "ModuleNotFoundError: No module named 'app'"**
- **Solution**: Always use `python run.py` instead of uvicorn directly
- The run.py script sets up Python paths correctly

**Issue: "No module named 'dotenv'"**
- **Solution**: Install dependencies: `pip install -r requirements.txt`

**Issue: "OpenAI API key not found"**
- **Solution**: Create `.env` file with your API key
  ```bash
  echo "OPENAI_API_KEY=sk-your-key" > .env
  ```

**Issue: Port 8000 already in use**
- **Solution**: Edit `run.py` and change port to 8001 (or any free port)

### Verify Installation

Check if all dependencies are installed:
```bash
python -c "import fastapi, openai, faiss, numpy; print('✅ All dependencies installed')"
```

### File Checklist

Before running, make sure you have:
- ✅ `requirements.txt` - Dependencies list
- ✅ `.env` - Your OpenAI API key (create from .env.example)
- ✅ `run.py` - Startup script
- ✅ `app/` directory - Backend code
- ✅ `templates/` directory - Frontend code

### First Steps After Running

1. **Upload a document** (txt or md file)
2. **Wait for processing** (you'll see chunk count)
3. **Ask a question** about your document
4. **See source citations** in the answer

### Stop the Server

Press `Ctrl+C` in the terminal where the server is running.

### Need Help?

Check the detailed guides:
- `README.md` - Project overview
- `SETUP.md` - Detailed setup instructions
- `TROUBLESHOOTING.md` - Common issues (this file)
