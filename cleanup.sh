#!/bin/bash

echo "🚀 Starting aggressive cleanup (Option B)..."

# ---- 1. Delete DB files ----
rm -f backend/*.db

# ---- 2. Delete test folders ----
rm -rf backend/test_data backend/test_output backend/test_sample_files backend/tests

# ---- 3. Keep only essential scripts ----
mkdir -p scripts
essential_scripts=("quick-start.sh" "start-production.sh" "start-simple.sh")

for file in scripts/*; do
    basename=$(basename "$file")
    if [[ ! " ${essential_scripts[@]} " =~ " ${basename} " ]]; then
        rm -f "scripts/$basename"
    fi
done

# ---- 4. Delete duplicate files ----
rm -f backend/co-pilot-tasks.md backend/co_pilot_tasks.md backend/co-pilot_tasks.md

# ---- 5. Delete archive folder ----
rm -rf archive

# ---- 6. Clean root directory ----
for item in *; do
    if [[ "$item" != "backend" && "$item" != "frontend" && "$item" != "docs" && "$item" != "scripts" && "$item" != "supabase" && "$item" != ".gitignore" && "$item" != "README.md" ]]; then
        rm -rf "$item"
    fi
done

# ---- 7. Replace .gitignore ----
cat <<EOF > .gitignore
# Python
__pycache__/
*.pyc
venv/
*.db

# Node
node_modules/
.next/
dist/
.output/

# Logs
*.log

# System
.DS_Store

# Local env files
.env
EOF

echo "🔥 Cleanup completed successfully!"
