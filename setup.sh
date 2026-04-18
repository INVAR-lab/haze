#!/bin/bash
set -e

if ! command -v terraform &> /dev/null; then
  echo "  terraform not found: https://developer.hashicorp.com/terraform/downloads"
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
pip install -q rich click

echo ""
echo "  done. to activate:"
echo "  source .venv/bin/activate"
