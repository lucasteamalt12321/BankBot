# AI Model Manager — Recommended Models

**Дата:** 2026-05-24  
**Статус:** Production-ready

## 🎯 Выбранные модели для ротации

AI Manager настроен на использование 5 моделей Hugging Face с автоматической ротацией при ошибках.

### Пул моделей:

| # | Модель | Размер | Скорость | Качество | Русский | Назначение |
|---|--------|--------|----------|----------|---------|------------|
| 1 | **Qwen/Qwen2.5-0.5B-Instruct** | 0.5B | ⚡⚡⚡ | ⭐⭐⭐ | ✅ | Основная (быстрая, современная) |
| 2 | **google/flan-t5-base** | 250M | ⚡⚡⚡ | ⭐⭐ | ✅ | Надёжная (проверенная) |
| 3 | **microsoft/phi-2** | 2.7B | ⚡⚡ | ⭐⭐⭐⭐ | ✅ | Качественная (лучше для сложных задач) |
| 4 | **TinyLlama/TinyLlama-1.1B-Chat-v1.0** | 1.1B | ⚡⚡⚡ | ⭐⭐⭐ | ✅ | Быстрая (chat-optimized) |
| 5 | **HuggingFaceH4/zephyr-7b-beta** | 7B | ⚡ | ⭐⭐⭐⭐⭐ | ✅ | Запасная (лучшее качество) |

## 🔄 Логика ротации

1. **Первая попытка:** Qwen (самая быстрая и современная)
2. **При ошибке 429/500/timeout:** Переключение на flan-t5
3. **При повторной ошибке:** phi-2
4. **Далее:** tinyllama → zephyr
5. **Если все упали:** RuntimeError

## ⚙️ Конфигурация

### Вариант 1: JSON (рекомендуется)

Добавить в `.env` или `.env.local`:

```bash
HF_TOKEN=hf_your_token_here

AI_PROVIDERS='[{"name":"qwen","type":"huggingface","api_key":"${HF_TOKEN}","endpoint":"https://api-inference.huggingface.co/models","model":"Qwen/Qwen2.5-0.5B-Instruct","timeout":10,"max_tokens":150},{"name":"flan-t5","type":"huggingface","api_key":"${HF_TOKEN}","endpoint":"https://api-inference.huggingface.co/models","model":"google/flan-t5-base","timeout":10,"max_tokens":150},{"name":"phi-2","type":"huggingface","api_key":"${HF_TOKEN}","endpoint":"https://api-inference.huggingface.co/models","model":"microsoft/phi-2","timeout":15,"max_tokens":150},{"name":"tinyllama","type":"huggingface","api_key":"${HF_TOKEN}","endpoint":"https://api-inference.huggingface.co/models","model":"TinyLlama/TinyLlama-1.1B-Chat-v1.0","timeout":10,"max_tokens":150},{"name":"zephyr","type":"huggingface","api_key":"${HF_TOKEN}","endpoint":"https://api-inference.huggingface.co/models","model":"HuggingFaceH4/zephyr-7b-beta","timeout":20,"max_tokens":150}]'
```

**Примечание:** `${HF_TOKEN}` будет заменён на значение переменной окружения.

### Вариант 2: Одна модель (fallback)

Если `AI_PROVIDERS` не задан, используется одна модель:

```bash
HF_INFERENCE_TOKEN=hf_your_token_here
HF_INFERENCE_MODEL=Qwen/Qwen2.5-0.5B-Instruct
```

## 📊 Преимущества ротации

1. **Отказоустойчивость:** Если одна модель недоступна, автоматически переключается на следующую
2. **Обход rate limits:** Распределение нагрузки между моделями
3. **Разнообразие:** Разные модели дают разные стили ответов
4. **Оптимизация скорости:** Быстрые модели первыми, медленные — запасные

## 🧪 Тестирование

Проверить доступность моделей:

```bash
# Запустить тесты AI Manager
python3 -m pytest tests/unit/test_ai_model_manager.py -v

# Проверить конфигурацию
python3 -c "from bot.ai.model_manager import AIModelManager; m = AIModelManager(); print(f'Providers: {m.get_available_providers()}')"
```

## 🔧 Troubleshooting

### Ошибка: "Model is currently loading"

Hugging Face Inference API загружает модель при первом запросе. Подождите 10-30 секунд и повторите.

### Ошибка: "Rate limit exceeded (429)"

AI Manager автоматически переключится на следующую модель. Если все модели исчерпали лимит, подождите несколько минут.

### Ошибка: "Invalid API token"

Проверьте, что `HF_TOKEN` или `HF_INFERENCE_TOKEN` установлен корректно:

```bash
echo $HF_TOKEN
```

Получить токен: https://huggingface.co/settings/tokens

## 📝 Использование в коде

```python
from bot.ai.model_manager import AIModelManager

# Инициализация
manager = AIModelManager()

# Проверка доступности
if manager.is_available():
    # Получить ответ (автоматическая ротация)
    response = await manager.get_response("Привет!")
    print(f"Provider: {response.provider}")
    print(f"Model: {response.model}")
    print(f"Text: {response.text}")
    
    # Для Mom Module
    sentence = await manager.generate_sentence(theme="животные")
    print(sentence)
```

## 🎯 Применение в модулях

- **Mom Module:** `generate_sentence()` для простых предложений
- **Universe Module:** `/olegovirus_name`, `/lore_event`
- **AI Module:** `/chat`, `/generate_prayer`, `/ask_canon`

---

**Статус:** Готово к использованию  
**Следующий шаг:** Реализация AI Commands (AI-02, AI-03, AI-04)
