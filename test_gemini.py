# -*- coding: utf-8 -*-
"""
Quick standalone test - verify the Gemini API key works.
"""
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

import requests
import json

API_KEY = "AIzaSyAAwuwWOBrs2Ay2L5pb_MuvmwaWe8nDZbc"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Models to try in order (free-tier friendly)
MODELS_TO_TRY = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash-lite",
]

payload = {
    "contents": [
        {"role": "user", "parts": [{"text": "Say 'HunterAI connected successfully' in one sentence."}]}
    ],
    "generationConfig": {
        "maxOutputTokens": 100,
        "temperature": 0.7
    }
}

working_model = None

for model in MODELS_TO_TRY:
    url = f"{BASE_URL}/models/{model}:generateContent?key={API_KEY}"
    print(f"[*] Testing model: {model} ...")
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        print(f"    HTTP Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"    [OK] SUCCESS! AI responded: {text.strip()}")
                working_model = model
                break
            except (KeyError, IndexError):
                print(f"    [!!] Got 200 but empty/blocked response")
        elif resp.status_code == 429:
            print(f"    [--] Rate limited, trying next model...")
        elif resp.status_code == 403:
            print(f"    [!!] API key not authorized for this model")
        else:
            print(f"    [!!] Error: {resp.text[:200]}")
    except Exception as e:
        print(f"    [!!] Connection error: {e}")

print()
if working_model:
    print(f"=== RESULT: API key WORKS with model '{working_model}' ===")
    print(f"=== This model will be set as default in HunterAI ===")
else:
    print("=== RESULT: No model worked. Key may be exhausted or invalid. ===")
    print("=== Get a new key at: https://aistudio.google.com/app/apikey ===")
