const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const STANDALONE_ROOT = path.join(__dirname, '.next', 'standalone');

function findServerJs(rootDir) {
  if (!fs.existsSync(rootDir)) {
    return null;
  }

  const queue = [rootDir];

  while (queue.length) {
    const currentDir = queue.shift();
    const serverPath = path.join(currentDir, 'server.js');

    if (fs.existsSync(serverPath)) {
      return serverPath;
    }

    const entries = fs.readdirSync(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        queue.push(path.join(currentDir, entry.name));
      }
    }
  }

  return null;
}

const serverJsPath = findServerJs(STANDALONE_ROOT);

if (!serverJsPath) {
  console.error('Unable to locate server.js inside .next/standalone. Did you run `npm run build`?');
  process.exit(1);
}

const child = spawn('node', [serverJsPath, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: process.env,
});

child.on('exit', (code) => {
  process.exit(code);
});
