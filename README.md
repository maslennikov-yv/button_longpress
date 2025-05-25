# 🔘 ESP-IDF Button Long Press Component

[![CI Status](https://github.com/your-username/button-longpress/workflows/CI/badge.svg)](https://github.com/your-username/button-longpress/actions)
[![Coverage](https://img.shields.io/badge/coverage-80%2B-brightgreen)](https://github.com/your-username/button-longpress/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ESP-IDF](https://img.shields.io/badge/ESP--IDF-v4.4%2B-blue)](https://github.com/espressif/esp-idf)

A robust and feature-rich button handling component for ESP-IDF that provides advanced button event detection including long press, double click, and debouncing capabilities.

## ✨ Features

- 🔘 **Multiple Event Types**: Press, release, long press, double click detection
- ⚡ **Debouncing**: Hardware debouncing with configurable timing
- 🔄 **State Machine**: Robust finite state machine for reliable operation
- 🧵 **Thread Safe**: Safe for use in multi-threaded applications
- 📊 **Low Overhead**: Minimal CPU and memory usage
- 🎯 **Configurable**: Flexible timing and behavior configuration
- 🧪 **Well Tested**: Comprehensive test suite with 80%+ coverage
- 📚 **Easy to Use**: Simple API with callback-based event handling

## 🚀 Quick Start

### Installation

Add this component to your ESP-IDF project:

```bash
cd components
git clone https://github.com/your-username/button-longpress.git
```

Or add as a submodule:

```bash
git submodule add https://github.com/your-username/button-longpress.git components/button_longpress
```

### Basic Usage

```c
#include "button_longpress.h"

// Button event callback
static void button_event_handler(button_event_t event)
{
    switch (event) {
        case BUTTON_EVENT_PRESSED:
            printf("Button pressed\n");
            break;
        case BUTTON_EVENT_RELEASED:
            printf("Button released\n");
            break;
        case BUTTON_EVENT_LONG_PRESS:
            printf("Long press detected!\n");
            break;
        case BUTTON_EVENT_DOUBLE_CLICK:
            printf("Double click detected!\n");
            break;
    }
}

void app_main(void)
{
    // Configure button
    button_config_t btn_config = {
        .gpio_num = GPIO_NUM_0,           // GPIO pin
        .active_level = 0,                // Active low
        .debounce_time_ms = 20,           // 20ms debounce
        .long_press_time_ms = 2000,       // 2 seconds for long press
        .double_click_time_ms = 300,      // 300ms for double click
        .callback = button_event_handler  // Event callback
    };
    
    // Create button instance
    button_handle_t btn = button_create(&btn_config);
    if (btn == NULL) {
        printf("Failed to create button\n");
        return;
    }
    
    // Your application code here...
    
    // Clean up (optional)
    button_delete(btn);
}
