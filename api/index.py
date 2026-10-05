import sys
import os

# Add the project root to the Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel expects the WSGI app to be exported as `app`
# This file acts as the serverless function entry point
