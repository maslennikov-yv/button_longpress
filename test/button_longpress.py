"""
Mock implementation of button_longpress module for testing
"""
import ctypes

# Import mock objects from conftest
try:
    from conftest import esp, gpio, freertos
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from conftest import esp, gpio, freertos

# Global state for button instances
button_instances = {}
next_button_id = 1

class ButtonInstance:
    """Internal button instance representation"""
    def __init__(self, config):
        self.gpio_num = config.gpio_num
        self.active_level = config.active_level
        self.debounce_time_ms = config.debounce_time_ms or 20
        self.long_press_time_ms = config.long_press_time_ms or 1000
        self.double_click_time_ms = config.double_click_time_ms or 300
        self.callback = config.callback
        self.state = esp.BUTTON_STATE_IDLE
        self.is_pressed = False
        self.debounce_timer = None
        self.long_press_timer = None
        self.double_click_timer = None
        self.click_count = 0
        self.waiting_for_double_click = False

def button_create(config_ptr):
    """Create a button instance"""
    global next_button_id
    
    if not config_ptr:
        return None
    
    try:
        config = config_ptr.contents
    except:
        return None
    
    # Validate GPIO number
    if config.gpio_num < 0 or config.gpio_num >= esp.GPIO_NUM_MAX:
        return None
    
    # Create button instance
    button_id = next_button_id
    next_button_id += 1
    
    button = ButtonInstance(config)
    button_instances[button_id] = button
    
    # Configure GPIO
    gpio_config = type('GPIOConfig', (), {
        'pin_bit_mask': 1 << config.gpio_num,
        'mode': esp.GPIO_MODE_INPUT,
        'pull_up_en': esp.GPIO_PULLUP_ENABLE,
        'pull_down_en': esp.GPIO_PULLDOWN_DISABLE,
        'intr_type': esp.GPIO_INTR_ANYEDGE
    })()
    
    gpio.gpio_config(gpio_config)
    
    # Create timers
    button.debounce_timer = freertos.xTimerCreate(
        f"debounce_{button_id}", 
        button.debounce_time_ms // 10,  # Convert to ticks
        False,  # One-shot
        button_id,
        debounce_timer_callback
    )
    
    button.long_press_timer = freertos.xTimerCreate(
        f"longpress_{button_id}",
        button.long_press_time_ms // 10,  # Convert to ticks
        False,  # One-shot
        button_id,
        long_press_timer_callback
    )
    
    button.double_click_timer = freertos.xTimerCreate(
        f"doubleclick_{button_id}",
        button.double_click_time_ms // 10,  # Convert to ticks
        False,  # One-shot
        button_id,
        double_click_timer_callback
    )
    
    # Install ISR handler
    gpio.gpio_isr_handler_add(config.gpio_num, gpio_isr_handler, button_id)
    
    return button_id

def button_delete(button_handle):
    """Delete a button instance"""
    if not button_handle or button_handle not in button_instances:
        return esp.ESP_ERR_INVALID_ARG
    
    button = button_instances[button_handle]
    
    # Remove ISR handler
    gpio.gpio_isr_handler_remove(button.gpio_num)
    
    # Delete timers
    if button.debounce_timer:
        freertos.xTimerDelete(button.debounce_timer, 0)
    if button.long_press_timer:
        freertos.xTimerDelete(button.long_press_timer, 0)
    if button.double_click_timer:
        freertos.xTimerDelete(button.double_click_timer, 0)
    
    # Remove from instances
    del button_instances[button_handle]
    
    return esp.ESP_OK

def button_get_state(button_handle):
    """Get button state"""
    if not button_handle or button_handle not in button_instances:
        return esp.BUTTON_STATE_IDLE
    
    return button_instances[button_handle].state

def button_is_pressed(button_handle):
    """Check if button is pressed"""
    if not button_handle or button_handle not in button_instances:
        return False
    
    return button_instances[button_handle].is_pressed

def gpio_isr_handler(button_id):
    """GPIO ISR handler"""
    if button_id not in button_instances:
        return
    
    button = button_instances[button_id]
    freertos.xTimerReset(button.debounce_timer, 0)

