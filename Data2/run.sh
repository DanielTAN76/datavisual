#!/bin/bash
export STREAMLIT_HOME="./.streamlit"
python3 -m streamlit run app.py --server.headless true
