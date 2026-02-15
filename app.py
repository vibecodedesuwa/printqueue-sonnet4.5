#!/usr/bin/env python3
"""
Print Queue Manager — Entry Point
"""
from dotenv import load_dotenv
load_dotenv(override=True)

from printqueue import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
