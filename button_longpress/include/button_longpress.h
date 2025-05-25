#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#include "driver/gpio.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Button state enumeration
 */
typedef enum {
    BUTTON_STATE_IDLE,          /*!< Button is not pressed */
    BUTTON_STATE_PRESSED,       /*!< Button is pressed but not long enough for long press */
    BUTTON_STATE_LONG_PRESS,    /*!< Button is in long press state */
    BUTTON_STATE_SHORT_PRESS,   /*!< Button was pressed and released (short press) */
    BUTTON_STATE_DOUBLE_CLICK   /*!< Button has been double-clicked */
} button_state_t;

/**
 * @brief Button event types
 */
typedef enum {
    BUTTON_EVENT_PRESSED,       /*!< Button pressed event */
    BUTTON_EVENT_RELEASED,      /*!< Button released event */
    BUTTON_EVENT_LONG_PRESS,    /*!< Button long press detected */
    BUTTON_EVENT_DOUBLE_CLICK   /*!< Button double click detected */
} button_event_t;

/**
 * @brief Button configuration structure
 */
typedef struct {
    gpio_num_t gpio_num;                /*!< GPIO number for button */
    bool active_level;                  /*!< Button active level (true: active high, false: active low) */
    uint32_t debounce_time_ms;          /*!< Debounce time in milliseconds */
    uint32_t long_press_time_ms;        /*!< Time in milliseconds to detect a long press */
    uint32_t double_click_time_ms;      /*!< Maximum time between clicks to detect a double click */
    void (*callback)(button_event_t);   /*!< Callback function for button events */
} button_config_t;

/**
 * @brief Button handle type
 */
typedef void* button_handle_t;

/**
 * @brief Create and initialize a button
 *
 * @param config Pointer to button configuration
 * @return button_handle_t Handle to the button instance, or NULL if failed
 */
button_handle_t button_create(const button_config_t *config);

/**
 * @brief Delete a button instance
 *
 * @param btn_handle Handle to the button instance
 * @return ESP_OK on success, ESP_FAIL otherwise
 */
esp_err_t button_delete(button_handle_t btn_handle);

/**
 * @brief Get current button state
 *
 * @param btn_handle Handle to the button instance
 * @return Current button state
 */
button_state_t button_get_state(button_handle_t btn_handle);

/**
 * @brief Check if button is currently pressed
 *
 * @param btn_handle Handle to the button instance
 * @return true if button is pressed, false otherwise
 */
bool button_is_pressed(button_handle_t btn_handle);

#ifdef __cplusplus
}
#endif
