const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36'
    });
    const page = await context.newPage();

    // collect console messages
    const logs = [];
    page.on('console', msg => logs.push(msg.type() + ': ' + msg.text()));
    page.on('pageerror', err => logs.push('PAGE_ERROR: ' + err.message));

    await page.goto('https://bank-bot-ruby.vercel.app/family_budget?user_id=2091908459', { waitUntil: 'load', timeout: 20000 });

    console.log('=== PAGE LOADED ===');
    console.log('Title:', await page.title());

    // check js-debug panel
    const debugText = await page.textContent('#js-debug');
    console.log('js-debug text:', debugText);

    // check auth section
    const authSection = await page.textContent('#auth-user-section');
    console.log('auth-section text:', authSection);

    // check input value
    const inputVal = await page.inputValue('#auth-user-id');
    console.log('auth-user-id value:', inputVal);

    // check buttons exist
    const createBtn = await page.$('button[onclick*="showCreateFamily"]');
    const joinBtn = await page.$('button[onclick*="showJoinFamily"]');
    const saveBtn = await page.$('button[onclick*="saveUserId"]');
    console.log('Create button exists:', !!createBtn);
    console.log('Join button exists:', !!joinBtn);
    console.log('Save button exists:', !!saveBtn);

    // try clicking Create Family
    if (createBtn) {
        await createBtn.click();
        await page.waitForTimeout(500);
        const createScreen = await page.$('#screen-create-family.active');
        console.log('Create family screen active after click:', !!createScreen);
    }

    // try clicking Join
    if (joinBtn) {
        await joinBtn.click();
        await page.waitForTimeout(500);
        const joinScreen = await page.$('#screen-join-family.active');
        console.log('Join family screen active after click:', !!joinScreen);
    }

    // check if any function is defined
    try {
        const fnCheck = await page.evaluate(() => typeof showCreateFamily);
        console.log('typeof showCreateFamily:', fnCheck);
    } catch(e) {
        console.log('evaluate error:', e.message);
    }

    // check for syntax errors
    try {
        const hasError = await page.evaluate(() => {
            var d = document.getElementById('js-debug');
            return d ? d.textContent : 'no-debug-el';
        });
        console.log('js-debug evaluate:', hasError);
    } catch(e) {
        console.log('evaluate error on debug:', e.message);
    }

    console.log('=== CONSOLE LOGS ===');
    logs.forEach(l => console.log(l));

    await browser.close();
})();
