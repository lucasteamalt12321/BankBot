// Состояние приложения
let currentData = null; // {sentences: [], questions: [{question, answer}]}
let currentQuestionIndex = 0;
let fontSize = 42; // Начальный размер шрифта (px)

// Константы
const MIN_FONT_SIZE = 24;
const MAX_FONT_SIZE = 72;
const FONT_SIZE_STEP = 6;
const BACKEND_URL = '/reading_generate'; // Относительный путь

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    loadFontSize();
    loadNewText();
});

// ===== Управление размером шрифта =====

function loadFontSize() {
    const saved = localStorage.getItem('reading_trainer_font_size');
    if (saved) {
        fontSize = parseInt(saved, 10);
    }
    applyFontSize();
}

function saveFontSize() {
    localStorage.setItem('reading_trainer_font_size', fontSize);
}

function applyFontSize() {
    const sentences = document.querySelectorAll('.sentence');
    sentences.forEach(s => s.style.fontSize = fontSize + 'px');
    
    const questionText = document.getElementById('question-text');
    if (questionText) {
        questionText.style.fontSize = fontSize + 'px';
    }
}

function increaseFontSize() {
    if (fontSize < MAX_FONT_SIZE) {
        fontSize += FONT_SIZE_STEP;
        saveFontSize();
        applyFontSize();
    }
}

function decreaseFontSize() {
    if (fontSize > MIN_FONT_SIZE) {
        fontSize -= FONT_SIZE_STEP;
        saveFontSize();
        applyFontSize();
    }
}

// ===== Загрузка текста =====

async function loadNewText() {
    showLoading();
    currentQuestionIndex = 0;
    
    try {
        const response = await fetch(BACKEND_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Валидация данных
        if (!data.sentences || !Array.isArray(data.sentences) || data.sentences.length === 0) {
            throw new Error('Некорректный формат данных: sentences');
        }
        
        if (!data.questions || !Array.isArray(data.questions) || data.questions.length === 0) {
            throw new Error('Некорректный формат данных: questions');
        }
        
        currentData = data;
        showReadingScreen();
        
    } catch (error) {
        console.error('Error loading text:', error);
        showError('Не удалось загрузить текст. Попробуйте позже.');
    }
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('reading-screen').style.display = 'none';
    document.getElementById('questions-screen').style.display = 'none';
}

function showError(message) {
    const loading = document.getElementById('loading');
    loading.innerHTML = `
        <div class="error">
            <p>${message}</p>
            <button class="btn-primary" onclick="loadNewText()" style="margin-top: 16px;">
                Попробовать снова
            </button>
        </div>
    `;
}

// ===== Экран чтения =====

function showReadingScreen() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('reading-screen').style.display = 'block';
    document.getElementById('questions-screen').style.display = 'none';
    
    renderSentences();
}

function renderSentences() {
    const container = document.getElementById('sentences');
    container.innerHTML = '';
    
    currentData.sentences.forEach((sentence, index) => {
        const div = document.createElement('div');
        div.className = 'sentence';
        div.textContent = sentence;
        div.style.fontSize = fontSize + 'px';
        container.appendChild(div);
    });
}

// ===== Экран вопросов =====

function goToQuestions() {
    document.getElementById('reading-screen').style.display = 'none';
    document.getElementById('questions-screen').style.display = 'block';
    
    showQuestion();
}

function goToReading() {
    document.getElementById('questions-screen').style.display = 'none';
    document.getElementById('reading-screen').style.display = 'block';
}

function showQuestion() {
    if (currentQuestionIndex >= currentData.questions.length) {
        // Все вопросы отвечены
        showCongratulations();
        return;
    }
    
    const question = currentData.questions[currentQuestionIndex];
    const questionText = document.getElementById('question-text');
    const answerInput = document.getElementById('answer-input');
    const feedback = document.getElementById('feedback');
    
    questionText.textContent = `${currentQuestionIndex + 1}. ${question.question}`;
    questionText.style.fontSize = fontSize + 'px';
    
    answerInput.value = '';
    answerInput.className = '';
    answerInput.disabled = false;
    answerInput.focus();
    
    feedback.textContent = '';
    feedback.className = '';
}

