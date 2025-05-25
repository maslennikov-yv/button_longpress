"""
Mock implementation of the button_longpress component for testing.
This file simulates the C implementation using Python.
"""

import ctypes
from conftest import esp, gpio, freertos, ButtonConfig

# Mock ESP-IDF functions that need to be exposed at module level for mocking
esp_log_write = lambda *args: None
gpio_config = gpio.gpio_config
gpio_get_level = gpio.gpio_get_level
gpio_set_level = gpio.gpio_set_level
gpio_install_isr_service = gpio.gpio_install_isr_service
gpio_isr_handler_add = gpio.gpio_isr_handler_add
gpio_isr_handler_remove = gpio.gpio_isr_handler_remove

# Mock FreeRTOS functions that need to be exposed at module level for mocking
xTimerCreate = freertos.xTimerCreate
xTimerStart = freertos.xTimerStart
xTimerStop = freertos.xTimerStop
xTimerDelete = freertos.xTimerDelete
xTimerReset = freertos.xTimerReset
xTimerResetFromISR = freertos.xTimerResetFromISR
pvTimerGetTimerID = freertos.pvTimerGetTimerID
xTaskGetTickCount = freertos.xTaskGetTickCount

# Mock button instance structure
class ButtonDev(ctypes.Structure):
    """Button instance structure"""
    _fields_ = [
        ("gpio_num", ctypes.c_int),
        ("active_level", ctypes.c_bool),
        ("debounce_time_ms", ctypes.c_uint32),
        ("long_press_time_ms", ctypes.c_uint32),
        ("double_click_time_ms", ctypes.c_uint32),
        ("callback", ctypes.c_void_p),
        ("state", ctypes.c_int),
        ("debounce_timer", ctypes.c_int),
        ("long_press_timer", ctypes.c_int),
        ("double_click_timer", ctypes.c_int),
        ("is_pressed", ctypes.c_bool),
        ("waiting_for_double_click", ctypes.c_bool),
        ("last_release_time", ctypes.c_uint32),
        ("click_count", ctypes.c_uint8),
        ("mutex", ctypes.c_void_p),
        ("last_event_time", ctypes.c_uint32)
    ]

# Global dictionary to store button instances
button_instances = {}
next_button_id = 1

# Define a C-compatible callback function type
BUTTON_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)

# Timer callback functions
def button_debounce_timer_cb(timer_id):
    """Debounce timer callback"""
    btn = None
    
    # Find the button associated with this timer
    for button_id, button in button_instances.items():
        if button.debounce_timer == timer_id:
            btn = button
            break
    
    if btn is None:
        return
    
    # Get the most up-to-date GPIO level
    level = gpio.gpio_get_level(btn.gpio_num)
    
    # Make the active level check more explicit and consistent
    if btn.active_level:
        # Active high: button is active when level is high (1)
        is_active = (level == 1)
    else:
        # Active low: button is active when level is low (0)
        is_active = (level == 0)
    
    # Add consistency checks
    if btn.state == esp.BUTTON_STATE_LONG_PRESS and not btn.is_pressed:
        btn.state = esp.BUTTON_STATE_IDLE  # Correct the inconsistency
    
    if is_active:
        # Button is pressed after debounce
        if not btn.is_pressed:
            btn.is_pressed = True
            
            # If we're waiting for a double click and a press occurs, this could be the second click
            if btn.waiting_for_double_click:
                # Stop the double click timer as we've detected a second press
                freertos.xTimerStop(btn.double_click_timer, 0)
                
                # Mark that we've detected the second press of a double click
                btn.state = esp.BUTTON_STATE_PRESSED  # Still in pressed state
                btn.waiting_for_double_click = False  # No longer waiting
                btn.click_count = 2  # Second click
                
                # We'll emit the DOUBLE_CLICK event on release, not on press
                # This allows for long press to take precedence if the button is held
            else:
                btn.state = esp.BUTTON_STATE_PRESSED
                btn.click_count = 1  # First click
            
            # Start long press timer
            freertos.xTimerStart(btn.long_press_timer, 0)
            
            # Call callback if registered
            if btn.callback:
                try:
                    callback_func = BUTTON_CALLBACK(btn.callback)
                    callback_func(esp.BUTTON_EVENT_PRESSED)
                except Exception as e:
                    pass
        else:
            pass
    else:
        # Button is released
        if btn.is_pressed:
            btn.is_pressed = False
            
            # Stop long press timer
            freertos.xTimerStop(btn.long_press_timer, 0)
            
            # Record the release time for double click detection
            btn.last_release_time = int(freertos.xTaskGetTickCount() * 10)  # Convert ticks to ms
            
            # If the button wasn't in long press state, it was a short press
            if btn.state == esp.BUTTON_STATE_PRESSED:
                btn.state = esp.BUTTON_STATE_SHORT_PRESS
            
            # Always emit RELEASED event
            if btn.callback:
                try:
                    callback_func = BUTTON_CALLBACK(btn.callback)
                    callback_func(esp.BUTTON_EVENT_RELEASED)
                except Exception as e:
                    pass
            
            # Check for double click completion
            if btn.click_count == 2 and btn.state != esp.BUTTON_STATE_LONG_PRESS:
                # Only emit double click if we're not in long press state
                btn.state = esp.BUTTON_STATE_DOUBLE_CLICK
                
                # Call double click callback
                if btn.callback:
                    try:
                        callback_func = BUTTON_CALLBACK(btn.callback)
                        callback_func(esp.BUTTON_EVENT_DOUBLE_CLICK)
                    except Exception as e:
                        pass
                
                # Reset click counter
                btn.click_count = 0
            elif btn.click_count == 1 and btn.state != esp.BUTTON_STATE_LONG_PRESS:
                # Only start waiting for double click if we're not in long press state
                # Start waiting for a potential second click
                btn.waiting_for_double_click = True
                
                # Start double click timer
                freertos.xTimerStart(btn.double_click_timer, 0)
            
            # Set state to IDLE if we're not in double click state
            if btn.state != esp.BUTTON_STATE_DOUBLE_CLICK:
                btn.state = esp.BUTTON_STATE_IDLE
        else:
            pass

