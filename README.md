/**
* @file button_longpress.c
* @brief Implementation of button handling with debounce, long press, and double-click detection
  */

#include "button_longpress.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/timers.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"

static const char *TAG = "BTN";

/* Macro for argument validation */
#define CHECK_ARG(ARG) do { \
if (!(ARG)) { \
ESP_LOGE(TAG, "Invalid argument"); \
return ESP_ERR_INVALID_ARG; \
} \
} while (0)

/* Button instance structure */
typedef struct {
/* Configuration */
gpio_num_t gpio_num;                /*!< GPIO number for button */
bool active_level;                  /*!< Button active level */
uint32_t debounce_time_ms;          /*!< Debounce time in milliseconds */
uint32_t long_press_time_ms;        /*!< Long press time in milliseconds */
uint32_t double_click_time_ms;      /*!< Double click time in milliseconds */
void (*callback)(button_event_t);   /*!< Callback function */

    /* State */
    button_state_t state;               /*!< Current button state */
    bool is_pressed;                    /*!< Current physical button state */
    bool waiting_for_double_click;      /*!< Flag indicating waiting for second click */
    uint8_t click_count;                /*!< Counter for click sequences */
    
    /* Timers */
    TimerHandle_t debounce_timer;       /*!< Timer for debouncing */
    TimerHandle_t long_press_timer;     /*!< Timer for long press detection */
    TimerHandle_t double_click_timer;   /*!< Timer for double click detection */
    
    /* Synchronization */
    SemaphoreHandle_t mutex;            /*!< Mutex for thread safety */
} button_dev_t;

/* Global variable to track the last event time for debouncing */
static uint32_t s_last_event_time = 0;

/**
* @brief Debounce timer callback
*
* This function is called when the debounce timer expires.
* It processes the button state after debounce period.
  */
  static void button_debounce_timer_cb(TimerHandle_t timer)
  {
  button_dev_t *btn = (button_dev_t *)pvTimerGetTimerID(timer);

  if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
  ESP_LOGE(TAG, "Mutex error in debounce callback");
  return;
  }

  /* Get current GPIO level and determine if button is active */
  int level = gpio_get_level(btn->gpio_num);
  bool is_active = (btn->active_level) ? (level == 1) : (level == 0);

  /* Fix state inconsistency if needed */
  if (btn->state == BUTTON_STATE_LONG_PRESS && !btn->is_pressed) {
  btn->state = BUTTON_STATE_IDLE;
  }

  /* Anti-noise protection */
  uint32_t current_time = xTaskGetTickCount() * portTICK_PERIOD_MS;
  uint32_t min_event_interval = btn->debounce_time_ms / 2;

  if (current_time - s_last_event_time < min_event_interval && is_active != btn->is_pressed) {
  xSemaphoreGive(btn->mutex);
  return;
  }

  if (is_active) {
  /* Button press detected */
  if (!btn->is_pressed) {
  btn->is_pressed = true;

           /* Handle potential double click */
           if (btn->waiting_for_double_click) {
               xTimerStop(btn->double_click_timer, 0);
               btn->state = BUTTON_STATE_PRESSED;
               btn->waiting_for_double_click = false;
               btn->click_count = 2;
           } else {
               btn->state = BUTTON_STATE_PRESSED;
               btn->click_count = 1;
           }
           
           /* Start long press timer */
           xTimerStart(btn->long_press_timer, 0);
           
           /* Call press callback */
           if (btn->callback) {
               xSemaphoreGive(btn->mutex);
               btn->callback(BUTTON_EVENT_PRESSED);
               if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                   ESP_LOGE(TAG, "Mutex error after press callback");
                   return;
               }
           }
           
           s_last_event_time = current_time;
       }
  } else {
  /* Button release detected */
  if (btn->is_pressed) {
  btn->is_pressed = false;
  xTimerStop(btn->long_press_timer, 0);

           /* Update state */
           if (btn->state == BUTTON_STATE_PRESSED) {
               btn->state = BUTTON_STATE_SHORT_PRESS;
           }
           
           /* Call release callback */
           if (btn->callback) {
               xSemaphoreGive(btn->mutex);
               btn->callback(BUTTON_EVENT_RELEASED);
               if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                   ESP_LOGE(TAG, "Mutex error after release callback");
                   return;
               }
           }
           
           /* Handle double click detection */
           if (btn->click_count == 2 && btn->state != BUTTON_STATE_LONG_PRESS) {
               btn->state = BUTTON_STATE_DOUBLE_CLICK;
               
               if (btn->callback) {
                   xSemaphoreGive(btn->mutex);
                   btn->callback(BUTTON_EVENT_DOUBLE_CLICK);
                   if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                       ESP_LOGE(TAG, "Mutex error after double click callback");
                       return;
                   }
               }
               
               btn->click_count = 0;
           } else if (btn->click_count == 1 && btn->state != BUTTON_STATE_LONG_PRESS) {
               btn->waiting_for_double_click = true;
               btn->state = BUTTON_STATE_IDLE;
               xTimerStart(btn->double_click_timer, 0);
           }
           
           s_last_event_time = current_time;
       }
  }

  xSemaphoreGive(btn->mutex);
  }

