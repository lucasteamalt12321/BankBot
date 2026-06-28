const fs = require('fs');
const vm = require('vm');

const script = fs.readFileSync('deployed_script.js', 'utf8');

console.log('Script length:', script.length);
console.log('---First 200---');
console.log(script.substring(0, 200));
console.log('---Last 200---');
console.log(script.substring(script.length - 200));

try {
    new vm.Script(script);
    console.log('✅ Script parses OK');
} catch(err) {
    console.log('❌ Syntax error:', err.message);
    const lines = script.split('\n');
    // Try to get the error line from the message or stack
    console.log('Stack:', err.stack);
    const m = err.stack ? err.stack.match(/:(\d+):(\d+)/) : null;
    if (m) {
        const lineNum = parseInt(m[1]);
        const colNum = parseInt(m[2]);
        console.log(`Error at line ${lineNum}, col ${colNum}`);
        for (let i = Math.max(0, lineNum - 3); i < Math.min(lines.length, lineNum + 2); i++) {
            console.log(`${i+1}: ${lines[i]}`);
            if (i === lineNum - 1) {
                console.log(' '.repeat(colNum + 3) + '^');
            }
        }
    } else {
        // just dump the whole thing
        lines.forEach((l, i) => console.log(`${i+1}: ${l}`));
    }
}
