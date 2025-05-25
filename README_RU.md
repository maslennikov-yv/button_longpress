# ESP-IDF Button Long Press Component

[![CI Status](https://github.com/maslennikov-yv/button_longpress/workflows/ESP-IDF%20Button%20Component%20CI/badge.svg)](https://github.com/maslennikov-yv/button_longpress/actions)
[![Test Coverage](https://img.shields.io/badge/coverage-80%25-green.svg)](https://github.com/maslennikov-yv/button_longpress/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v4.4%2B-blue.svg)](https://github.com/espressif/esp-idf)

Высокопроизводительный и надежный компонент для ESP-IDF, обеспечивающий расширенную обработку кнопок с поддержкой длительного нажатия, двойного клика и устранения дребезга контактов.

## ✨ Основные возможности

- 🔘 **Обнаружение длительного нажатия** - настраиваемое время удержания
- 🖱️ **Двойной клик** - детекция быстрых последовательных нажатий
- ⚡ **Устранение дребезга** - аппаратная фильтрация помех
- 🔄 **Асинхронные события** - callback-функции для всех типов событий
- 🛡️ **Потокобезопасность** - защита мьютексами для многозадачности
- 📊 **Конечный автомат** - надежная логика обработки состояний
- 🎛️ **Гибкая конфигурация** - настройка всех временных параметров
- 🔌 **Поддержка активного уровня** - работа с active-high и active-low кнопками
- 💾 **Эффективное использование памяти** - минимальное потребление ресурсов
- 🧪 **Полное тестирование** - 80%+ покрытие тестами

## 🚀 Быстрый старт

### Установка

1. Клонируйте репозиторий в папку `components` вашего ESP-IDF проекта:
```bash
cd your_project/components
git clone https://github.com/maslennikov-yv/button_longpress.git
```

2. Или добавьте как git submodule:
```bash
git submodule add https://github.com/maslennikov-yv/button_longpress.git components/button_longpress
```

### Базовое использование

```c
#include "button_longpress.h"

// Обработчик событий кнопки
static void button_event_handler(button_event_t event)
{
    switch (event) {
        case BUTTON_EVENT_PRESSED:
            printf("Кнопка нажата\n");
            break;
        case BUTTON_EVENT_RELEASED:
            printf("Кнопка отпущена\n");
            break;
        case BUTTON_EVENT_LONG_PRESS:
            printf("Длительное нажатие!\n");
            break;
        case BUTTON_EVENT_DOUBLE_CLICK:
            printf("Двойной клик!\n");
            break;
    }
}

void app_main(void)
{
    // Конфигурация кнопки
    button_config_t btn_config = {
        .gpio_num = GPIO_NUM_0,           // GPIO пин
        .active_level = 0,                // Активный низкий уровень
        .debounce_time_ms = 20,           // 20мс устранение дребезга
        .long_press_time_ms = 2000,       // 2 секунды для длительного нажатия
        .double_click_time_ms = 300,      // 300мс для двойного клика
        .callback = button_event_handler  // Функция обратного вызова
    };
    
    // Создание экземпляра кнопки
    button_handle_t btn = button_create(&btn_config);
    if (btn == NULL) {
        printf("Ошибка создания кнопки\n");
        return;
    }
    
    // Ваш код приложения здесь...
    
    // Очистка ресурсов (опционально)
    button_delete(btn);
}