/**
* @brief Long press timer callback
*
* This function is called when the long press timer expires.
* It processes the long press event.
  */
  static void button_long_press_timer_cb(TimerHandle_t timer)
  {
  button_dev_t *btn = (button_dev_t *)pvTimerGetTimerID(timer);

  if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
  ESP_LOGE(TAG, "Mutex error in long press callback");
  return;
  }

  /* Verify button is still pressed */
  if (btn->is_pressed) {
  int level = gpio_get_level(btn->gpio_num);
  bool is_active = (btn->active_level) ? (level == 1) : (level == 0);

       if (is_active) {
           /* Cancel double click detection */
           btn->waiting_for_double_click = false;
           xTimerStop(btn->double_click_timer, 0);
           btn->click_count = 0;
           btn->state = BUTTON_STATE_LONG_PRESS;
           
           if (btn->callback) {
               xSemaphoreGive(btn->mutex);
               btn->callback(BUTTON_EVENT_LONG_PRESS);
               if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
                   ESP_LOGE(TAG, "Mutex error after long press callback");
                   return;
               }
           }
       } else {
           /* Button was released between timer expiry and callback execution */
           btn->is_pressed = false;
       }
  }

  xSemaphoreGive(btn->mutex);
  }

/**
* @brief Double click timer callback
*
* This function is called when the double click timer expires.
* It handles the case when the second click doesn't arrive in time.
  */
  static void button_double_click_timer_cb(TimerHandle_t timer)
  {
  button_dev_t *btn = (button_dev_t *)pvTimerGetTimerID(timer);

  if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
  ESP_LOGE(TAG, "Mutex error in double click callback");
  return;
  }

  /* Reset double click state if timer expires */
  if (btn->waiting_for_double_click) {
  btn->waiting_for_double_click = false;

       /* Trigger single click event since no second click occurred */
       if (btn->callback) {
           xSemaphoreGive(btn->mutex);
           btn->callback(BUTTON_EVENT_CLICK);
           if (xSemaphoreTake(btn->mutex, portMAX_DELAY) != pdTRUE) {
               ESP_LOGE(TAG, "Mutex error after click callback");
               return;
           }
       }
       
       /* Ensure the button state is updated */
       if (!btn->is_pressed) {
           btn->state = BUTTON_STATE_IDLE;
       }
       
       /* Reset click counter */
       btn->click_count = 0;
       ESP_LOGD(TAG, "Single click confirmed after timeout");
  }

  xSemaphoreGive(btn->mutex);
  }

