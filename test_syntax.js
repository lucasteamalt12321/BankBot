const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(process.argv[2], 'utf8');
const s = html.indexOf('<script>');
const e = html.indexOf('</script>', s);
const script = html.substring(s + 8, e);

// Try to parse the script
try {
    new vm.Script(script);
    console.log('✅ Script parses OK');
} catch(err) {
    console.log('❌ Syntax error:', err.message);
    // Find the approximate location
    const lines = script.split('\n');
    if (err.stack) {
        const match = err.stack.match(/:(\d+)/);
        if (match) {
            const lineNum = parseInt(match[1]);
            console.log(`Around line ${lineNum-1}:`, lines[lineNum-2]?.trim());
            console.log(`Around line ${lineNum}:`, lines[lineNum-1]?.trim());
            console.log(`Around line ${lineNum+1}:`, lines[lineNum]?.trim());
        }
    }
}
