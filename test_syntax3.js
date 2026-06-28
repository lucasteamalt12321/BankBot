const fs = require('fs');

const buf = fs.readFileSync(process.argv[2]);
const html = buf.toString('utf8').replace(/^\uFEFF/, '');

const s = html.indexOf('<script>');
if (s < 0) { 
    // Try with different BOM/encoding
    const html2 = buf.toString('latin1');
    const s2 = html2.indexOf('<script>');
    if (s2 < 0) {
        console.log('No script tag found at all');
        // Check what the file contains
        console.log('First 100 bytes:', buf.slice(0, 100).toString('hex'));
        console.log('First 100 chars utf8:', html.substring(0, 100));
        console.log('First 100 chars latin1:', html2.substring(0, 100));
        process.exit(1);
    }
    const e2 = html2.indexOf('</script>', s2);
    const script2 = html2.substring(s2 + 8, e2);
    console.log('Script found (latin1 encoding), length:', script2.length);
    fs.writeFileSync('deployed_script.js', script2, 'utf8');
    process.exit(0);
}

const e = html.indexOf('</script>', s);
const script = html.substring(s + 8, e);
console.log('Script length:', script.length);
fs.writeFileSync('deployed_script.js', script, 'utf8');
console.log('Saved to deployed_script.js');