/**
* @brief GPIO interrupt handler
*
* This function is called when a GPIO interrupt occurs.
* It resets the debounce timer to start debouncing.
  */
  static void IRAM_ATTR button_isr_handler(void *arg)
  {
  button_dev_t *btn = (button_dev_t *)arg;
  BaseType_t xHigherPriorityTaskWoken = pdFALSE;

  xTimerResetFromISR(btn->debounce_timer, &xHigherPriorityTaskWoken);

  if (xHigherPriorityTaskWoken) {
  portYIELD_FROM_ISR();
  }
  }

/**
* @brief Create and initialize a button
*
* @param config Pointer to button configuration
* @return button_handle_t Handle to the button instance, or NULL if failed
  */
  button_handle_t button_create(const button_config_t *config)
  {
  /* Validate parameters */
  if (config == NULL || config->gpio_num >= GPIO_NUM_MAX) {
  ESP_LOGE(TAG, "Invalid button configuration");
  return NULL;
  }

  /* Allocate memory for button instance */
  button_dev_t *btn = calloc(1, sizeof(button_dev_t));
  if (btn == NULL) {
  ESP_LOGE(TAG, "Memory allocation failed");
  return NULL;
  }

  /* Initialize button configuration with defaults for zero values */
  btn->gpio_num = config->gpio_num;
  btn->active_level = config->active_level;
  btn->debounce_time_ms = config->debounce_time_ms > 0 ? config->debounce_time_ms : 20;
  btn->long_press_time_ms = config->long_press_time_ms > 0 ? config->long_press_time_ms : 1000;
  btn->double_click_time_ms = config->double_click_time_ms > 0 ? config->double_click_time_ms : 300;
  btn->callback = config->callback;
  btn->state = BUTTON_STATE_IDLE;
  btn->is_pressed = false;
  btn->waiting_for_double_click = false;
  btn->click_count = 0;

  /* Create mutex for thread safety */
  btn->mutex = xSemaphoreCreateMutex();
  if (btn->mutex == NULL) {
  ESP_LOGE(TAG, "Mutex creation failed");
  free(btn);
  return NULL;
  }

  /* Configure GPIO */
  gpio_config_t io_conf = {
  .pin_bit_mask = (1ULL << config->gpio_num),
  .mode = GPIO_MODE_INPUT,
  .pull_up_en = config->active_level ? GPIO_PULLDOWN_ENABLE : GPIO_PULLUP_ENABLE,
  .pull_down_en = config->active_level ? GPIO_PULLUP_DISABLE : GPIO_PULLDOWN_DISABLE,
  .intr_type = GPIO_INTR_ANYEDGE,
  };

  if (gpio_config(&io_conf) != ESP_OK) {
  ESP_LOGE(TAG, "GPIO configuration failed");
  vSemaphoreDelete(btn->mutex);
  free(btn);
  return NULL;
  }

  /* Create timers */
  btn->debounce_timer = xTimerCreate("btn_dbnc",
  pdMS_TO_TICKS(btn->debounce_time_ms),
  pdFALSE, btn, button_debounce_timer_cb);

  btn->long_press_timer = xTimerCreate("btn_long",
  pdMS_TO_TICKS(btn->long_press_time_ms),
  pdFALSE, btn, button_long_press_timer_cb);

  btn->double_click_timer = xTimerCreate("btn_dblc",
  pdMS_TO_TICKS(btn->double_click_time_ms),
  pdFALSE, btn, button_double_click_timer_cb);

  /* Verify timer creation */
  if (btn->debounce_timer == NULL || btn->long_press_timer == NULL || btn->double_click_timer == NULL) {
  ESP_LOGE(TAG, "Timer creation failed");
  if (btn->debounce_timer) xTimerDelete(btn->debounce_timer, 0);
  if (btn->long_press_timer) xTimerDelete(btn->long_press_timer, 0);
  if (btn->double_click_timer) xTimerDelete(btn->double_click_timer, 0);
  vSemaphoreDelete(btn->mutex);
  free(btn);
  return NULL;
  }

  /* Install ISR service if needed */
  static bool isr_service_installed = false;
  if (!isr_service_installed) {
  esp_err_t ret = gpio_install_isr_service(0);
  if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
  ESP_LOGE(TAG, "ISR service installation failed: %d", ret);
  xTimerDelete(btn->debounce_timer, 0);
  xTimerDelete(btn->long_press_timer, 0);
  xTimerDelete(btn->double_click_timer, 0);
  vSemaphoreDelete(btn->mutex);
  free(btn);
  return NULL;
  }
  isr_service_installed = true;
  }

  /* Add ISR handler */
  if (gpio_isr_handler_add(btn->gpio_num, button_isr_handler, btn) != ESP_OK) {
  ESP_LOGE(TAG, "ISR handler addition failed");
  xTimerDelete(btn->debounce_timer, 0);
  xTimerDelete(btn->long_press_timer, 0);
  xTimerDelete(btn->double_click_timer, 0);
  vSemaphoreDelete(btn->mutex);
  free(btn);
  return NULL;
  }

  /* Initialize state and start the debounce timer */
  btn->is_pressed = false;
  btn->state = BUTTON_STATE_IDLE;
  xTimerReset(btn->debounce_timer, 0);

  ESP_LOGI(TAG, "Button created on GPIO %d, active %s",
  btn->gpio_num, btn->active_level ? "HIGH" : "LOW");

  return (button_handle_t)btn;
  }

