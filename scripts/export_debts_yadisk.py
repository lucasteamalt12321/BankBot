#!/usr/bin/env python3
"""
Export active debts to JSON and upload to Yandex.Disk.

Usage:
    python scripts/export_debts_yadisk.py [YANDEX_TOKEN]

Requires DATABASE_URL env var or .env file in config/ or project root.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from sqlalchemy import create_engine, text

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to load .env
try:
    from dotenv import load_dotenv

    for env_path in [
        project_root / "config" / ".env.local",
        project_root / "config" / ".env",
        project_root / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

YANDEX_API = "https://cloud-api.yandex.net/v1/disk/resources/upload"


def get_db_url() -> str:
    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("SUPABASE_DB_URL")
    )
    if not url:
        raise SystemExit("FATAL: DATABASE_URL not found in env or .env files")
    return url


def fetch_debts(engine) -> list[dict]:
    """Fetch active debts with debtor/creditor names, reason, category."""
    query = text("""
        SELECT
            fm_debtor.display_name AS debtor_name,
            fm_creditor.display_name AS creditor_name,
            d.amount_left,
            bt.description,
            bt.category
        FROM debts d
        JOIN budget_transactions bt
            ON bt.family_id = d.family_id
        JOIN transaction_details td
            ON td.transaction_id = bt.id AND td.for_whom_id = d.debtor_id
        JOIN family_members fm_debtor
            ON fm_debtor.user_id = d.debtor_id AND fm_debtor.family_id = d.family_id
        JOIN family_members fm_creditor
            ON fm_creditor.user_id = d.creditor_id AND fm_creditor.family_id = d.family_id
        WHERE d.amount_left > 0
        ORDER BY d.created_at ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    result = []
    for row in rows:
        result.append({
            "from": row["debtor_name"],
            "to": row["creditor_name"],
            "amount": row["amount_left"],
            "reason": row["description"] or "—",
            "category": row["category"] or "Прочее",
        })
    return result


def upload_to_yadisk(token: str, remote_path: str, content: str | bytes) -> str:
    """Upload a file to Yandex.Disk. Returns public URL."""
    # Step 1: get upload URL
    params = {"path": remote_path, "overwrite": "true"}
    headers = {"Authorization": f"OAuth {token}"}
    resp = requests.get(YANDEX_API, params=params, headers=headers, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to get upload URL: {resp.status_code} {resp.text[:200]}"
        )
    upload_url = resp.json().get("href")
    if not upload_url:
        raise RuntimeError("No upload URL in response")

    # Step 2: upload content
    data = content.encode("utf-8") if isinstance(content, str) else content
    resp = requests.put(upload_url, data=data, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to upload file: {resp.status_code} {resp.text[:200]}"
        )

    # Step 3: make public
    pub_headers = {"Authorization": f"OAuth {token}"}
    pub_resp = requests.put(
        "https://cloud-api.yandex.net/v1/disk/resources/publish",
        params={"path": remote_path},
        headers=pub_headers,
        timeout=10,
    )
    if pub_resp.status_code in (200, 201):
        return pub_resp.json().get("public_url", "")
    return ""


def build_debts_html() -> str:
    """Return the HTML page that will be uploaded alongside debts.json."""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Список долгов</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 900px; margin: 32px auto; padding: 0 16px; color: #333; }
    h1 { margin-top: 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: left; }
    th { background-color: #f5f5f5; color: #444; position: sticky; top: 0; z-index: 10; }
    tr:nth-child(even) { background-color: #fafafa; }
    .amount { font-weight: bold; color: #2c3e50; }
    .reason { color: #666; }
    .empty { color: #888; font-style: italic; }
    .error { color: #d32f2f; }
    #loading { margin-top: 20px; color: #666; }
    @media (max-width: 600px) {
      table { display: block; overflow-x: auto; }
    }
  </style>
</head>
<body>
  <h1>Список долгов</h1>
  <div id="loading">Загрузка данных…</div>
  <table id="debts-table" style="display:none;">
    <thead>
      <tr>
        <th>Кто должен</th>
        <th>Кому</th>
        <th>Сумма, ₽</th>
        <th>Причина</th>
        <th>Категория</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
  <p id="error" style="display:none;"></p>

  <script>
    var jsonUrl = "debts.json";

    function escapeHtml(str) {
      if (typeof str !== 'string') return '';
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    async function loadDebts() {
      var tbody = document.querySelector('#debts-table tbody');
      var loading = document.getElementById('loading');
      var table = document.getElementById('debts-table');
      var errorEl = document.getElementById('error');

      try {
        var res = await fetch(jsonUrl);
        if (!res.ok) throw new Error('Ошибка сети или доступа');
        var data = await res.json();
        loading.style.display = 'none';
        errorEl.style.display = 'none';

        if (!Array.isArray(data) || data.length === 0) {
          table.style.display = 'table';
          tbody.innerHTML = '<tr><td colspan="5" class="empty">Долгов нет</td></tr>';
          return;
        }

        table.style.display = 'table';
        data.forEach(function(d) {
          var row = '<tr>' +
            '<td>' + escapeHtml(d.from || '—') + '</td>' +
            '<td>' + escapeHtml(d.to || '—') + '</td>' +
            '<td class="amount">' + escapeHtml(String(d.amount || 0)) + '</td>' +
            '<td class="reason">' + escapeHtml(d.reason || '—') + '</td>' +
            '<td>' + escapeHtml(d.category || 'Прочее') + '</td>' +
            '</tr>';
          tbody.innerHTML += row;
        });
      } catch (e) {
        console.error(e);
        loading.style.display = 'none';
        errorEl.textContent = 'Не удалось загрузить список долгов. Проверьте подключение.';
        errorEl.style.display = 'block';
      }
    }

    loadDebts();
  </script>
</body>
</html>"""


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else os.getenv("YANDEX_DISK_TOKEN")
    if not token:
        print("Usage: python scripts/export_debts_yadisk.py [YANDEX_TOKEN]")
        print("Or set YANDEX_DISK_TOKEN env var")
        sys.exit(1)

    db_url = get_db_url()
    engine = create_engine(db_url)

    print("Fetching debts from database...")
    debts = fetch_debts(engine)
    print(f"Found {len(debts)} active debts.")

    json_content = json.dumps(debts, ensure_ascii=False, indent=2)

    print("Uploading debts.json to Yandex.Disk...")
    json_url = upload_to_yadisk(token, "/debts.json", json_content)
    if json_url:
        print(f"JSON uploaded: {json_url}")
    else:
        print("JSON uploaded (no public URL)")

    print("Uploading debts.html to Yandex.Disk...")
    html_content = build_debts_html()
    html_url = upload_to_yadisk(token, "/debts.html", html_content)
    if html_url:
        print(f"HTML uploaded: {html_url}")
    else:
        print("HTML uploaded (no public URL)")

    print("Done!")


if __name__ == "__main__":
    main()