def button_long_press_timer_cb(timer_id):
    """Long press timer callback"""
    btn = None
    
    # Find the button associated with this timer
    for button_id, button in button_instances.items():
        if button.long_press_timer == timer_id:
            btn = button
            break
    
    if btn is None:
        return
    
    # Check if button is still pressed
    if btn.is_pressed:
        # Double-check the actual GPIO level to be sure
        level = gpio.gpio_get_level(btn.gpio_num)
        if btn.active_level:
            is_active = (level == 1)
        else:
            is_active = (level == 0)
        
        if is_active:
            
            # Cancel any pending double click detection
            btn.waiting_for_double_click = False
            freertos.xTimerStop(btn.double_click_timer, 0)
            
            # Reset click counter to prevent double click after long press
            btn.click_count = 0
            
            btn.state = esp.BUTTON_STATE_LONG_PRESS
            
            # Call callback if registered
            if btn.callback:
                try:
                    callback_func = BUTTON_CALLBACK(btn.callback)
                    callback_func(esp.BUTTON_EVENT_LONG_PRESS)
                except Exception as e:
                    pass
        else:
            # Button was released between the timer expiry and this callback
            btn.is_pressed = False
    else:
        pass

def button_double_click_timer_cb(timer_id):
    """Double click timer callback"""
    btn = None
    
    # Find the button associated with this timer
    for button_id, button in button_instances.items():
        if button.double_click_timer == timer_id:
            btn = button
            break
    
    if btn is None:
        return
    
    # If this timer expires, it means the second click didn't come in time
    if btn.waiting_for_double_click:
        btn.waiting_for_double_click = False
        
        # Ensure the button state is updated
        if not btn.is_pressed:
            btn.state = esp.BUTTON_STATE_IDLE
        
        # Reset click counter
        btn.click_count = 0
    else:
        pass

def button_isr_handler(arg):
    """GPIO interrupt handler"""
    btn = ctypes.cast(arg, ctypes.POINTER(ButtonDev)).contents
    
    # Restart debounce timer
    freertos.xTimerResetFromISR(btn.debounce_timer, ctypes.byref(ctypes.c_int(0)))