function checkAnswer() {
    const answerInput = document.getElementById('answer-input');
    const feedback = document.getElementById('feedback');
    const userAnswer = answerInput.value.trim().toLowerCase();
    
    if (!userAnswer) {
        feedback.textContent = 'Введи ответ!';
        feedback.className = 'incorrect';
        return;
    }
    
    const correctAnswer = currentData.questions[currentQuestionIndex].answer.toLowerCase();
    
    if (userAnswer === correctAnswer) {
        // Правильный ответ
        answerInput.className = 'correct';
        feedback.textContent = '✓ Верно!';
        feedback.className = 'correct';
        answerInput.disabled = true;
        
        // Переход к следующему вопросу через 1 секунду
        setTimeout(() => {
            currentQuestionIndex++;
            showQuestion();
        }, 1000);
        
    } else {
        // Неправильный ответ
        answerInput.className = 'incorrect';
        feedback.textContent = '✗ Неверно, попробуй ещё';
        feedback.className = 'incorrect';
    }
}

// Enter для отправки ответа
document.addEventListener('DOMContentLoaded', () => {
    const answerInput = document.getElementById('answer-input');
    if (answerInput) {
        answerInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                checkAnswer();
            }
        });
    }
});

function showCongratulations() {
    const container = document.getElementById('question-container');
    container.innerHTML = `
        <div style="text-align: center; padding: 40px 0;">
            <h2 style="font-size: 32px; color: #4CAF50; margin-bottom: 24px;">
                🎉 Молодец! Все ответы правильные!
            </h2>
            <button class="btn-primary" onclick="loadNewText()" style="font-size: 20px; padding: 20px 40px;">
                Новый текст
            </button>
        </div>
    `;
}

// ===== Печать =====

function printContent() {
    // Создаём временный контейнер для печати
    const printContainer = document.createElement('div');
    printContainer.className = 'print-only';
    printContainer.style.display = 'none';
    
    // Заголовок: Прочитай предложения
    const readingTitle = document.createElement('h2');
    readingTitle.textContent = 'Прочитай предложения';
    readingTitle.style.marginBottom = '20px';
    printContainer.appendChild(readingTitle);
    
    // Предложения
    currentData.sentences.forEach(sentence => {
        const p = document.createElement('p');
        p.textContent = sentence;
        p.style.fontSize = '16pt';
        p.style.marginBottom = '12px';
        p.style.fontWeight = 'bold';
        printContainer.appendChild(p);
    });
    
    // Разделитель
    const separator = document.createElement('div');
    separator.style.height = '30px';
    printContainer.appendChild(separator);
    
    // Заголовок: Ответь на вопросы
    const questionsTitle = document.createElement('h2');
    questionsTitle.textContent = 'Ответь на вопросы';
    questionsTitle.style.marginBottom = '20px';
    printContainer.appendChild(questionsTitle);
    
    // Вопросы с пустыми строками
    currentData.questions.forEach((q, index) => {
        const questionDiv = document.createElement('div');
        questionDiv.style.marginBottom = '20px';
        
        const questionText = document.createElement('p');
        questionText.textContent = `${index + 1}. ${q.question}`;
        questionText.style.fontSize = '14pt';
        questionText.style.marginBottom = '8px';
        questionDiv.appendChild(questionText);
        
        const answerLine = document.createElement('div');
        answerLine.className = 'print-answer-line';
        answerLine.style.borderBottom = '1px solid #000';
        answerLine.style.minHeight = '30px';
        answerLine.style.margin = '10px 0';
        questionDiv.appendChild(answerLine);
        
        printContainer.appendChild(questionDiv);
    });
    
    // Добавляем в DOM
    document.body.appendChild(printContainer);
    
    // Печатаем
    window.print();
    
    // Удаляем временный контейнер
    document.body.removeChild(printContainer);
}
