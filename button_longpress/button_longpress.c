#include "button_longpress.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/timers.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"

static const char *TAG = "BTN";

/**
 * @brief Macro for argument checking
 */
#define CHECK_ARG(ARG) do { \
    if (!(ARG)) { \
        ESP_LOGE(TAG, "Invalid argument: %s", #ARG); \
        return ESP_ERR_INVALID_ARG; \
    } \
} while (0)

/**
 * @brief Button instance structure
 */
typedef struct {
    gpio_num_t gpio_num;                /*!< GPIO number for button */
    bool active_level;                  /*!< Button active level */
    uint32_t debounce_time_ms;          /*!< Debounce time in milliseconds */
    uint32_t long_press_time_ms;        /*!< Long press time in milliseconds */
    uint32_t double_click_time_ms;      /*!< Double click time in milliseconds */
    void (*callback)(button_event_t);   /*!< Callback function */
    button_state_t state;               /*!< Current button state */
    TimerHandle_t debounce_timer;       /*!< Timer for debouncing */
    TimerHandle_t long_press_timer;     /*!< Timer for long press detection */
    TimerHandle_t double_click_timer;   /*!< Timer for double click detection */
    bool is_pressed;                    /*!< Current physical button state */
    bool waiting_for_double_click;      /*!< Flag indicating waiting for second click */
    uint32_t last_release_time;         /*!< Timestamp of last button release */
    uint8_t click_count;                /*!< Counter for click sequences */
    SemaphoreHandle_t mutex;            /*!< Mutex for thread safety */
} button_dev_t;

// Global variable to track the last event time for debouncing
static uint32_t last_event_time = 0;

/**
 * @brief Debounce timer callback
 */
static void button_debounce_timer_cb(TimerHandle_t timer)
{
    button_dev_t *btn = (button_dev_t *)pvTimerGetTimerID(timer);
    
    // Take the mutex for thread safety
    if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
        ESP_LOGE(TAG, "Failed to take mutex in debounce timer callback");
        return;
    }
    
    // Get the most up-to-date GPIO level
    int level = gpio_get_level(btn->gpio_num);
    
    // Make the active level check more explicit and consistent
    bool is_active;
    if (btn->active_level) {
        // Active high: button is active when level is high (1)
        is_active = (level == 1);
    } else {
        // Active low: button is active when level is low (0)
        is_active = (level == 0);
    }
    
    // Add consistency checks
    if (btn->state == BUTTON_STATE_LONG_PRESS && !btn->is_pressed) {
        btn->state = BUTTON_STATE_IDLE;  // Correct the inconsistency
    }

    // Add protection against rapid button presses
    uint32_t current_time = xTaskGetTickCount() * portTICK_PERIOD_MS;
    uint32_t min_event_interval = btn->debounce_time_ms / 2;  // Half the debounce time
    
    if (current_time - last_event_time < min_event_interval && is_active != btn->is_pressed) {
        xSemaphoreGive(btn->mutex);
        return;
    }
    
    if (is_active) {
        // Button is pressed after debounce
        if (!btn->is_pressed) {
            btn->is_pressed = true;
            
            // If we're waiting for a double click and a press occurs, this could be the second click
            if (btn->waiting_for_double_click) {
                // Stop the double click timer as we've detected a second press
                xTimerStop(btn->double_click_timer, 0);
                
                // Mark that we've detected the second press of a double click
                btn->state = BUTTON_STATE_PRESSED;  // Still in pressed state
                btn->waiting_for_double_click = false;  // No longer waiting
                btn->click_count = 2;  // Second click
                
                // We'll emit the DOUBLE_CLICK event on release, not on press
                // This allows for long press to take precedence if the button is held
            } else {
                btn->state = BUTTON_STATE_PRESSED;
                btn->click_count = 1;  // First click
            }
            
            // Start long press timer
            xTimerStart(btn->long_press_timer, 0);
            
            // Call callback if registered
            if (btn->callback) {
                xSemaphoreGive(btn->mutex);  // Release mutex before callback
                btn->callback(BUTTON_EVENT_PRESSED);
                if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                    ESP_LOGE(TAG, "Failed to retake mutex after callback");
                    return;
                }
            }
            
            // Update the last event time
            last_event_time = current_time;
        }
    } else {
        // Button is released
        if (btn->is_pressed) {
            btn->is_pressed = false;
            
            // Stop long press timer
            xTimerStop(btn->long_press_timer, 0);
            
            // Record the release time for double click detection
            btn->last_release_time = current_time;
            
            // If the button wasn't in long press state, it was a short press
            if (btn->state == BUTTON_STATE_PRESSED) {
                btn->state = BUTTON_STATE_SHORT_PRESS;
            }
            
            // Always emit RELEASED event
            if (btn->callback) {
                xSemaphoreGive(btn->mutex);  // Release mutex before callback
                btn->callback(BUTTON_EVENT_RELEASED);
                if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                    ESP_LOGE(TAG, "Failed to retake mutex after callback");
                    return;
                }
            }
            
            // Check for double click completion
            if (btn->click_count == 2 && btn->state != BUTTON_STATE_LONG_PRESS) {
                btn->state = BUTTON_STATE_DOUBLE_CLICK;
                
                // Call double click callback
                if (btn->callback) {
                    xSemaphoreGive(btn->mutex);  // Release mutex before callback
                    btn->callback(BUTTON_EVENT_DOUBLE_CLICK);
                    if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                        ESP_LOGE(TAG, "Failed to retake mutex after callback");
                        return;
                    }
                }
                
                // Reset click counter
                btn->click_count = 0;
            } else if (btn->click_count == 1 && btn->state != BUTTON_STATE_LONG_PRESS) {
                // Start waiting for a potential second click
                btn->waiting_for_double_click = true;
                btn->state = BUTTON_STATE_IDLE;
                
                // Start double click timer
                xTimerStart(btn->double_click_timer, 0);
            }
            
            // Update the last event time
            last_event_time = current_time;
        }
    }
    
    xSemaphoreGive(btn->mutex);
}

