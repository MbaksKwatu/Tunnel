#!/bin/bash
# Push commits to GitHub
# Run this from your terminal: ./scripts/push-to-github.sh

cd "$(dirname "$0")/.."

echo "📤 Pushing commits to GitHub..."
echo ""

# Check if there are commits to push
COMMITS_AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")

if [ "$COMMITS_AHEAD" -eq "0" ]; then
    echo "✅ No commits to push. Everything is up to date."
    exit 0
fi

echo "📋 Commits to push:"
git log origin/main..HEAD --oneline
echo ""

# Push to GitHub
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed $COMMITS_AHEAD commit(s) to GitHub!"
else
    echo ""
    echo "❌ Push failed. Check your GitHub credentials and network connection."
    exit 1
fi
