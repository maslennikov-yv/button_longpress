import ctypes
import time

# Mock ESP-IDF and FreeRTOS
class ESP:
    ESP_OK = 0
    ESP_FAIL = -1
    ESP_ERR_INVALID_ARG = -2
    ESP_ERR_INVALID_STATE = -3
    
    GPIO_NUM_MAX = 40
    GPIO_MODE_INPUT = 1
    GPIO_PULLUP_ENABLE = 1
    GPIO_PULLUP_DISABLE = 0
    GPIO_PULLDOWN_ENABLE = 1
    GPIO_PULLDOWN_DISABLE = 0
    GPIO_INTR_ANYEDGE = 3

    # Button states - обновленные в соответствии с C реализацией
    BUTTON_STATE_IDLE = 0
    BUTTON_STATE_PRESSED = 1
    BUTTON_STATE_LONG_PRESS = 2
    BUTTON_STATE_SHORT_PRESS = 3
    BUTTON_STATE_DOUBLE_CLICK = 4

    # Button events
    BUTTON_EVENT_PRESSED = 0
    BUTTON_EVENT_RELEASED = 1
    BUTTON_EVENT_CLICK = 2
    BUTTON_EVENT_LONG_PRESS = 3
    BUTTON_EVENT_DOUBLE_CLICK = 4

esp = ESP()

class FreeRTOS:
    def xTimerCreate(self, name, period_ticks, auto_reload, timer_id, callback):
        print(f"DEBUG: Timer created: {name}, period: {period_ticks}, auto_reload: {auto_reload}, timer_id: {timer_id}, callback: {callback.__name__}")
        return id(callback)  # Mock timer ID

    def xTimerStart(self, timer_id, ticks_to_wait):
        print(f"DEBUG: Timer started: {timer_id}, wait: {ticks_to_wait}")

    def xTimerStop(self, timer_id, ticks_to_wait):
        print(f"DEBUG: Timer stopped: {timer_id}, wait: {ticks_to_wait}")

    def xTimerDelete(self, timer_id, ticks_to_wait):
        print(f"DEBUG: Timer deleted: {timer_id}, wait: {ticks_to_wait}")

    def xTaskGetTickCount(self):
        return int(time.time() * 100) # Mock tick count in 10ms units

freertos = FreeRTOS()

class GPIO:
    def gpio_install_isr_service(self, intr_flag):
        print(f"DEBUG: ISR service installed with flag: {intr_flag}")
        return esp.ESP_OK

    def gpio_config(self, io_conf):
        print(f"DEBUG: GPIO config: pin_bit_mask={io_conf.pin_bit_mask}, mode={io_conf.mode}, pull_up_en={io_conf.pull_up_en}, pull_down_en={io_conf.pull_down_en}, intr_type={io_conf.intr_type}")
        return esp.ESP_OK

    def gpio_isr_handler_add(self, gpio_num, isr_handler, args):
        print(f"DEBUG: ISR handler added for GPIO {gpio_num} with handler {isr_handler.__name__} and args {args}")
        return esp.ESP_OK

    def gpio_get_level(self, gpio_num):
        # Mock GPIO level - can be modified for testing
        if gpio_num in gpio_levels:
            return gpio_levels[gpio_num]
        else:
            return 0  # Default low
gpio = GPIO()

# Define button configuration structure
class ButtonConfig(ctypes.Structure):
    _fields_ = [
        ("gpio_num", ctypes.c_int),
        ("active_level", ctypes.c_int),
        ("long_press_time_ms", ctypes.c_int),
        ("double_click_time_ms", ctypes.c_int),
        ("debounce_time_ms", ctypes.c_int),
        ("callback", ctypes.c_void_p)  # Function pointer
    ]

# Define button device structure
class ButtonDev:
    def __init__(self):
        self.gpio_num = 0
        self.active_level = 0
        self.long_press_time_ms = 1000
        self.double_click_time_ms = 300
        self.debounce_time_ms = 20
        self.callback = None
        self.state = esp.BUTTON_STATE_IDLE
        self.is_pressed = False
        self.waiting_for_double_click = False
        self.last_release_time = 0
        self.click_count = 0
        self.mutex = None
        self.debounce_timer = 0
        self.long_press_timer = 0
        self.double_click_timer = 0
        self.last_event_time = 0

# Global variables
button_instances = {}
next_button_id = 1
gpio_levels = {} # Mock GPIO levels

# Define callback function type
BUTTON_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)

def button_isr_handler(args):
    """Interrupt service routine for button events"""
    btn = ctypes.cast(args, ctypes.POINTER(ButtonDev)).contents
    print(f"DEBUG: ISR triggered for GPIO {btn.gpio_num}")
    freertos.xTimerReset(btn.debounce_timer, 0)