/**
* @brief Delete a button instance and clean up resources
*
* @param btn_handle Handle to the button instance
* @return ESP_OK on success, ESP_ERR_INVALID_ARG otherwise
  */
  esp_err_t button_delete(button_handle_t btn_handle)
  {
  CHECK_ARG(btn_handle);

  button_dev_t *btn = (button_dev_t *)btn_handle;

  /* Remove ISR handler */
  esp_err_t ret = gpio_isr_handler_remove(btn->gpio_num);
  if (ret != ESP_OK) {
  ESP_LOGW(TAG, "ISR handler removal failed: %d", ret);
  /* Continue with cleanup anyway */
  }

  /* Delete timers */
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

  /* Delete mutex */
  if (btn->mutex) {
  vSemaphoreDelete(btn->mutex);
  }

  /* Free memory */
  free(btn);

  return ESP_OK;
  }

/**
* @brief Get current button state
*
* @param btn_handle Handle to the button instance
* @return Current button state
  */
  button_state_t button_get_state(button_handle_t btn_handle)
  {
  if (btn_handle == NULL) {
  ESP_LOGW(TAG, "Null button handle in get_state");
  return BUTTON_STATE_IDLE;
  }

  button_dev_t *btn = (button_dev_t *)btn_handle;
  button_state_t state = BUTTON_STATE_IDLE;

  if (xSemaphoreTake(btn->mutex, portMAX_DELAY) == pdTRUE) {
  state = btn->state;
  xSemaphoreGive(btn->mutex);
  } else {
  ESP_LOGE(TAG, "Mutex error in get_state");
  }

  return state;
  }

/**
* @brief Check if button is currently pressed
*
* @param btn_handle Handle to the button instance
* @return true if button is pressed, false otherwise
  */
  bool button_is_pressed(button_handle_t btn_handle)
  {
  if (btn_handle == NULL) {
  ESP_LOGW(TAG, "Null button handle in is_pressed");
  return false;
  }

  button_dev_t *btn = (button_dev_t *)btn_handle;
  bool is_pressed = false;

  if (xSemaphoreTake(btn->mutex, portMAX_DELAY) == pdTRUE) {
  is_pressed = btn->is_pressed;
  xSemaphoreGive(btn->mutex);
  } else {
  ESP_LOGE(TAG, "Mutex error in is_pressed");
  }

  return is_pressed;
  }
