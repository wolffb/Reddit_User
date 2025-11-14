#!/bin/bash

# Setup script for RedditUser conda environment

echo "Creating conda environment: RedditUser"
conda create -n RedditUser python=3.11 -y

echo "Activating RedditUser environment"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate RedditUser

echo "Installing required packages"
pip install -r requirements.txt

echo ""
echo "Setup complete! To activate the environment, run:"
echo "  conda activate RedditUser"
echo ""
echo "Don't forget to:"
echo "  1. Copy .env.example to .env and fill in your credentials"
echo "  2. Ensure LM Studio is running on http://localhost:1234"
echo "  3. Run: python main.py"