def debounce_timer_callback(timer_id):
    """Debounce timer callback"""
    # Find button by timer ID
    button_id = None
    for bid, button in button_instances.items():
        if button.debounce_timer == timer_id:
            button_id = bid
            break
    
    if button_id is None:
        return
    
    button = button_instances[button_id]
    current_level = gpio.gpio_get_level(button.gpio_num)
    is_active = (current_level == 1) if button.active_level else (current_level == 0)
    
    if is_active and not button.is_pressed:
        # Confirmed button press
        button.is_pressed = True
        button.state = esp.BUTTON_STATE_PRESSED
        
        # Handle double click detection
        if button.waiting_for_double_click:
            button.click_count = 2
            button.waiting_for_double_click = False
            freertos.xTimerStop(button.double_click_timer, 0)
        else:
            button.click_count = 1
        
        # Start long press timer
        freertos.xTimerStart(button.long_press_timer, 0)
        
        # Call callback
        if button.callback:
            callback_func = ctypes.CFUNCTYPE(None, ctypes.c_int)(button.callback)
            callback_func(esp.BUTTON_EVENT_PRESSED)
    
    elif not is_active and button.is_pressed:
        # Confirmed button release
        button.is_pressed = False
        
        # Stop long press timer
        freertos.xTimerStop(button.long_press_timer, 0)
        
        if button.state == esp.BUTTON_STATE_LONG_PRESS:
            # Was a long press, reset state
            button.state = esp.BUTTON_STATE_IDLE
            button.click_count = 0
        else:
            # Was a short press
            button.state = esp.BUTTON_STATE_SHORT_PRESS
            
            if button.click_count == 2:
                # Double click detected
                button.state = esp.BUTTON_STATE_DOUBLE_CLICK
                button.click_count = 0
                button.waiting_for_double_click = False
                freertos.xTimerStop(button.double_click_timer, 0)
                
                if button.callback:
                    callback_func = ctypes.CFUNCTYPE(None, ctypes.c_int)(button.callback)
                    callback_func(esp.BUTTON_EVENT_DOUBLE_CLICK)
            elif button.click_count == 1:
                # First click, start double click timer
                button.waiting_for_double_click = True
                button.state = esp.BUTTON_STATE_IDLE
                freertos.xTimerStart(button.double_click_timer, 0)
        
        # Call released callback
        if button.callback:
            callback_func = ctypes.CFUNCTYPE(None, ctypes.c_int)(button.callback)
            callback_func(esp.BUTTON_EVENT_RELEASED)

def long_press_timer_callback(timer_id):
    """Long press timer callback"""
    # Find button by timer ID
    button_id = None
    for bid, button in button_instances.items():
        if button.long_press_timer == timer_id:
            button_id = bid
            break
    
    if button_id is None:
        return
    
    button = button_instances[button_id]
    
    if button.is_pressed and button.state == esp.BUTTON_STATE_PRESSED:
        button.state = esp.BUTTON_STATE_LONG_PRESS
        
        # Cancel double click detection
        button.waiting_for_double_click = False
        freertos.xTimerStop(button.double_click_timer, 0)
        button.click_count = 0
        
        # Call callback
        if button.callback:
            callback_func = ctypes.CFUNCTYPE(None, ctypes.c_int)(button.callback)
            callback_func(esp.BUTTON_EVENT_LONG_PRESS)

def double_click_timer_callback(timer_id):
    """Double click timeout callback"""
    # Find button by timer ID
    button_id = None
    for bid, button in button_instances.items():
        if button.double_click_timer == timer_id:
            button_id = bid
            break
    
    if button_id is None:
        return
    
    button = button_instances[button_id]
    
    if button.waiting_for_double_click and button.click_count == 1:
        # Single click confirmed
        button.waiting_for_double_click = False
        button.click_count = 0
        button.state = esp.BUTTON_STATE_IDLE
        
        # Call click callback
        if button.callback:
            callback_func = ctypes.CFUNCTYPE(None, ctypes.c_int)(button.callback)
            callback_func(esp.BUTTON_EVENT_CLICK)
