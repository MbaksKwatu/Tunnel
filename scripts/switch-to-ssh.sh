#!/bin/bash
# Switch git remote from HTTPS to SSH
# Run this from your terminal: ./scripts/switch-to-ssh.sh

cd "$(dirname "$0")/.."

echo "🔄 Switching git remote to SSH..."
git remote set-url origin git@github.com:MbaksKwatu/Tunnel.git

echo "✅ Remote updated to SSH"
echo ""
echo "📋 Current remote:"
git remote -v
echo ""
echo "⚠️  Note: You still need SSH keys set up with GitHub for this to work."
echo "   See: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
