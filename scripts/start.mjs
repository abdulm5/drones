import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const python = `${root}/.venv/bin/python`;
if (!existsSync(python)) {
  console.error('Create .venv and install requirements.txt first. See README.md.');
  process.exit(1);
}
const api = spawn(python, ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000'], { cwd: root, stdio: 'inherit' });
const web = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort'], { cwd: root, stdio: 'inherit' });
let closing = false;
function close(code = 0) {
  if (closing) return;
  closing = true;
  api.kill('SIGTERM'); web.kill('SIGTERM');
  process.exitCode = code;
}
for (const child of [api, web]) {
  child.on('error', error => { console.error(error.message); close(1); });
  child.on('exit', code => close(code || 0));
}
process.on('SIGINT', () => close());
process.on('SIGTERM', () => close());
