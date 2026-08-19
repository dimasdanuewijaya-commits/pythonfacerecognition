#!/bin/bash
# Shortcut untuk menjalankan backend dengan mudah
source .venv/bin/activate
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