# Button API functions
def button_create(config_arg):
    """Create and initialize a button"""
    global next_button_id
    
    if not config_arg:
        return None
    
    # Extract the actual configuration from the argument
    # This handles both direct pointers and byref arguments
    if isinstance(config_arg, ctypes.c_void_p):
        config_ptr = ctypes.cast(config_arg, ctypes.POINTER(ButtonConfig))
        config = config_ptr.contents
    elif hasattr(config_arg, 'contents'):
        config = config_arg.contents
    else:
        # For byref arguments, we need to get the original object
        # This is a bit of a hack, but it works for our testing purposes
        config = ButtonConfig.from_address(ctypes.addressof(config_arg._obj))
    
    if config.gpio_num >= esp.GPIO_NUM_MAX:
        return None
    
    # Allocate memory for button instance
    btn = ButtonDev()
    
    # Copy configuration
    btn.gpio_num = config.gpio_num
    btn.active_level = config.active_level
    btn.debounce_time_ms = config.debounce_time_ms if config.debounce_time_ms > 0 else 20
    btn.long_press_time_ms = config.long_press_time_ms if config.long_press_time_ms > 0 else 1000
    btn.double_click_time_ms = config.double_click_time_ms if config.double_click_time_ms > 0 else 300
    btn.callback = config.callback
    btn.state = esp.BUTTON_STATE_IDLE
    btn.is_pressed = False
    btn.waiting_for_double_click = False
    btn.last_release_time = 0
    btn.click_count = 0
    btn.mutex = ctypes.c_void_p(1)  # Dummy mutex for testing
    btn.last_event_time = 0
    
    # Configure GPIO
    class GpioConfig(ctypes.Structure):
        _fields_ = [
            ("pin_bit_mask", ctypes.c_uint64),
            ("mode", ctypes.c_int),
            ("pull_up_en", ctypes.c_int),
            ("pull_down_en", ctypes.c_int),
            ("intr_type", ctypes.c_int)
        ]
    
    io_conf = GpioConfig()
    io_conf.pin_bit_mask = 1 << config.gpio_num
    io_conf.mode = esp.GPIO_MODE_INPUT
    io_conf.pull_up_en = esp.GPIO_PULLUP_ENABLE if not config.active_level else esp.GPIO_PULLUP_DISABLE
    io_conf.pull_down_en = esp.GPIO_PULLDOWN_ENABLE if config.active_level else esp.GPIO_PULLDOWN_DISABLE
    io_conf.intr_type = esp.GPIO_INTR_ANYEDGE
    
    ret = gpio.gpio_config(io_conf)
    if ret != esp.ESP_OK:
        return None
    
    # Create debounce timer
    btn.debounce_timer = freertos.xTimerCreate(
        "btn_debounce",
        btn.debounce_time_ms // 10,  # Convert ms to ticks
        False,  # One-shot timer
        ctypes.addressof(btn),  # Timer ID
        button_debounce_timer_cb
    )
    
    if btn.debounce_timer == 0:
        return None
    
    # Create long press timer
    btn.long_press_timer = freertos.xTimerCreate(
        "btn_long_press",
        btn.long_press_time_ms // 10,  # Convert ms to ticks
        False,  # One-shot timer
        ctypes.addressof(btn),  # Timer ID
        button_long_press_timer_cb
    )
    
    if btn.long_press_timer == 0:
        freertos.xTimerDelete(btn.debounce_timer, 0)
        return None
    
    # Create double click timer
    btn.double_click_timer = freertos.xTimerCreate(
        "btn_double_click",
        btn.double_click_time_ms // 10,  # Convert ms to ticks
        False,  # One-shot timer
        ctypes.addressof(btn),  # Timer ID
        button_double_click_timer_cb
    )
    
    if btn.double_click_timer == 0:
        freertos.xTimerDelete(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
        return None
    
    # Install GPIO ISR service if not already
    ret = gpio.gpio_install_isr_service(0)
    if ret != esp.ESP_OK and ret != esp.ESP_ERR_INVALID_STATE:
        freertos.xTimerDelete(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
        freertos.xTimerDelete(btn.double_click_timer, 0)
        return None
    
    # Add ISR handler
    ret = gpio.gpio_isr_handler_add(btn.gpio_num, button_isr_handler, ctypes.addressof(btn))
    if ret != esp.ESP_OK:
        freertos.xTimerDelete(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
        freertos.xTimerDelete(btn.double_click_timer, 0)
        return None
    
    # Start with a known state (not pressed) and use the debounce timer to detect the initial state
    btn.is_pressed = False
    btn.state = esp.BUTTON_STATE_IDLE
    freertos.xTimerReset(btn.debounce_timer, 0)
    
    # Store button instance
    button_id = next_button_id
    next_button_id += 1
    button_instances[button_id] = btn
    
    return button_id

def button_delete(btn_handle):
    """Delete a button instance"""
    if not btn_handle or btn_handle not in button_instances:
        return esp.ESP_ERR_INVALID_ARG
    
    btn = button_instances[btn_handle]
    
    # Remove ISR handler
    gpio.gpio_isr_handler_remove(btn.gpio_num)
    
    # Delete timers
    if btn.debounce_timer:
        freertos.xTimerStop(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.debounce_timer, 0)
    
    if btn.long_press_timer:
        freertos.xTimerStop(btn.long_press_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
    
    if btn.double_click_timer:
        freertos.xTimerStop(btn.double_click_timer, 0)
        freertos.xTimerDelete(btn.double_click_timer, 0)
    
    # Remove button instance
    del button_instances[btn_handle]
    
    return esp.ESP_OK

def button_get_state(btn_handle):
    """Get current button state"""
    if not btn_handle or btn_handle not in button_instances:
        return esp.BUTTON_STATE_IDLE
    
    btn = button_instances[btn_handle]
    return btn.state

def button_is_pressed(btn_handle):
    """Check if button is currently pressed"""
    if not btn_handle or btn_handle not in button_instances:
        return False
    
    btn = button_instances[btn_handle]
    return btn.is_pressed
