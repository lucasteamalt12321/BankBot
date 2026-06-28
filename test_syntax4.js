const fs = require('fs');

const buf = fs.readFileSync(process.argv[2]);
// UTF-16LE with BOM
const html = buf.toString('utf16le').replace(/^\uFEFF/, '');

const s = html.indexOf('<script>');
if (s < 0) { console.log('No script tag'); process.exit(1); }

const e = html.indexOf('</script>', s);
const script = html.substring(s + 8, e);
console.log('Script length:', script.length);
fs.writeFileSync('deployed_script.js', script, 'utf8');
console.log('Saved to deployed_script.js');