/**
 * @brief Long press timer callback
 */
static void button_long_press_timer_cb(TimerHandle_t timer)
{
    button_dev_t *btn = (button_dev_t *)pvTimerGetTimerID(timer);
    
    // Take the mutex for thread safety
    if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
        ESP_LOGE(TAG, "Failed to take mutex in long press timer callback");
        return;
    }
    
    // Check if button is still pressed
    if (btn->is_pressed) {
        // Double-check the actual GPIO level to be sure
        int level = gpio_get_level(btn->gpio_num);
        bool is_active;
        if (btn->active_level) {
            is_active = (level == 1);
        } else {
            is_active = (level == 0);
        }
        
        if (is_active) {
            // Cancel any pending double click detection
            btn->waiting_for_double_click = false;
            xTimerStop(btn->double_click_timer, 0);
            
            // Reset click counter to prevent double click after long press
            btn->click_count = 0;
            
            btn->state = BUTTON_STATE_LONG_PRESS;
            
            // Call callback if registered
            if (btn->callback) {
                xSemaphoreGive(btn->mutex);  // Release mutex before callback
                btn->callback(BUTTON_EVENT_LONG_PRESS);
                if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                    ESP_LOGE(TAG, "Failed to retake mutex after callback");
                    return;
                }
            }
        } else {
            // Button was released between the timer expiry and this callback
            btn->is_pressed = false;
        }
    }
    
    xSemaphoreGive(btn->mutex);
}

/**
 * @brief Double click timer callback
 */
static void button_double_click_timer_cb(TimerHandle_t timer)
{
    button_dev_t *btn = (button_dev_t *)pvTimerGetTimerID(timer);
    
    // Take the mutex for thread safety
    if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
        ESP_LOGE(TAG, "Failed to take mutex in double click timer callback");
        return;
    }
    
    // If this timer expires, it means the second click didn't come in time
    if (btn->waiting_for_double_click) {
        btn->waiting_for_double_click = false;
        
        // Ensure the button state is updated
        if (!btn->is_pressed) {
            btn->state = BUTTON_STATE_IDLE;
        }
        
        // Reset click counter
        btn->click_count = 0;
    }
    
    xSemaphoreGive(btn->mutex);
}

