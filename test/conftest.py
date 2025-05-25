"""
Pytest configuration and mock objects for ESP-IDF button component testing
"""
import pytest
import ctypes
import sys
import os

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

class MockESP:
    """Mock class for ESP-IDF functionality"""
    
    # ESP error codes
    ESP_OK = 0
    ESP_FAIL = -1
    ESP_ERR_INVALID_ARG = -2
    ESP_ERR_INVALID_STATE = -3
    
    # GPIO definitions
    GPIO_NUM_MAX = 40
    GPIO_MODE_INPUT = 1
    GPIO_PULLUP_ENABLE = 1
    GPIO_PULLDOWN_ENABLE = 1
    GPIO_PULLUP_DISABLE = 0
    GPIO_PULLDOWN_DISABLE = 0
    GPIO_INTR_ANYEDGE = 3
    
    # Button states
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

class MockFreeRTOS:
    """Mock class for FreeRTOS functionality"""
    
    def __init__(self):
        self.timers = {}
        self.timer_id = 0
        self.current_time_ms = 0
        self.tick_rate_hz = 100  # 100Hz tick rate (10ms per tick)
    
    def xTimerCreate(self, name, period_ticks, auto_reload, timer_id, callback):
        """Create a timer"""
        self.timer_id += 1
        timer = {
            'id': self.timer_id,
            'name': name,
            'period_ms': period_ticks * (1000 // self.tick_rate_hz),
            'auto_reload': auto_reload,
            'timer_id': timer_id,
            'callback': callback,
            'running': False,
            'expiry_time': 0,
            'created_time': self.current_time_ms
        }
        self.timers[self.timer_id] = timer
        return self.timer_id
    
    def xTimerStart(self, timer_id, block_time):
        """Start a timer"""
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            timer['running'] = True
            timer['expiry_time'] = self.current_time_ms + timer['period_ms']
            return 1  # pdPASS
        return 0  # pdFAIL
    
    def xTimerStop(self, timer_id, block_time):
        """Stop a timer"""
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            timer['running'] = False
            return 1  # pdPASS
        return 0  # pdFAIL
    
    def xTimerDelete(self, timer_id, block_time):
        """Delete a timer"""
        if timer_id in self.timers:
            del self.timers[timer_id]
            return 1  # pdPASS
        return 0  # pdFAIL
    
    def xTimerReset(self, timer_id, block_time):
        """Reset a timer"""
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            timer['expiry_time'] = self.current_time_ms + timer['period_ms']
            timer['running'] = True
            return 1  # pdPASS
        return 0  # pdFAIL
    
    def pvTimerGetTimerID(self, timer_id):
        """Get timer ID"""
        if timer_id in self.timers:
            return self.timers[timer_id]['timer_id']
        return timer_id  # Return the timer_id itself as fallback
    
    def xTaskGetTickCount(self):
        """Get current tick count"""
        return self.current_time_ms * self.tick_rate_hz // 1000
    
    def advance_time(self, ms):
        """Advance time and process timers"""
        if ms <= 0:
            return
            
        target_time = self.current_time_ms + ms
        
        # Process timers in chronological order
        while self.current_time_ms < target_time:
            # Find the next timer to expire
            next_expiry = target_time
            next_timer = None
            
            for timer_id, timer in self.timers.items():
                if (timer['running'] and 
                    timer['expiry_time'] > self.current_time_ms and 
                    timer['expiry_time'] <= next_expiry):
                    next_expiry = timer['expiry_time']
                    next_timer = timer_id
            
            if next_timer is not None:
                # Advance to the next timer expiry
                self.current_time_ms = next_expiry
                timer = self.timers[next_timer]
                
                # Stop the timer (one-shot behavior)
                timer['running'] = False
                
                # Handle auto-reload
                if timer['auto_reload']:
                    timer['expiry_time'] = self.current_time_ms + timer['period_ms']
                    timer['running'] = True
                
                # Call the callback
                if timer['callback']:
                    try:
                        timer['callback'](next_timer)
                    except Exception as e:
                        print(f"DEBUG: Error in timer callback: {e}")
            else:
                # No more timers to process, advance to target time
                self.current_time_ms = target_time

class MockGPIO:
    """Mock class for GPIO functionality"""
    
    def __init__(self):
        self.pins = {}
        self.isr_handlers = {}
        self.isr_args = {}
        self.isr_service_installed = False
    
    def gpio_config(self, config):
        """Configure a GPIO pin"""
        pin_bit_mask = config.pin_bit_mask
        
        # Extract the pin number from the bit mask
        pin = 0
        while pin_bit_mask:
            if pin_bit_mask & 1:
                # Set initial level based on pull-up/pull-down configuration
                initial_level = 1 if config.pull_up_en else 0
                
                self.pins[pin] = {
                    'mode': config.mode,
                    'pull_up_en': config.pull_up_en,
                    'pull_down_en': config.pull_down_en,
                    'intr_type': config.intr_type,
                    'level': initial_level,
                    'configured': True
                }
            pin_bit_mask >>= 1
            pin += 1
        
        return esp.ESP_OK
    
    def gpio_get_level(self, gpio_num):
        """Get the level of a GPIO pin"""
        if gpio_num in self.pins:
            return self.pins[gpio_num]['level']
        return 0
    
    def gpio_set_level(self, gpio_num, level):
        """Set the level of a GPIO pin (simulates external button press/release)"""
        if gpio_num in self.pins:
            old_level = self.pins[gpio_num]['level']
            self.pins[gpio_num]['level'] = level
            
            # Trigger ISR if level changed and there's a handler
            if old_level != level and gpio_num in self.isr_handlers:
                try:
                    self.isr_handlers[gpio_num](self.isr_args[gpio_num])
                except Exception as e:
                    print(f"DEBUG: Error in ISR handler: {e}")
            
            return esp.ESP_OK
        return esp.ESP_ERR_INVALID_ARG
    
    def gpio_install_isr_service(self, intr_alloc_flags):
        """Install GPIO ISR service"""
        if self.isr_service_installed:
            return esp.ESP_ERR_INVALID_STATE
        
        self.isr_service_installed = True
        return esp.ESP_OK
    
    def gpio_isr_handler_add(self, gpio_num, isr_handler, args):
        """Add an ISR handler for a GPIO pin"""
        if gpio_num >= esp.GPIO_NUM_MAX:
            return esp.ESP_ERR_INVALID_ARG
        
        if not self.isr_service_installed:
            return esp.ESP_ERR_INVALID_STATE
        
        self.isr_handlers[gpio_num] = isr_handler
        self.isr_args[gpio_num] = args
        return esp.ESP_OK
    
    def gpio_isr_handler_remove(self, gpio_num):
        """Remove an ISR handler for a GPIO pin"""
        if gpio_num in self.isr_handlers:
            del self.isr_handlers[gpio_num]
            if gpio_num in self.isr_args:
                del self.isr_args[gpio_num]
            return esp.ESP_OK
        return esp.ESP_ERR_INVALID_ARG
    
    def reset(self):
        """Reset GPIO state"""
        self.pins = {}
        self.isr_handlers = {}
        self.isr_args = {}
        self.isr_service_installed = False

# Define ButtonConfig structure for C compatibility
class ButtonConfig(ctypes.Structure):
    _fields_ = [
        ("gpio_num", ctypes.c_int),
        ("active_level", ctypes.c_bool),
        ("debounce_time_ms", ctypes.c_uint32),
        ("long_press_time_ms", ctypes.c_uint32),
        ("double_click_time_ms", ctypes.c_uint32),
        ("callback", ctypes.c_void_p)
    ]

# Create global instances of mock objects
esp = MockESP()
gpio = MockGPIO()
freertos = MockFreeRTOS()

# Pytest fixtures
@pytest.fixture
def mock_button_component():
    """Fixture to set up the button component mock environment"""
    # Reset all mock states
    gpio.reset()
    freertos.timers = {}
    freertos.timer_id = 0
    freertos.current_time_ms = 0
    
    # Install ISR service
    gpio.gpio_install_isr_service(0)
    
    yield
    
    # Cleanup after test
    gpio.reset()
    freertos.timers = {}

@pytest.fixture
def button_config():
    """Fixture providing default button configuration"""
    return {
        'gpio_num': 4,
        'active_level': True,
        'debounce_time_ms': 20,
        'long_press_time_ms': 1000,
        'double_click_time_ms': 300
    }
