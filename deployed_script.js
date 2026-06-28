
          var _dbg = document.getElementById('js-debug');
          if (_dbg) { _dbg.style.background = '#cce5ff'; _dbg.style.color = '#004085'; _dbg.textContent = 'тП│ ╨╖╨░╨┐╤Г╤Б╨║...'; }

          if (typeof Promise !== 'function') {
              window.Promise = function(fn) {
                  var _thens = [], _err;
                  var p = {};
                  p.then = function(cb) { _thens.push(cb); return p; };
                  p.catch = function(cb) { _err = cb; return p; };
                  fn(function(v) { for (var i=0;i<_thens.length;i++) _thens[i](v); }, function(e) { if (_err) _err(e); });
                  return p;
              };
          }

          /* show error on screen */
          window.onerror = function(m, u, l) {
              var e = document.getElementById('auth-user-section');
              if (e) e.innerHTML = 'тЪая╕П ╨Ю╤И╨╕╨▒╨║╨░: ' + m + ' [' + l + ']';
              var d = document.getElementById('js-debug');
              if (d) { d.style.background = '#f8d7da'; d.style.color = '#721c24'; d.textContent = 'тЭМ ╨Ю╤И╨╕╨▒╨║╨░: ' + m; }
          };
          if (_dbg) { _dbg.style.background = '#d4edda'; _dbg.style.color = '#155724'; _dbg.textContent = 'тЬЕ onerror ╤Г╤Б╤В╨░╨╜╨╛╨▓╨╗╨╡╨╜'; }

          var BASE = '/api/budget';
          var USER_ID = (window.location.search.match(/[?&]user_id=([^&]*)/) || [,''])[1] || localStorage.getItem('budget_user_id') || '';
          USER_ID = '2091908459' || USER_ID;
          var STATE = { family: null, debts: [], members: [] };
          if (_dbg) { _dbg.textContent = 'тЬЕ JS ╤А╨░╨▒╨╛╤В╨░╨╡╤В, ID=' + USER_ID; }

          function saveUserId() {
              var v = document.getElementById('auth-user-id').value.trim();
              if (!v) { showToast('╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╨▓╨░╤И ID'); return; }
              USER_ID = v;
              localStorage.setItem('budget_user_id', v);
              showToast('ID ╤Б╨╛╤Е╤А╨░╨╜╤С╨╜. ╨Ч╨░╨│╤А╤Г╨╢╨░╤О...');
              loadDashboard();
          }

          function api(method, path, body) {
              if (typeof fetch !== 'undefined') {
                  var opts = { method: method, headers: { 'Content-Type': 'application/json', 'X-User-Id': USER_ID } };
                  if (body) { opts.body = JSON.stringify(body); }
                  return fetch(BASE + path, opts).then(function(res) { return res.json(); });
              }
              // fallback for very old browsers without fetch
              return new Promise(function(resolve, reject) {
                  var xhr = new XMLHttpRequest();
                  xhr.open(method, BASE + path, true);
                  xhr.setRequestHeader('Content-Type', 'application/json');
                  xhr.setRequestHeader('X-User-Id', USER_ID);
                  xhr.onreadystatechange = function() {
                      if (xhr.readyState === 4) {
                          if (xhr.status >= 200 && xhr.status < 300) {
                              resolve(JSON.parse(xhr.responseText));
                          } else {
                              reject(new Error('HTTP ' + xhr.status));
                          }
                      }
                  };
                  xhr.send(body ? JSON.stringify(body) : null);
              });
          }

          function get(path) { return api('GET', path); }
          function post(path, data) { return api('POST', path, data); }
          function del(path) { return api('DELETE', path); }

          function showToast(msg) {
              var t = document.createElement('div');
              t.className = 'toast';
              t.textContent = msg;
              document.body.appendChild(t);
              setTimeout(function() { t.remove(); }, 2500);
          }

          function showScreen(id) {
              var screens = document.querySelectorAll('.screen');
              for (var i = 0; i < screens.length; i++) { screens[i].classList.remove('active'); }
              document.getElementById(id).classList.add('active');
          }

          function showAuth() { showScreen('screen-auth'); }
          function showCreateFamily() { showScreen('screen-create-family'); }
          function showJoinFamily() { showScreen('screen-join-family'); }

          function logout() {
              USER_ID = '';
              STATE = { family: null, debts: [], members: [] };
              showAuth();
          }

          function createFamily() {
              var name = document.getElementById('family-name').value.trim();
              var displayName = document.getElementById('create-display-name').value.trim() || '╨г╤З╨░╤Б╤В╨╜╨╕╨║';
              if (!name) { showToast('╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╨╜╨░╨╖╨▓╨░╨╜╨╕╨╡ ╤Б╨╡╨╝╤М╨╕'); return; }
              post('/family/create', { name: name, display_name: displayName }).then(function(res) {
                  if (res.error) { showToast(res.error); return; }
                  STATE.family = res.family;
                  showToast('╨б╨╡╨╝╤М╤П ╤Б╨╛╨╖╨┤╨░╨╜╨░! ╨Ъ╨╛╨┤: ' + res.family.invite_code);
                  loadDashboard();
              }).catch(function(e) { showToast('╨Ю╤И╨╕╨▒╨║╨░: ' + e.message); });
          }

          function joinFamily() {
              var code = document.getElementById('invite-code').value.trim();
              var displayName = document.getElementById('join-display-name').value.trim() || '╨г╤З╨░╤Б╤В╨╜╨╕╨║';
              if (!code) { showToast('╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╨║╨╛╨┤ ╨┐╤А╨╕╨│╨╗╨░╤И╨╡╨╜╨╕╤П'); return; }
              post('/family/join', { code: code, display_name: displayName }).then(function(res) {
                  if (res.error) { showToast(res.error); return; }
                  STATE.family = res.family;
                  showToast('╨Т╤Л ╨┐╤А╨╕╤Б╨╛╨╡╨┤╨╕╨╜╨╕╨╗╨╕╤Б╤М ╨║ ╤Б╨╡╨╝╤М╨╡!');
                  loadDashboard();
              }).catch(function(e) { showToast('╨Ю╤И╨╕╨▒╨║╨░: ' + e.message); });
          }

          function loadDashboard() {
              if (!USER_ID) { showToast('╨Э╨╡╨╛╨▒╤Е╨╛╨┤╨╕╨╝╨░ ╨░╨▓╤В╨╛╤А╨╕╨╖╨░╤Ж╨╕╤П'); showAuth(); return; }
              get('/family/status?user_id=' + USER_ID).then(function(status) {
                  if (!status.family) { showAuth(); return; }
                  STATE.family = status.family;
                  document.getElementById('dash-family-name').textContent = 'ЁЯПа ' + status.family.name;
                  document.getElementById('dash-invite-code').textContent = '╨Ъ╨╛╨┤ ╨┐╤А╨╕╨│╨╗╨░╤И╨╡╨╜╨╕╤П: ' + status.family.invite_code;
                  STATE.members = status.family.members || [];
                  renderMembers();
                  get('/debts?family_id=' + status.family.id + '&user_id=' + USER_ID).then(function(debtsRes) {
                      STATE.debts = debtsRes.debts || [];
                      renderDebts();
                      get('/balance?family_id=' + status.family.id + '&user_id=' + USER_ID).then(function(balanceRes) {
                          renderBalances(balanceRes.balances || []);
                          showScreen('screen-dashboard');
                      });
                  });
              }).catch(function(e) { console.log('loadDashboard error', e); showAuth(); });
          }

          function renderMembers() {
              var el = document.getElementById('member-list');
              var html = '';
              for (var i = 0; i < STATE.members.length; i++) {
                  html += '<div class="row"><span class="debt-text">' + esc(STATE.members[i].display_name) + '</span></div>';
              }
              el.innerHTML = html;
          }

          function renderDebts() {
              var el = document.getElementById('debt-list');
              var empty = document.getElementById('debt-empty');
              if (!STATE.debts.length) {
                  el.innerHTML = '';
                  empty.classList.remove('hidden');
                  return;
              }
              empty.classList.add('hidden');
              var html = '';
              for (var i = 0; i < STATE.debts.length; i++) {
                  var d = STATE.debts[i];
                  var debtorName = getUserName(d.debtor_id);
                  var creditorName = getUserName(d.creditor_id);
                  html += '<div class="row">' +
                      '<div class="debt-info"><div class="debt-text">' + esc(debtorName) + ' тЖТ ' + esc(creditorName) + '</div>' +
                      '<div class="debt-amount">' + d.amount_left + ' тВ╜</div></div>' +
                      '<button class="btn btn-small btn-primary" onclick="showPayDebt('' + esc(d.debtor_id) + '','' + esc(d.creditor_id) + '',' + d.amount_left + ')">╨Я╨╛╨│╨░╤Б╨╕╤В╤М</button>' +
                      '</div>';
              }
              el.innerHTML = html;
          }

          function renderBalances(balances) {
              var el = document.getElementById('balance-bar');
              var html = '';
              for (var i = 0; i < balances.length; i++) {
                  var b = balances[i];
                  var name = getUserName(b.user_id);
                  var cls = b.net >= 0 ? 'positive' : 'negative';
                  var sign = b.net >= 0 ? '+' : '';
                  html += '<div class="balance-item"><div class="name">' + esc(name) + '</div>' +
                      '<div class="amount ' + cls + '">' + sign + b.net + '</div></div>';
              }
              el.innerHTML = html;
          }

          function getUserName(userId) {
              for (var i = 0; i < STATE.members.length; i++) {
                  if (STATE.members[i].user_id === userId) { return STATE.members[i].display_name; }
              }
              return userId;
          }

          function esc(s) {
              var d = document.createElement('div');
              d.textContent = s;
              return d.innerHTML;
          }

          function showAddExpense() {
              var payerEl = document.getElementById('expense-payer');
              var forWhomEl = document.getElementById('expense-for-whom');
              var payerHtml = '';
              var forWhomHtml = '';
              for (var i = 0; i < STATE.members.length; i++) {
                  var m = STATE.members[i];
                  payerHtml += '<option value="' + esc(m.user_id) + '">' + esc(m.display_name) + '</option>';
                  forWhomHtml += '<label style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
                      '<input type="checkbox" value="' + esc(m.user_id) + '">' + esc(m.display_name) + '</label>';
              }
              payerEl.innerHTML = payerHtml;
              forWhomEl.innerHTML = forWhomHtml;
              document.getElementById('expense-amount').value = '';
              document.getElementById('expense-description').value = '';
              showScreen('screen-add-expense');
          }

          function createExpense() {
              var payerId = document.getElementById('expense-payer').value;
              var checkboxes = document.querySelectorAll('#expense-for-whom input[type=checkbox]:checked');
              var forWhomIds = [];
              for (var i = 0; i < checkboxes.length; i++) { forWhomIds.push(checkboxes[i].value); }
              var amount = parseInt(document.getElementById('expense-amount').value);
              var category = document.getElementById('expense-category').value;
              var description = document.getElementById('expense-description').value.trim();
              if (!forWhomIds.length) { showToast('╨Т╤Л╨▒╨╡╤А╨╕╤В╨╡, ╨╖╨░ ╨║╨╛╨│╨╛ ╨╖╨░╨┐╨╗╨░╤В╨╕╨╗╨╕'); return; }
              if (!amount || amount <= 0) { showToast('╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Г╤О ╤Б╤Г╨╝╨╝╤Г'); return; }
              post('/transactions', {
                  family_id: STATE.family.id,
                  payer_id: payerId,
                  amount: amount,
                  category: category,
                  description: description,
                  for_whom_ids: forWhomIds
              }).then(function(res) {
                  if (res.error) { showToast(res.error); return; }
                  showToast('╨в╤А╨░╤В╨░ ╨┤╨╛╨▒╨░╨▓╨╗╨╡╨╜╨░!');
                  loadDashboard();
              }).catch(function(e) { showToast('╨Ю╤И╨╕╨▒╨║╨░: ' + e.message); });
          }

          var _payData = null;

          function showPayDebt(debtorId, creditorId, amountLeft) {
              _payData = { debtor_id: debtorId, creditor_id: creditorId };
              document.getElementById('pay-debtor-display').textContent = 'ЁЯСд ' + getUserName(debtorId);
              document.getElementById('pay-creditor-display').textContent = 'ЁЯСд ' + getUserName(creditorId);
              document.getElementById('pay-amount').value = amountLeft;
              document.getElementById('pay-amount').max = amountLeft;
              showScreen('screen-pay-debt');
          }

          function payDebt() {
              var amount = parseInt(document.getElementById('pay-amount').value);
              if (!amount || amount <= 0) { showToast('╨Т╨▓╨╡╨┤╨╕╤В╨╡ ╨║╨╛╤А╤А╨╡╨║╤В╨╜╤Г╤О ╤Б╤Г╨╝╨╝╤Г'); return; }
              post('/debts/pay', {
                  family_id: STATE.family.id,
                  debtor_id: _payData.debtor_id,
                  creditor_id: _payData.creditor_id,
                  amount: amount
              }).then(function(res) {
                  if (res.error) { showToast(res.error); return; }
                  showToast('╨Ф╨╛╨╗╨│ ╨┐╨╛╨│╨░╤И╨╡╨╜!');
                  loadDashboard();
              }).catch(function(e) { showToast('╨Ю╤И╨╕╨▒╨║╨░: ' + e.message); });
          }

          function initPage() {
              document.getElementById('auth-user-id').value = USER_ID;
              (document.getElementById('auth-user-section')||{}).innerHTML = 'тЬЕ JS ╤А╨░╨▒╨╛╤В╨░╨╡╤В (ES5)';
              var d = document.getElementById('js-debug');
              if (d) { d.textContent = 'тЬЕ ╨У╨╛╤В╨╛╨▓! USER_ID=' + USER_ID; d.style.background = '#d4edda'; d.style.color = '#155724'; }
          }
          initPage();
    