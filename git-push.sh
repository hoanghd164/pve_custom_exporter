#!/bin/bash
# git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/hoanghd164/pve_custom_exporter.git
git pull origin main --allow-unrelated-histories
git push -u origin main