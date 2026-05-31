"""Minimal Vercel webhook handler for Telegram bot."""

from __future__ import annotations

import hmac
import os
from flask import Flask, jsonify, request

app = Flask(__name__)

# Webhook secret
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "2f0cada15d8c40d3331d895340329c328494cba48aef25ee8c1461a7fc81d266")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")


@app.route("/")
def index():
    return jsonify({"service": "BankBot", "status": "ok", "platform": "vercel"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "platform": "vercel"})


@app.route("/reading_trainer.html")
def reading_trainer():
    """Serve reading trainer HTML."""
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тренажёр чтения</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1 { text-align: center; margin-bottom: 30px; color: #333; }
        .story-title { font-size: 24px; font-weight: bold; margin: 20px 0; text-align: center; }
        .story-image { font-size: 80px; text-align: center; margin: 20px 0; }
        .story-text { font-size: 20px; line-height: 1.8; text-align: justify; margin: 20px 0; }
        button { padding: 12px 24px; font-size: 16px; margin: 10px 5px; cursor: pointer; border: none; border-radius: 8px; font-weight: 600; }
        .btn-primary { background: #007AFF; color: white; }
        .btn-primary:hover { background: #0051D5; }
        .btn-secondary { background: #8E8E93; color: white; }
        .btn-secondary:hover { background: #636366; }
        .btn-print { background: #34C759; color: white; }
        .btn-print:hover { background: #248A3D; }
        input { width: 100%; padding: 12px; font-size: 16px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; }
        input:focus { outline: none; border-color: #007AFF; }
        .question { margin: 20px 0; }
        .question-text { font-size: 18px; font-weight: 600; margin-bottom: 10px; }
        .result { padding: 12px; margin: 10px 0; border-radius: 8px; font-weight: bold; }
        .correct { background: #D1F2DD; color: #248A3D; }
        .incorrect { background: #FFD7D9; color: #D70015; }
        #questions-screen { display: none; }
        @media print {
            body { background: white; padding: 0; }
            .container { box-shadow: none; padding: 20px; }
            button { display: none !important; }
            input { border: none; border-bottom: 2px solid #000; background: transparent; }
            .result { display: none !important; }
            h1 { font-size: 24px; margin-bottom: 20px; }
            .story-title { font-size: 20px; margin-bottom: 10px; }
            .story-image { font-size: 60px; margin: 10px 0; }
            .story-text { font-size: 16px; line-height: 1.6; }
            .question { page-break-inside: avoid; margin: 15px 0; }
            .question-text { font-size: 16px; }
            #questions-screen { display: block !important; }
            #reading-screen { display: block !important; }
            .print-separator { border-top: 2px dashed #000; margin: 30px 0; padding-top: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧸 Тренажёр чтения и понимания</h1>
        <div id="reading-screen">
            <div id="sentences"></div>
            <button class="btn-primary" onclick="goToQuestions()">Дальше →</button>
            <button class="btn-secondary" onclick="loadNewText()">Новый текст</button>
            <button class="btn-print" onclick="printWorksheet()">🖨️ Печать</button>
        </div>
        <div id="questions-screen">
            <div id="questions-container"></div>
            <button class="btn-primary" onclick="checkAnswers()">Проверить</button>
            <button class="btn-secondary" onclick="goBackToReading()">← Назад к чтению</button>
            <button class="btn-print" onclick="printWorksheet()">🖨️ Печать</button>
        </div>
    </div>
    <script>
        const fallbackSets = [
            {
                title: "🐱 Кот Мурзик",
                image: "🐱",
                text: "Жил-был кот Мурзик. Он любил спать на диване. Мама мыла раму. Солнце светило ярко. Дети играли в парке. Папа читал книгу. Бабушка пекла пирог.",
                questions: [
                    {question: "Как звали кота?", answer: "мурзик"},
                    {question: "Что делала мама?", answer: "мыла раму"},
                    {question: "Где играли дети?", answer: "в парке"}
                ]
            },
            {
                title: "🐕 Собака Шарик",
                image: "🐕",
                text: "Собака Шарик громко лаяла. Птица пела песню на дереве. Дождь шёл сильно. Цветы росли в саду. Машина ехала быстро. Река текла медленно.",
                questions: [
                    {question: "Как звали собаку?", answer: "шарик"},
                    {question: "Что делала птица?", answer: "пела песню"},
                    {question: "Где росли цветы?", answer: "в саду"}
                ]
            },
            {
                title: "🎨 В школе",
                image: "🏫",
                text: "Мальчик рисовал дом. Девочка пела песню. Учитель писал мелом на доске. Ученик читал текст. Повар готовил суп. Врач лечил людей.",
                questions: [
                    {question: "Что рисовал мальчик?", answer: "дом"},
                    {question: "Кто пел песню?", answer: "девочка"},
                    {question: "Что готовил повар?", answer: "суп"}
                ]
            }
        ];
        let currentData = null;
        function loadNewText() {
            // Show loading indicator
            document.getElementById('sentences').innerHTML = '<div style="text-align: center; padding: 40px;">⏳ Загрузка нового текста...</div>';
            
            // Try to fetch from API (use relative path for Vercel)
            fetch('/api/reading_generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({})
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('API request failed');
                }
                return response.json();
            })
            .then(data => {
                console.log('Generated story:', data);
                currentData = data;
                displayReading();
            })
            .catch(error => {
                console.error('Error loading text:', error);
                // Fallback to predefined sets
                currentData = fallbackSets[Math.floor(Math.random() * fallbackSets.length)];
                displayReading();
            });
        }
        function displayReading() {
            const html = `
                <div class="story-title">${currentData.title}</div>
                <div class="story-image">${currentData.image}</div>
                <div class="story-text">${currentData.text}</div>
            `;
            document.getElementById('sentences').innerHTML = html;
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }
        function goToQuestions() {
            document.getElementById('questions-container').innerHTML = currentData.questions.map((q, i) => 
                '<div class="question">' +
                '<div class="question-text">' + (i+1) + '. ' + q.question + '</div>' +
                '<input type="text" id="answer-' + i + '" placeholder="Введите ответ">' +
                '<div class="result" id="result-' + i + '" style="display:none;"></div>' +
                '</div>'
            ).join('');
            document.getElementById('reading-screen').style.display = 'none';
            document.getElementById('questions-screen').style.display = 'block';
        }
        function goBackToReading() {
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }
        function checkAnswers() {
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById('answer-' + i);
                const result = document.getElementById('result-' + i);
                const userAnswer = input.value.trim().toLowerCase();
                const correctAnswer = q.answer.toLowerCase();
                if (userAnswer === correctAnswer) {
                    result.textContent = '✓ Правильно!';
                    result.className = 'result correct';
                } else {
                    result.textContent = '✗ Правильный ответ: ' + q.answer;
                    result.className = 'result incorrect';
                }
                result.style.display = 'block';
            });
        }
        function printWorksheet() {
            const readingScreen = document.getElementById('reading-screen');
            const questionsScreen = document.getElementById('questions-screen');
            const wasReadingVisible = readingScreen.style.display !== 'none';
            const wasQuestionsVisible = questionsScreen.style.display !== 'none';
            readingScreen.style.display = 'block';
            questionsScreen.style.display = 'block';
            if (!document.getElementById('print-separator')) {
                const separator = document.createElement('div');
                separator.id = 'print-separator';
                separator.className = 'print-separator';
                separator.innerHTML = '<h2>Вопросы:</h2>';
                questionsScreen.insertBefore(separator, questionsScreen.firstChild);
            }
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById('answer-' + i);
                const result = document.getElementById('result-' + i);
                if (input) input.value = '';
                if (result) result.style.display = 'none';
            });
            window.print();
            setTimeout(() => {
                readingScreen.style.display = wasReadingVisible ? 'block' : 'none';
                questionsScreen.style.display = wasQuestionsVisible ? 'block' : 'none';
            }, 100);
        }
        loadNewText();
    </script>
</body>
</html>"""
    return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route("/telegram/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    """Receive Telegram webhook and forward to processing."""
    
    # Verify secret
    if not hmac.compare_digest(secret, WEBHOOK_SECRET):
        return jsonify({"error": "invalid_secret"}), 404
    
    # Get update
    update = request.get_json()
    if not update:
        return jsonify({"ok": True})
    
    # Process /reading_trainer command
    try:
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        
        if text == "/reading_trainer" and chat_id:
            # Send response with inline button
            import requests
            
            response_text = (
                "🧸 Тренажёр чтения и понимания\n\n"
                "Приложение для тренировки чтения простых текстов.\n\n"
                "📖 Что внутри:\n"
                "• 6 простых предложений (3-4 слова)\n"
                "• 2-3 вопроса по содержанию\n"
                "• Проверка ответов\n"
                "• Возможность вернуться к чтению\n"
                "• Регулировка размера шрифта\n\n"
                "Нажмите кнопку ниже, чтобы открыть в браузере:"
            )
            
            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "🧸 Открыть тренажёр",
                        "url": "https://bank-bot-ruby.vercel.app/reading_trainer.html"
                    }
                ]]
            }
            
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": response_text,
                    "reply_markup": keyboard
                },
                timeout=5
            )
    except Exception as e:
        print(f"Error processing update: {e}")
    
    return jsonify({"ok": True})


@app.route("/api/debug_hf", methods=["GET"])
def debug_hf():
    """Debug endpoint to check HF API configuration and connectivity."""
    import httpx
    
    debug_info = {
        "timestamp": "2026-05-31T17:52:00Z",
        "hf_token_exists": bool(os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")),
        "hf_token_length": len(os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN") or ""),
        "models_to_try": [
            "mistralai/Mistral-7B-Instruct-v0.2",
            "google/flan-t5-base",
            "facebook/bart-large-cnn"
        ],
        "test_results": []
    }
    
    hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")
    
    if not hf_token:
        debug_info["error"] = "No HF token found in environment"
        return jsonify(debug_info)
    
    # Test each model with a simple request
    for model in debug_info["models_to_try"]:
        try:
            response = httpx.post(
                f"https://api-inference.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {hf_token}"},
                json={
                    "inputs": "Test",
                    "parameters": {"max_new_tokens": 10},
                    "options": {"wait_for_model": True}
                },
                timeout=10.0
            )
            
            debug_info["test_results"].append({
                "model": model,
                "status_code": response.status_code,
                "response_preview": response.text[:200] if response.status_code != 200 else "OK",
                "success": response.status_code == 200
            })
        except Exception as e:
            debug_info["test_results"].append({
                "model": model,
                "error": str(e),
                "success": False
            })
    
    return jsonify(debug_info)


@app.route("/api/reading_generate", methods=["POST", "GET"])
def reading_generate():
    """Generate reading text and questions using HF API."""
    try:
        import requests  # Use requests instead of httpx
        import json
        import random
        
        hf_token = os.getenv("HF_INFERENCE_TOKEN") or os.getenv("HF_TOKEN")
        
        print(f"HF Token available: {bool(hf_token)}")
        
        if not hf_token:
            print("No HF token, using fallback")
            # Return fallback set if no HF token
            fallback_sets = get_fallback_sets()
            return jsonify(random.choice(fallback_sets))
        
        print("Calling HF API with requests library...")
        
        # Try multiple models in order of preference
        models = [
            "mistralai/Mistral-7B-Instruct-v0.2",
            "google/flan-t5-base",
            "facebook/bart-large-cnn"
        ]
        
        # Simplified prompt for better results
        prompt = """Напиши короткую историю для ребёнка 7 лет.

История должна быть про животное или семью.
Используй простые слова.
6 коротких предложений.

Потом напиши 3 простых вопроса по истории.

Пример:
Жил кот Барсик. Он любил молоко. Мама кормила кота. Барсик мурлыкал. Он спал на диване. Кот был добрый.

Вопросы:
1. Как звали кота?
2. Что любил кот?
3. Где спал кот?

Теперь напиши новую историю:"""

        generated_text = None
        last_error = None
        
        # Try each model until one works
        for model in models:
            try:
                print(f"Trying model: {model}")
                
                # Call HF API using requests library
                response = requests.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={"Authorization": f"Bearer {hf_token}"},
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 300,
                            "temperature": 0.8,
                            "top_p": 0.9,
                            "return_full_text": False
                        },
                        "options": {
                            "wait_for_model": True
                        }
                    },
                    timeout=30.0
                )
                
                print(f"Model {model} status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    generated_text = result[0]["generated_text"] if isinstance(result, list) else result.get("generated_text", "")
                    print(f"Success with {model}! Generated {len(generated_text)} chars")
                    break
                else:
                    last_error = f"{model}: {response.status_code}"
                    print(f"Model {model} failed: {response.text[:200]}")
                    
            except Exception as e:
                last_error = f"{model}: {str(e)}"
                print(f"Model {model} error: {e}")
                continue
        
        if not generated_text:
            print(f"All models failed. Last error: {last_error}")
            raise Exception(f"All HF models failed: {last_error}")
        
        print(f"Generated text length: {len(generated_text)}")
        
        # Parse the generated text
        lines = [line.strip() for line in generated_text.split('\n') if line.strip()]
        
        # Extract story text (first 6-7 lines before "Вопросы")
        story_lines = []
        questions_section = []
        in_questions = False
        
        for line in lines:
            if 'вопрос' in line.lower() or line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                in_questions = True
            
            if in_questions:
                questions_section.append(line)
            else:
                if len(story_lines) < 7 and len(line) > 10:
                    story_lines.append(line)
        
        # Build story text
        story_text = ' '.join(story_lines[:7]) if story_lines else "Жил-был кот. Он любил играть. Кот был добрый."
        
        # Extract questions and answers
        questions = []
        for line in questions_section[:3]:
            # Remove numbering
            line = line.lstrip('123.').strip()
            if '?' in line:
                questions.append({"question": line, "answer": "ответ"})
        
        # Ensure we have 3 questions
        while len(questions) < 3:
            questions.append({"question": "Что было в истории?", "answer": "ответ"})
        
        # Pick random emoji
        emojis = ["🐱", "🐶", "🐰", "🐻", "🦊", "🐸", "🏫", "🏠", "🌳", "🐭", "🐷", "🐮"]
        emoji = random.choice(emojis)
        
        story_data = {
            "title": f"{emoji} Новая история",
            "image": emoji,
            "text": story_text,
            "questions": questions[:3]
        }
        
        print(f"Returning story: {story_data['title']}")
        return jsonify(story_data)
        
    except Exception as e:
        print(f"Error generating reading text: {e}")
        import traceback
        traceback.print_exc()
        
        # Return fallback set on error
        import random
        fallback_sets = get_fallback_sets()
        return jsonify(random.choice(fallback_sets))


def get_fallback_sets():
    """Return predefined fallback story sets."""
    return [
        {
            "title": "🐱 Кот Мурзик",
            "image": "🐱",
            "text": "Жил-был кот Мурзик. Он любил спать на диване. Мама мыла раму. Солнце светило ярко. Дети играли в парке. Папа читал книгу. Бабушка пекла пирог.",
            "questions": [
                {"question": "Как звали кота?", "answer": "мурзик"},
                {"question": "Что делала мама?", "answer": "мыла раму"},
                {"question": "Где играли дети?", "answer": "в парке"}
            ]
        },
        {
            "title": "🐕 Собака Шарик",
            "image": "🐕",
            "text": "Собака Шарик громко лаяла. Птица пела песню на дереве. Дождь шёл сильно. Цветы росли в саду. Машина ехала быстро. Река текла медленно.",
            "questions": [
                {"question": "Как звали собаку?", "answer": "шарик"},
                {"question": "Что делала птица?", "answer": "пела песню"},
                {"question": "Где росли цветы?", "answer": "в саду"}
            ]
        },
        {
            "title": "🎨 В школе",
            "image": "🏫",
            "text": "Мальчик рисовал дом. Девочка пела песню. Учитель писал мелом на доске. Ученик читал текст. Повар готовил суп. Врач лечил людей.",
            "questions": [
                {"question": "Что рисовал мальчик?", "answer": "дом"},
                {"question": "Кто пел песню?", "answer": "девочка"},
                {"question": "Что готовил повар?", "answer": "суп"}
            ]
        }
    ]


# Vercel handler
handler = app
application = app