/**
 * @brief GPIO interrupt handler
 */
static void IRAM_ATTR button_isr_handler(void *arg)
{
    button_dev_t *btn = (button_dev_t *)arg;
    
    // Restart debounce timer
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    xTimerResetFromISR(btn->debounce_timer, &xHigherPriorityTaskWoken);
    
    if (xHigherPriorityTaskWoken) {
        portYIELD_FROM_ISR();
    }
}

button_handle_t button_create(const button_config_t *config)
{
    if (config == NULL) {
        ESP_LOGE(TAG, "Button configuration is NULL");
        return NULL;
    }
    
    if (config->gpio_num >= GPIO_NUM_MAX) {
        ESP_LOGE(TAG, "Invalid GPIO number: %d", config->gpio_num);
        return NULL;
    }
    
    // Allocate memory for button instance
    button_dev_t *btn = calloc(1, sizeof(button_dev_t));
    if (btn == NULL) {
        ESP_LOGE(TAG, "Failed to allocate memory for button");
        return NULL;
    }
    
    // Copy configuration
    btn->gpio_num = config->gpio_num;
    btn->active_level = config->active_level;
    btn->debounce_time_ms = config->debounce_time_ms > 0 ? config->debounce_time_ms : 20; // Default 20ms
    btn->long_press_time_ms = config->long_press_time_ms > 0 ? config->long_press_time_ms : 1000; // Default 1s
    btn->double_click_time_ms = config->double_click_time_ms > 0 ? config->double_click_time_ms : 300; // Default 300ms
    btn->callback = config->callback;
    btn->state = BUTTON_STATE_IDLE;
    btn->is_pressed = false;
    btn->waiting_for_double_click = false;
    btn->last_release_time = 0;
    btn->click_count = 0;
    
    // Create mutex for thread safety
    btn->mutex = xSemaphoreCreateMutex();
    if (btn->mutex == NULL) {
        ESP_LOGE(TAG, "Failed to create mutex");
        free(btn);
        return NULL;
    }
    
    // Configure GPIO
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << config->gpio_num),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = config->active_level ? GPIO_PULLDOWN_ENABLE : GPIO_PULLUP_ENABLE,
        .pull_down_en = config->active_level ? GPIO_PULLUP_DISABLE : GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_ANYEDGE,
    };
    
    esp_err_t ret = gpio_config(&io_conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to configure GPIO: %d", ret);
        vSemaphoreDelete(btn->mutex);
        free(btn);
        return NULL;
    }
    
    // Create debounce timer
    btn->debounce_timer = xTimerCreate("btn_debounce", 
                                       pdMS_TO_TICKS(btn->debounce_time_ms),
                                       pdFALSE,  // One-shot timer
                                       btn,      // Timer ID
                                       button_debounce_timer_cb);
    
    if (btn->debounce_timer == NULL) {
        ESP_LOGE(TAG, "Failed to create debounce timer");
        vSemaphoreDelete(btn->mutex);
        free(btn);
        return NULL;
    }
    
    // Create long press timer
    btn->long_press_timer = xTimerCreate("btn_long_press", 
                                         pdMS_TO_TICKS(btn->long_press_time_ms),
                                         pdFALSE,  // One-shot timer
                                         btn,      // Timer ID
                                         button_long_press_timer_cb);
    
    if (btn->long_press_timer == NULL) {
        ESP_LOGE(TAG, "Failed to create long press timer");
        xTimerDelete(btn->debounce_timer, 0);
        vSemaphoreDelete(btn->mutex);
        free(btn);
        return NULL;
    }
    
    // Create double click timer
    btn->double_click_timer = xTimerCreate("btn_double_click", 
                                          pdMS_TO_TICKS(btn->double_click_time_ms),
                                          pdFALSE,  // One-shot timer
                                          btn,      // Timer ID
                                          button_double_click_timer_cb);
    
    if (btn->double_click_timer == NULL) {
        ESP_LOGE(TAG, "Failed to create double click timer");
        xTimerDelete(btn->debounce_timer, 0);
        xTimerDelete(btn->long_press_timer, 0);
        vSemaphoreDelete(btn->mutex);
        free(btn);
        return NULL;
    }
    
    // Install GPIO ISR service if not already
    static bool isr_service_installed = false;
    if (!isr_service_installed) {
        ret = gpio_install_isr_service(0);
        if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
            ESP_LOGE(TAG, "Failed to install ISR service: %d", ret);
            xTimerDelete(btn->debounce_timer, 0);
            xTimerDelete(btn->long_press_timer, 0);
            xTimerDelete(btn->double_click_timer, 0);
            vSemaphoreDelete(btn->mutex);
            free(btn);
            return NULL;
        }
        isr_service_installed = true;
    }
    
    // Add ISR handler
    ret = gpio_isr_handler_add(btn->gpio_num, button_isr_handler, btn);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add ISR handler: %d", ret);
        xTimerDelete(btn->debounce_timer, 0);
        xTimerDelete(btn->long_press_timer, 0);
        xTimerDelete(btn->double_click_timer, 0);
        vSemaphoreDelete(btn->mutex);
        free(btn);
        return NULL;
    }
    
    // Start with a known state (not pressed) and use the debounce timer to detect the initial state
    btn->is_pressed = false;
    btn->state = BUTTON_STATE_IDLE;
    xTimerReset(btn->debounce_timer, 0);
    
    ESP_LOGI(TAG, "Button created on GPIO %d, active %s", 
             btn->gpio_num, btn->active_level ? "HIGH" : "LOW");
    
    return (button_handle_t)btn;
}

