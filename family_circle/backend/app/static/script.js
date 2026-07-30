const API_BASE = '/api';

// --- Utils ---
function $(id) { return document.getElementById(id); }

function showError(id, msg) {
    const el = $(id);
    if (el) { el.textContent = msg; el.style.display = msg ? 'block' : 'none'; }
}

function hide(el) {
    if (el) el.style.display = 'none';
}

function show(el, display) {
    if (el) el.style.display = display || 'block';
}

function store(key, val) {
    try { sessionStorage.setItem('fc_' + key, val); } catch(e) {}
}

function load(key) {
    try { return sessionStorage.getItem('fc_' + key); } catch(e) { return null; }
}

async function api(method, path, body) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API_BASE + path, opts);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || 'Ошибка сервера');
    return data;
}

// --- Index page: create room ---
(function() {
    const createBtn = $('createBtn');
    if (!createBtn) return;

    createBtn.addEventListener('click', async () => {
        const name = $('roomName').value.trim() || 'Семейный совет';
        const participants = parseInt($('participants').value) || 2;

        showError('createError', '');
        createBtn.disabled = true;
        createBtn.textContent = 'Создаём...';

        try {
            const data = await api('POST', '/rooms', { name, participants_total: participants });

            $('roomIdDisplay').textContent = 'ID комнаты: ' + data.room_id;
            const link = window.location.origin + '/room.html?room_id=' + data.room_id;
            $('inviteLink').innerHTML = 'Ссылка: <a href="' + link + '">' + link + '</a>';

            const passDiv = $('passwordDisplay');
            passDiv.innerHTML = '<h3 style="font-size:14px;margin-bottom:8px;">Пароли участников (сохраните их!):</h3>';
            for (const [name, pass] of Object.entries(data.passwords)) {
                passDiv.innerHTML += '<div class="entry"><span class="name">' + name + '</span><span class="pass">' + pass + '</span></div>';
            }

            show($('resultCard'));
            $('goToRoomBtn').onclick = () => {
                window.location.href = 'room.html?room_id=' + data.room_id;
            };
        } catch (err) {
            showError('createError', err.message);
        } finally {
            createBtn.disabled = false;
            createBtn.textContent = 'Создать комнату';
        }
    });
})();

// --- Room page: login + chat ---
(function() {
    const loginBtn = $('loginBtn');
    if (!loginBtn) return;

    // Load room_id from URL
    function cleanRoomId(val) {
        return val.split('?')[0].split('&')[0].trim();
    }
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('room_id')) {
        $('roomIdInput').value = cleanRoomId(urlParams.get('room_id'));
        loadRoomInfo(cleanRoomId(urlParams.get('room_id')));
    }

    $('roomIdInput').addEventListener('change', () => {
        const rid = $('roomIdInput').value.trim();
        if (rid) loadRoomInfo(rid);
    });

    // Restore session
    const savedRoom = load('room_id');
    const savedName = load('member_name');
    const savedPass = load('password');
    if (savedRoom && savedName && savedPass) {
        $('roomIdInput').value = savedRoom;
        loadRoomInfo(savedRoom, savedName, savedPass);
    }

    async function loadRoomInfo(roomId, autoName, autoPass) {
        try {
            const data = await api('GET', '/rooms/' + roomId);
            $('roomSubtitle').textContent = 'Комната: ' + data.name;

            const sel = $('memberSelect');
            sel.innerHTML = '';
            data.members.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                sel.appendChild(opt);
            });

            if (autoName && data.members.includes(autoName)) {
                sel.value = autoName;
                $('passwordInput').value = autoPass || '';
                tryLogin();
            }
        } catch (err) {
            showError('loginError', 'Не удалось загрузить комнату: ' + err.message);
        }
    }

    loginBtn.addEventListener('click', tryLogin);

    async function tryLogin() {
        const roomId = $('roomIdInput').value.trim();
        const memberName = $('memberSelect').value;
        const password = $('passwordInput').value.trim();

        if (!roomId || !memberName || !password) {
            showError('loginError', 'Заполните все поля');
            return;
        }

        showError('loginError', '');
        loginBtn.disabled = true;

        try {
            // Verify by trying to get room info (password check happens later in chat)
            const cleanId = cleanRoomId(roomId);
            const data = await api('GET', '/rooms/' + cleanId);
            if (!data.members.includes(memberName)) {
                throw new Error('Участник не найден в этой комнате');
            }

            store('room_id', cleanId);
            store('member_name', memberName);
            store('password', password);

            $('roomSubtitle').textContent = 'Комната: ' + data.name;
            $('roomInfo').innerHTML = '';
            const infoHtml = `
                <div class="info-row"><span class="info-label">Статус</span><span class="info-value">${data.status === 'active' ? 'Активна' : data.status}</span></div>
                <div class="info-row"><span class="info-label">Высказалось</span><span class="info-value">${data.spoke_count}/${data.participants_total}</span></div>
                <div class="info-row"><span class="info-label">Участники</span><span class="info-value">${data.members.join(', ')}</span></div>
            `;
            $('roomInfo').innerHTML = infoHtml;

            hide($('loginCard'));
            show($('chatCard'));

            // Load existing messages if any
            const msgInput = $('messageInput');
            msgInput.focus();

        } catch (err) {
            showError('loginError', err.message);
        } finally {
            loginBtn.disabled = false;
        }
    }

    // --- Chat ---
    const sendBtn = $('sendBtn');
    const msgInput = $('messageInput');
    const chatLog = $('chatLog');
    const typing = $('typing');

    msgInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    });

    sendBtn.addEventListener('click', async () => {
        const text = msgInput.value.trim();
        if (!text) return;

        const roomId = load('room_id');
        const memberName = load('member_name');
        const password = load('password');

        if (!roomId || !memberName || !password) {
            showError('chatError', 'Сессия потеряна. Войдите заново.');
            return;
        }

        showError('chatError', '');
        sendBtn.disabled = true;
        msgInput.disabled = true;

        addMessage('user', memberName, text);
        msgInput.value = '';
        show(typing);

        try {
            const data = await api('POST', '/chat/send', {
                room_id: roomId,
                member_name: memberName,
                password: password,
                message: text,
            });

            hide(typing);
            addMessage('ai', 'Медиатор', data.response);

            if (data.intent_type) {
                console.log('Intent:', data.intent_type);
            }
        } catch (err) {
            hide(typing);
            showError('chatError', err.message);
        } finally {
            sendBtn.disabled = false;
            msgInput.disabled = false;
            msgInput.focus();
        }
    });

    function addMessage(type, label, text) {
        const div = document.createElement('div');
        div.className = 'msg ' + type;
        div.innerHTML = '<div class="label">' + label + '</div>' + escapeHtml(text);
        chatLog.appendChild(div);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // --- Finish ---
    $('finishBtn').addEventListener('click', async () => {
        if (!confirm('Вы уверены, что хотите завершить диалог? После этого вы не сможете писать в этой комнате.')) return;

        const roomId = load('room_id');
        const memberName = load('member_name');
        const password = load('password');

        try {
            await api('POST', '/chat/finish', {
                room_id: roomId,
                member_name: memberName,
                password: password,
            });

            sendBtn.disabled = true;
            msgInput.disabled = true;
            $('finishBtn').disabled = true;
            $('finishBtn').textContent = '✓ Диалог завершён';

            showError('chatError', '');
            show($('reportReady'));

        } catch (err) {
            showError('chatError', err.message);
        }
    });

    // --- Report ---
    $('reportBtn').addEventListener('click', () => {
        const roomId = load('room_id');
        const memberName = load('member_name');
        const password = load('password');
        window.location.href = 'result.html?room_id=' + roomId + '&name=' + encodeURIComponent(memberName) + '&pass=' + encodeURIComponent(password);
    });
})();

