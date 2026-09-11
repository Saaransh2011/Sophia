#!/bin/bash
set -e

echo "==> Pushing Sophia repository to GitHub..."
git branch -M main
git push -u origin main
echo "==> Successfully pushed to GitHub!"
