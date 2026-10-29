// Trusted data-only observer. Never imports or executes repository modules.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
// Only owned observer controls pass a synthetic argv root; production passes none.
const root = process.argv[1] || '/workspace/repository';
const rows = [];
let bytes = 0;
function visit(relative) {
  if (rows.length >= 200000) throw new Error('source tree entry bound');
  const full = relative === '.' ? root : path.join(root, relative);
  const stat = fs.lstatSync(full);
  if (stat.isSymbolicLink()) {
    rows.push([relative, 'symlink', fs.readlinkSync(full)]);
  } else if (stat.isDirectory()) {
    rows.push([relative, 'directory']);
    for (const child of fs.readdirSync(full)) visit(relative === '.' ? child : relative + '/' + child);
  } else if (stat.isFile()) {
    if (stat.size > 134217728) throw new Error('source tree file bound');
    bytes += stat.size;
    if (bytes > 2147483648) throw new Error('source tree expanded bound');
    rows.push([relative, 'file', crypto.createHash('sha256').update(fs.readFileSync(full)).digest('hex'), stat.size]);
  } else {
    rows.push([relative, 'special']);
  }
}
visit('.');
rows.sort((a, b) => Buffer.compare(Buffer.from(a[0]), Buffer.from(b[0])));
const raw = rows.map(row => JSON.stringify(row) + '\n').join('');
console.log(JSON.stringify({sha256: crypto.createHash('sha256').update(raw).digest('hex'), entries: rows.length, bytes}));
