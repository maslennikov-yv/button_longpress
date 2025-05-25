/**
 * @file button_longpress.h
 * @brief Button handling with debounce, long press, and double-click detection
 */

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
    BUTTON_EVENT_CLICK,         /*!< Button single click detected */
    BUTTON_EVENT_LONG_PRESS,    /*!< Button long press detected */
    BUTTON_EVENT_DOUBLE_CLICK   /*!< Button double click detected */
} button_event_t;

/**
 * @brief Button configuration structure
 */
typedef struct {
    gpio_num_t gpio_num;                /*!< GPIO number for button */
    bool active_level;                  /*!< Button active level (true: active high, false: active low) */
    uint32_t debounce_time_ms;          /*!< Debounce time in milliseconds (default: 20ms) */
    uint32_t long_press_time_ms;        /*!< Time in milliseconds to detect a long press (default: 1000ms) */
    uint32_t double_click_time_ms;      /*!< Maximum time between clicks to detect a double click (default: 300ms) */
    void (*callback)(button_event_t);   /*!< Callback function for button events */
} button_config_t;

/**
 * @brief Button handle type
 */
typedef void* button_handle_t;

/**
 * @brief Create and initialize a button
 *
 * This function creates a button instance with the specified configuration.
 * It sets up the GPIO, timers, and interrupt handlers needed for button operation.
 *
 * @param config Pointer to button configuration
 * @return button_handle_t Handle to the button instance, or NULL if failed
 */
button_handle_t button_create(const button_config_t *config);

/**
 * @brief Delete a button instance
 *
 * This function cleans up all resources associated with a button instance.
 *
 * @param btn_handle Handle to the button instance
 * @return ESP_OK on success, ESP_ERR_INVALID_ARG if btn_handle is NULL
 */
esp_err_t button_delete(button_handle_t btn_handle);

/**
 * @brief Get current button state
 *
 * This function returns the current state of the button.
 *
 * @param btn_handle Handle to the button instance
 * @return Current button state, BUTTON_STATE_IDLE if btn_handle is NULL
 */
button_state_t button_get_state(button_handle_t btn_handle);

/**
 * @brief Check if button is currently pressed
 *
 * This function returns whether the button is currently in the pressed state.
 *
 * @param btn_handle Handle to the button instance
 * @return true if button is pressed, false otherwise or if btn_handle is NULL
 */
bool button_is_pressed(button_handle_t btn_handle);

#ifdef __cplusplus
}
#endif