esp_err_t button_delete(button_handle_t btn_handle)
{
    CHECK_ARG(btn_handle);
    
    button_dev_t *btn = (button_dev_t *)btn_handle;
    
    // Remove ISR handler
    esp_err_t ret = gpio_isr_handler_remove(btn->gpio_num);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "Failed to remove ISR handler: %d", ret);
        // Continue with cleanup anyway, but log the error
    }
    
    // Delete timers
    if (btn->debounce_timer) {
        xTimerStop(btn->debounce_timer, 0);
        xTimerDelete(btn->debounce_timer, 0);
    }
    
    if (btn->long_press_timer) {
        xTimerStop(btn->long_press_timer, 0);
        xTimerDelete(btn->long_press_timer, 0);
    }
    
    if (btn->double_click_timer) {
        xTimerStop(btn->double_click_timer, 0);
        xTimerDelete(btn->double_click_timer, 0);
    }
    
    // Delete mutex
    if (btn->mutex) {
        vSemaphoreDelete(btn->mutex);
    }
    
    // Free memory
    free(btn);
    
    return ESP_OK;
}

button_state_t button_get_state(button_handle_t btn_handle)
{
    if (btn_handle == NULL) {
        ESP_LOGE(TAG, "Button handle is NULL");
        return BUTTON_STATE_IDLE;
    }
    
    button_dev_t *btn = (button_dev_t *)btn_handle;
    button_state_t state;
    
    if (xSemaphoreTake(btn->mutex, portMAX_DELAY) == pdTRUE) {
        state = btn->state;
        xSemaphoreGive(btn->mutex);
    } else {
        ESP_LOGE(TAG, "Failed to take mutex");
        state = BUTTON_STATE_IDLE;  // Default value
    }
    
    return state;
}

bool button_is_pressed(button_handle_t btn_handle)
{
    if (btn_handle == NULL) {
        ESP_LOGE(TAG, "Button handle is NULL");
        return false;
    }
    
    button_dev_t *btn = (button_dev_t *)btn_handle;
    bool is_pressed;
    
    if (xSemaphoreTake(btn->mutex, portMAX_DELAY) == pdTRUE) {
        is_pressed = btn->is_pressed;
        xSemaphoreGive(btn->mutex);
    } else {
        ESP_LOGE(TAG, "Failed to take mutex");
        is_pressed = false;  // Default value
    }
    
    return is_pressed;
}
