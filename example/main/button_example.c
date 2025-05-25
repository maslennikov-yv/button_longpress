#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "button_longpress.h"

static const char *TAG = "BTN_EXAMPLE";

// Button event callback
static void button_event_handler(button_event_t event)
{
    switch (event) {
        case BUTTON_EVENT_PRESSED:
            ESP_LOGI(TAG, "Button pressed");
            break;
        case BUTTON_EVENT_RELEASED:
            ESP_LOGI(TAG, "Button released");
            break;
        case BUTTON_EVENT_CLICK:
            ESP_LOGI(TAG, "Button single click detected!");
            break;
        case BUTTON_EVENT_LONG_PRESS:
            ESP_LOGI(TAG, "Button long press detected!");
            break;
        case BUTTON_EVENT_DOUBLE_CLICK:
            ESP_LOGI(TAG, "Button double click detected!");
            break;
        default:
            break;
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Button long press and double click example");

    // Configure button
    button_config_t btn_config = {
        .gpio_num = GPIO_NUM_0,           // Using GPIO0 (usually the BOOT button on many ESP32 dev boards)
        .active_level = 0,                // Active low (button connects GPIO to GND when pressed)
        .debounce_time_ms = 20,           // 20ms debounce time
        .long_press_time_ms = 2000,       // 2 seconds for long press
        .double_click_time_ms = 300,      // 300ms for double click detection
        .callback = button_event_handler  // Set callback function
    };

    // Create button
    button_handle_t btn_handle = button_create(&btn_config);
    if (btn_handle == NULL) {
        ESP_LOGE(TAG, "Failed to create button");
        return;
    }

    ESP_LOGI(TAG, "Button initialized. Try different interactions:");
    ESP_LOGI(TAG, "1. Press and release for a single click");
    ESP_LOGI(TAG, "2. Press twice quickly for a double click");
    ESP_LOGI(TAG, "3. Press and hold for a long press");
    
    // Main loop
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(100));
        
        // You can also check button state programmatically
        button_state_t state = button_get_state(btn_handle);
        if (state == BUTTON_STATE_SHORT_PRESS) {
            // Additional actions for short press if needed
            ESP_LOGI(TAG, "Short press detected programmatically");
        }
    }
    
    // This part won't be reached in this example
    button_delete(btn_handle);
}
