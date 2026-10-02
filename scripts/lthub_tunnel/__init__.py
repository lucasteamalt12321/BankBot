"""Обход блокировки Vercel-доменов из РФ через VPN-подписку.

Задача: открыть сайт проекта (Vercel) в обход фильтрации ``*.vercel.app``
через локальный прокси sing-box, собранный из готовой VPN-подписки.

Модули:
    nodes        разбор ``vless://`` / ``trojan://`` в нормализованные ноды
    subscriptions загрузка подписки (base64 и «голый» текст) и разбор
    sbconfig     сборка конфига sing-box (local mixed inbound + urltest)
    clash        экспорт того же набора нод в Clash/Mihomo YAML
    tunnel       CLI: install / build / check / up / export

Сеть затрагивает только ``tunnel``; остальные модули чистые и покрыты тестами.
"""

__all__ = ["nodes", "subscriptions", "sbconfig", "clash"]