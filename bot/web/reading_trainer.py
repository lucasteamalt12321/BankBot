"""Reading trainer web app HTML and JS content."""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Тренажёр чтения и понимания</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: #f5f5f5;
            padding: 16px;
            min-height: 100vh;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        h1 {
            font-size: 28px;
            margin-bottom: 24px;
            color: #333;
            text-align: center;
        }

        #reading-screen {
            display: block;
        }

        #sentences {
            margin: 32px 0;
            line-height: 1.8;
        }

        .sentence {
            font-weight: bold;
            color: #000;
            margin-bottom: 16px;
            font-size: 20px;
        }

        #questions-screen {
            display: none;
        }

        .question {
            margin-bottom: 24px;
        }

        .question-text {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #333;
        }

        input[type="text"] {
            width: 100%;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            transition: border-color 0.3s;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: #007AFF;
        }

        .controls {
            display: flex;
            gap: 12px;
            margin-top: 24px;
            flex-wrap: wrap;
        }

        button {
            flex: 1;
            min-width: 120px;
            padding: 14px 24px;
            font-size: 16px;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }

        .btn-primary {
            background: #007AFF;
            color: white;
        }

        .btn-primary:hover {
            background: #0051D5;
        }

        .btn-secondary {
            background: #8E8E93;
            color: white;
        }

        .btn-secondary:hover {
            background: #636366;
        }

        .btn-success {
            background: #34C759;
            color: white;
        }

        .btn-success:hover {
            background: #248A3D;
        }

        .font-controls {
            display: flex;
            gap: 8px;
            justify-content: center;
            margin-bottom: 16px;
        }

        .font-btn {
            min-width: 50px;
            padding: 8px 16px;
            background: #E5E5EA;
            color: #000;
        }

        .font-btn:hover {
            background: #D1D1D6;
        }

        .result {
            margin-top: 12px;
            padding: 12px;
            border-radius: 8px;
            font-weight: 600;
        }

        .result.correct {
            background: #D1F2DD;
            color: #248A3D;
        }

        .result.incorrect {
            background: #FFD7D9;
            color: #D70015;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #8E8E93;
        }

        @media print {
            body {
                background: white;
                padding: 0;
            }
            .container {
                box-shadow: none;
                padding: 20px;
            }
            button, .controls, .font-controls {
                display: none !important;
            }
            #reading-screen, #questions-screen {
                display: block !important;
            }
            h1 {
                page-break-after: avoid;
            }
            .question {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧸 Тренажёр чтения и понимания</h1>
        
        <div class="font-controls">
            <button class="font-btn" onclick="changeFontSize(-2)">A-</button>
            <button class="font-btn" onclick="changeFontSize(2)">A+</button>
        </div>

        <div id="reading-screen">
            <div id="sentences"></div>
            <div class="controls">
                <button class="btn-primary" onclick="goToQuestions()">Дальше →</button>
                <button class="btn-secondary" onclick="loadNewText()">Новый текст</button>
            </div>
        </div>

        <div id="questions-screen">
            <div id="questions-container"></div>
            <div class="controls">
                <button class="btn-success" onclick="checkAnswers()">Проверить</button>
                <button class="btn-secondary" onclick="goBackToReading()">← Назад к чтению</button>
                <button class="btn-secondary" onclick="printAll()">🖨️ Печать</button>
            </div>
        </div>

        <div id="loading" class="loading" style="display:none;">
            Загрузка...
        </div>
    </div>

    <script>
        let currentData = null;
        let fontSize = parseInt(localStorage.getItem('fontSize') || '20');

        function applyFontSize() {
            document.querySelectorAll('.sentence').forEach(el => {
                el.style.fontSize = fontSize + 'px';
            });
        }

        function changeFontSize(delta) {
            fontSize = Math.max(14, Math.min(32, fontSize + delta));
            localStorage.setItem('fontSize', fontSize);
            applyFontSize();
        }

        async function loadNewText() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('reading-screen').style.display = 'none';
            document.getElementById('questions-screen').style.display = 'none';

            try {
                const response = await fetch('/reading_generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                
                if (!response.ok) throw new Error('Failed to load');
                
                currentData = await response.json();
                displayReading();
            } catch (error) {
                alert('Ошибка загрузки. Попробуйте ещё раз.');
                console.error(error);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }

        function displayReading() {
            const container = document.getElementById('sentences');
            container.innerHTML = currentData.sentences
                .map(s => `<div class="sentence">${s}</div>`)
                .join('');
            
            applyFontSize();
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }

        function goToQuestions() {
            const container = document.getElementById('questions-container');
            container.innerHTML = currentData.questions.map((q, i) => `
                <div class="question">
                    <div class="question-text">${i + 1}. ${q.question}</div>
                    <input type="text" id="answer-${i}" placeholder="Введите ответ">
                    <div class="result" id="result-${i}" style="display:none;"></div>
                </div>
            `).join('');

            document.getElementById('reading-screen').style.display = 'none';
            document.getElementById('questions-screen').style.display = 'block';
        }

        function goBackToReading() {
            document.getElementById('reading-screen').style.display = 'block';
            document.getElementById('questions-screen').style.display = 'none';
        }

        function checkAnswers() {
            currentData.questions.forEach((q, i) => {
                const input = document.getElementById(`answer-${i}`);
                const result = document.getElementById(`result-${i}`);
                const userAnswer = input.value.trim().toLowerCase();
                const correctAnswer = q.answer.toLowerCase();

                if (userAnswer === correctAnswer) {
                    result.textContent = '✓ Правильно!';
                    result.className = 'result correct';
                } else {
                    result.textContent = `✗ Правильный ответ: ${q.answer}`;
                    result.className = 'result incorrect';
                }
                result.style.display = 'block';
            });
        }

        function printAll() {
            window.print();
        }

        loadNewText();
    </script>
</body>
</html>
"""
