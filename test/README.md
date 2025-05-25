# ESP-IDF Button Component Test Suite

Этот набор тестов предназначен для тестирования компонента кнопки ESP-IDF с поддержкой длительного нажатия, двойного клика и обычного клика.

## Структура файлов

\`\`\`
test/
├── conftest.py              # Конфигурация pytest и mock объекты
├── button_longpress.py      # Mock реализация компонента кнопки
├── test_button_longpress.py # Основные тесты функциональности
├── test_button_click.py     # Тесты функциональности клика
├── run_tests.py            # Python скрипт для запуска тестов
├── run-tests.sh            # Shell скрипт для запуска тестов
├── pytest.ini             # Конфигурация pytest
└── README.md               # Этот файл
\`\`\`

## Как запустить тесты

### Вариант 1: Python скрипт (рекомендуется)
\`\`\`bash
cd test
python3 run_tests.py
\`\`\`

### Вариант 2: Shell скрипт
\`\`\`bash
cd test
chmod +x run-tests.sh
./run-tests.sh
\`\`\`

### Вариант 3: Прямой запуск pytest
\`\`\`bash
cd test
python3 -m pytest test_button_longpress.py -v
python3 -m pytest test_button_click.py -v
\`\`\`

### Вариант 4: Запуск всех тестов
\`\`\`bash
cd test
python3 -m pytest -v
\`\`\`

## Что тестируется

### Основная функциональность (`test_button_longpress.py`)
- ✅ Создание и удаление кнопки
- ✅ Валидация параметров
- ✅ Обнаружение нажатия (active high/low)
- ✅ Длительное нажатие
- ✅ Двойной клик
- ✅ Короткое нажатие
- ✅ Подавление дребезга
- ✅ Множественные кнопки
- ✅ Обработка ошибок

### Функциональность клика (`test_button_click.py`)
- ✅ Одиночный клик
- ✅ Предотвращение клика при двойном клике
- ✅ Предотвращение клика при длительном нажатии
- ✅ Точность таймингов

## Mock объекты

Тесты используют mock объекты для симуляции ESP-IDF и FreeRTOS:

- **MockESP**: Симулирует ESP-IDF функции и константы
- **MockFreeRTOS**: Симулирует таймеры FreeRTOS
- **MockGPIO**: Симулирует GPIO операции

## Требования

- Python 3.6+
- pytest
- ctypes (встроенный в Python)

## Установка зависимостей

\`\`\`bash
pip install pytest
\`\`\`

## Ожидаемый результат

При успешном выполнении вы увидите:

\`\`\`
=== ESP-IDF Button Component Test Suite ===

1. Verifying imports...
   ✓ All imports successful

2. Quick functionality test...
   ✓ Button created: 1
   ✓ State: 0, Pressed: False
   ✓ Button deleted successfully

3. Running pytest...
   ✓ Main test suite PASSED
   ✓ Click test suite PASSED

=== ALL TESTS PASSED ===
✓ Test suite is working correctly!
