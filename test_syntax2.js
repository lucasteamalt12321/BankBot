const fs = require('fs');
const vm = require('vm');

// Try reading with different encodings
let html;
try {
    html = fs.readFileSync(process.argv[2], 'utf8');
} catch(e) {
    html = fs.readFileSync(process.argv[2], 'latin1');
}

const s = html.indexOf('<script>');
if (s < 0) { console.log('No script tag found'); process.exit(1); }
const e = html.indexOf('</script>', s);
const script = html.substring(s + 8, e);

// Write script to file for inspection
fs.writeFileSync('deployed_script.js', script, 'utf8');
console.log('Script length:', script.length);
console.log('First 100 chars:', script.substring(0, 100));

try {
    new vm.Script(script);
    console.log('✅ Script parses OK');
} catch(err) {
    console.log('❌ Syntax error:', err.message);
    const lines = script.split('\n');
    // Parse line number from error message
    const m = err.stack ? err.stack.match(/:(\d+):\d+\)/) : null;
    const lineNum = m ? parseInt(m[1]) : 1;
    const context = 3;
    for (let i = Math.max(0, lineNum - context - 1); i < Math.min(lines.length, lineNum + context); i++) {
        console.log(`${i+1}: ${lines[i]}`);
    }
}
