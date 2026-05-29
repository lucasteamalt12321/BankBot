"""Reading trainer endpoint for Vercel."""
from flask import Flask, jsonify, Response

app = Flask(__name__)

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Тренажёр чтения</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; }
        h1 { text-align: center; margin-bottom: 30px; }
        .sentence { font-size: 20px; margin: 15px 0; font-weight: bold; }
        button { padding: 12px 24px; font-size: 16px; margin: 10px 5px; cursor: pointer; border: none; border-radius: 8px; }
        .btn-primary { background: #007AFF; color: white; }
        .btn-secondary { background: #8E8E93; color: white; }
        input { width: 100%; padding: 10px; font-size: 16px; margin: 10px 0; border: 2px solid #ddd; border-radius: 8px; }
        .question { margin: 20px 0; }
        .result { padding: 10px; margin: 10px 0; border-radius: 8px; font-weight: bold; }
        .correct { background: #D1F2DD; color: #248A3D; }
        .incorrect { background: #FFD7D9; color: #D70015; }
        #questions-screen { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧸 Тренажёр чтения и понимания</h1>
        
        <div id="reading-screen">
            <div id="sentences"></div>
            <button class="btn-primary" onclick="goToQuestions()">Дальше →</button>
            <button class="btn-secondary" onclick="loadNewText()">Новый текст</button>
        </div>

        <div id="questions-screen">
            <div id="questions-container"></div>
            <button class="btn-primary" onclick="checkAnswers()">Проверить</button>
            <button class="btn-secondary" onclick="goBackToReading()">← Назад</button>
        </div>
    </div>

    <script>
        let currentData = null;

        async function loadNewText() {
            try {
                const response = await fetch('/api/reading_generate', { method: 'POST' });
                currentData = await response.json();
                displayReading();
            } catch (error) {
                alert('Ошибка загрузки');
            }
        }

        function displayReading() {
            document.getElementById('sentences').innerHTML = currentData.sentences
                .map(s => '<div class="sentence">' + s + '</div>').join('');
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }

        function goToQuestions() {
            document.getElementById('questions-container').innerHTML = currentData.questions.map((q, i) => 
                '<div class="question"><div>' + (i+1) + '. ' + q.question + '</div>' +
                '<input type="text" id="answer-' + i + '"><div class="result" id="result-' + i + '" style="display:none;"></div></div>'
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

        loadNewText();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return Response(HTML_CONTENT, mimetype='text/html')

handler = app