def button_debounce_timer_cb(timer_id):
    """Debounce timer callback"""
    btn = None
    
    # Find the button associated with this timer
    for button_id, button in button_instances.items():
        if button.debounce_timer == timer_id:
            btn = button
            break
    
    if btn is None:
        print(f"DEBUG: No button found for debounce timer {timer_id}")
        return
    
    # Get the current GPIO level
    level = gpio.gpio_get_level(btn.gpio_num)
    
    # Determine if button is active based on configuration
    if btn.active_level:
        is_active = (level == 1)
    else:
        is_active = (level == 0)
    
    print(f"DEBUG: Debounce callback - GPIO {btn.gpio_num}, level: {level}, active_level: {btn.active_level}, is_active: {is_active}")
    
    # Fix state inconsistency if needed
    if btn.state == esp.BUTTON_STATE_LONG_PRESS and not btn.is_pressed:
        btn.state = esp.BUTTON_STATE_IDLE
    
    # Anti-noise protection - check timing
    current_time = int(freertos.xTaskGetTickCount() * 10)  # Convert ticks to ms
    min_event_interval = btn.debounce_time_ms // 2
    
    if current_time - btn.last_event_time < min_event_interval and is_active != btn.is_pressed:
        print(f"DEBUG: Event too soon after last event, ignoring")
        return
    
    if is_active:
        # Button press detected
        if not btn.is_pressed:
            btn.is_pressed = True
            
            # Handle potential double click
            if btn.waiting_for_double_click:
                print(f"DEBUG: Second click detected for double click")
                freertos.xTimerStop(btn.double_click_timer, 0)
                btn.state = esp.BUTTON_STATE_PRESSED
                btn.waiting_for_double_click = False
                btn.click_count = 2
            else:
                print(f"DEBUG: First click detected")
                btn.state = esp.BUTTON_STATE_PRESSED
                btn.click_count = 1
            
            # Start long press timer
            freertos.xTimerStart(btn.long_press_timer, 0)
            
            # Call press callback
            if btn.callback:
                try:
                    callback_func = BUTTON_CALLBACK(btn.callback)
                    callback_func(esp.BUTTON_EVENT_PRESSED)
                    print(f"DEBUG: PRESSED event callback called")
                except Exception as e:
                    print(f"DEBUG: Error in PRESSED callback: {e}")
            
            btn.last_event_time = current_time
    else:
        # Button release detected
        if btn.is_pressed:
            btn.is_pressed = False
            freertos.xTimerStop(btn.long_press_timer, 0)
            
            # Update state based on previous state
            if btn.state == esp.BUTTON_STATE_PRESSED:
                btn.state = esp.BUTTON_STATE_SHORT_PRESS
                print(f"DEBUG: Button state changed to SHORT_PRESS")
            
            # Call release callback
            if btn.callback:
                try:
                    callback_func = BUTTON_CALLBACK(btn.callback)
                    callback_func(esp.BUTTON_EVENT_RELEASED)
                    print(f"DEBUG: RELEASED event callback called")
                except Exception as e:
                    print(f"DEBUG: Error in RELEASED callback: {e}")
            
            # Handle double click detection
            if btn.click_count == 2 and btn.state != esp.BUTTON_STATE_LONG_PRESS:
                print(f"DEBUG: Double click completed")
                btn.state = esp.BUTTON_STATE_DOUBLE_CLICK
                
                if btn.callback:
                    try:
                        callback_func = BUTTON_CALLBACK(btn.callback)
                        callback_func(esp.BUTTON_EVENT_DOUBLE_CLICK)
                        print(f"DEBUG: DOUBLE_CLICK event callback called")
                    except Exception as e:
                        print(f"DEBUG: Error in DOUBLE_CLICK callback: {e}")
                
                btn.click_count = 0
                btn.waiting_for_double_click = False
            elif btn.click_count == 1 and btn.state != esp.BUTTON_STATE_LONG_PRESS:
                print(f"DEBUG: Starting double click wait period")
                btn.waiting_for_double_click = True
                btn.state = esp.BUTTON_STATE_IDLE  # Reset to IDLE while waiting
                freertos.xTimerStart(btn.double_click_timer, 0)
            
            btn.last_event_time = current_time

def button_long_press_timer_cb(timer_id):
    """Long press timer callback"""
    btn = None
    
    # Find the button associated with this timer
    for button_id, button in button_instances.items():
        if button.long_press_timer == timer_id:
            btn = button
            break
    
    if btn is None:
        print(f"DEBUG: No button found for long press timer {timer_id}")
        return
    
    print(f"DEBUG: Long press timer callback - button pressed: {btn.is_pressed}")
    
    # Check if button is still pressed
    if btn.is_pressed:
        # Double-check the actual GPIO level to be sure
        level = gpio.gpio_get_level(btn.gpio_num)
        if btn.active_level:
            is_active = (level == 1)
        else:
            is_active = (level == 0)
        
        if is_active:
            print(f"DEBUG: Long press confirmed")
            
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
                    print(f"DEBUG: LONG_PRESS event callback called")
                except Exception as e:
                    print(f"DEBUG: Error in LONG_PRESS callback: {e}")
        else:
            # Button was released between the timer expiry and this callback
            print(f"DEBUG: Button released before long press callback")
            btn.is_pressed = False

