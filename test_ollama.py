import requests

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
}

data = '{\n  "model": "llama3.2",\n  "prompt": "Why is the sky blue?",\n"stream":false}'

response = requests.post('http://13.126.154.253:11434/api/generate', headers=headers, data=data)

print(response.json()['response'])