// --- Result page ---
(function() {
    const getReportBtn = $('getReportBtn');
    if (!getReportBtn) return;

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('room_id') && urlParams.get('name') && urlParams.get('pass')) {
        $('roomIdInput').value = urlParams.get('room_id');
        loadMembers(urlParams.get('room_id'), urlParams.get('name'), urlParams.get('pass'));
    }

    $('roomIdInput').addEventListener('change', () => {
        const rid = $('roomIdInput').value.trim();
        if (rid) loadMembers(rid);
    });

    async function loadMembers(roomId, autoName, autoPass) {
        try {
            const data = await api('GET', '/rooms/' + roomId);
            const sel = $('memberSelect');
            sel.innerHTML = '';
            data.members.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                sel.appendChild(opt);
            });
            if (autoName) {
                sel.value = autoName;
                $('passwordInput').value = autoPass || '';
                fetchReport();
            }
        } catch (err) {
            showError('reportError', err.message);
        }
    }

    getReportBtn.addEventListener('click', fetchReport);

    async function fetchReport() {
        const roomId = $('roomIdInput').value.trim();
        const memberName = $('memberSelect').value;
        const password = $('passwordInput').value.trim();

        if (!roomId || !memberName || !password) {
            showError('reportError', 'Заполните все поля');
            return;
        }

        showError('reportError', '');
        getReportBtn.disabled = true;
        getReportBtn.textContent = 'Генерируем...';

        try {
            const data = await api('POST', '/report/generate', {
                room_id: roomId,
                member_name: memberName,
                password: password,
            });

            $('reportTitle').textContent = 'Отчёт по комнате';
            $('reportContent').innerHTML = formatReport(data.report_text);
            show($('reportCard'));
        } catch (err) {
            showError('reportError', err.message);
        } finally {
            getReportBtn.disabled = false;
            getReportBtn.textContent = 'Получить отчёт';
        }
    }

    function formatReport(text) {
        // Simple markdown-to-HTML
        let html = text
            .replace(/### \d+\.\s+(.+)/g, '</div><div class="report-section"><h3>$1</h3>')
            .replace(/- (.+)/g, '<li>$1</li>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');

        html = html.replace(/<li>/g, '<ul><li>');
        html = html.replace(/<\/li>(?![\s\S]*?<\/li>)/g, '</li></ul>');

        return '<div class="report-section" style="margin-top:0;">' + html + '</div>';
    }

    $('printBtn').addEventListener('click', () => {
        window.print();
    });
})();