def button_double_click_timer_cb(timer_id):
    """Double click timer callback"""
    btn = None
    
    # Find the button associated with this timer
    for button_id, button in button_instances.items():
        if button.double_click_timer == timer_id:
            btn = button
            break
    
    if btn is None:
        print(f"DEBUG: No button found for double click timer {timer_id}")
        return
    
    print(f"DEBUG: Double click timer expired - waiting: {btn.waiting_for_double_click}")
    
    # If this timer expires, it means the second click didn't come in time
    if btn.waiting_for_double_click:
        btn.waiting_for_double_click = False
        
        # Trigger single click event since no second click occurred
        if btn.callback:
            try:
                callback_func = BUTTON_CALLBACK(btn.callback)
                callback_func(esp.BUTTON_EVENT_CLICK)
                print(f"DEBUG: CLICK event callback called")
            except Exception as e:
                print(f"DEBUG: Error in CLICK callback: {e}")
        
        # Ensure the button state is updated
        if not btn.is_pressed:
            btn.state = esp.BUTTON_STATE_IDLE
        
        # Reset click counter
        btn.click_count = 0
        print(f"DEBUG: Single click confirmed after timeout")

def button_create(config_arg):
    """Create and initialize a button"""
    global next_button_id
    
    if not config_arg:
        print("DEBUG: NULL config provided")
        return None
    
    # Extract the actual configuration from the argument
    try:
        if isinstance(config_arg, ctypes.c_void_p):
            config_ptr = ctypes.cast(config_arg, ctypes.POINTER(ButtonConfig))
            config = config_ptr.contents
        elif hasattr(config_arg, 'contents'):
            config = config_arg.contents
        else:
            # For byref arguments
            config = ButtonConfig.from_address(ctypes.addressof(config_arg._obj))
    except Exception as e:
        print(f"DEBUG: Error extracting config: {e}")
        return None
    
    if config.gpio_num >= esp.GPIO_NUM_MAX:
        print(f"DEBUG: Invalid GPIO number: {config.gpio_num}")
        return None
    
    # Allocate memory for button instance
    btn = ButtonDev()
    
    # Copy configuration with proper defaults
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
    
    print(f"DEBUG: Creating button - GPIO: {btn.gpio_num}, active_level: {btn.active_level}")
    print(f"DEBUG: Timings - debounce: {btn.debounce_time_ms}ms, long_press: {btn.long_press_time_ms}ms, double_click: {btn.double_click_time_ms}ms")
    
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
        print(f"DEBUG: GPIO config failed: {ret}")
        return None
    
    # Create timers with proper tick conversion
    tick_rate_hz = 100  # 100Hz = 10ms per tick
    
    btn.debounce_timer = freertos.xTimerCreate(
        "btn_debounce",
        btn.debounce_time_ms * tick_rate_hz // 1000,  # Convert ms to ticks
        False,  # One-shot timer
        ctypes.addressof(btn),  # Timer ID
        button_debounce_timer_cb
    )
    
    if btn.debounce_timer == 0:
        print("DEBUG: Failed to create debounce timer")
        return None
    
    btn.long_press_timer = freertos.xTimerCreate(
        "btn_long_press",
        btn.long_press_time_ms * tick_rate_hz // 1000,  # Convert ms to ticks
        False,  # One-shot timer
        ctypes.addressof(btn),  # Timer ID
        button_long_press_timer_cb
    )
    
    if btn.long_press_timer == 0:
        print("DEBUG: Failed to create long press timer")
        freertos.xTimerDelete(btn.debounce_timer, 0)
        return None
    
    btn.double_click_timer = freertos.xTimerCreate(
        "btn_double_click",
        btn.double_click_time_ms * tick_rate_hz // 1000,  # Convert ms to ticks
        False,  # One-shot timer
        ctypes.addressof(btn),  # Timer ID
        button_double_click_timer_cb
    )
    
    if btn.double_click_timer == 0:
        print("DEBUG: Failed to create double click timer")
        freertos.xTimerDelete(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
        return None
    
    # Install GPIO ISR service if not already installed
    ret = gpio.gpio_install_isr_service(0)
    if ret != esp.ESP_OK and ret != esp.ESP_ERR_INVALID_STATE:
        print(f"DEBUG: Failed to install ISR service: {ret}")
        freertos.xTimerDelete(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
        freertos.xTimerDelete(btn.double_click_timer, 0)
        return None
    
    # Add ISR handler
    ret = gpio.gpio_isr_handler_add(btn.gpio_num, button_isr_handler, ctypes.addressof(btn))
    if ret != esp.ESP_OK:
        print(f"DEBUG: Failed to add ISR handler: {ret}")
        freertos.xTimerDelete(btn.debounce_timer, 0)
        freertos.xTimerDelete(btn.long_press_timer, 0)
        freertos.xTimerDelete(btn.double_click_timer, 0)
        return None
    
    # Initialize state and start the debounce timer to detect initial state
    btn.is_pressed = False
    btn.state = esp.BUTTON_STATE_IDLE
    freertos.xTimerReset(btn.debounce_timer, 0)
    
    # Store button instance
    button_id = next_button_id
    next_button_id += 1
    button_instances[button_id] = btn
    
    print(f"DEBUG: Button created successfully with ID {button_id}")
    return button_id
