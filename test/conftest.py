import pytest
import ctypes
import time
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add path to the button_longpress component
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Mock ESP-IDF components
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
    BUTTON_EVENT_LONG_PRESS = 2
    BUTTON_EVENT_DOUBLE_CLICK = 3

# Create a global instance of MockESP
esp = MockESP()

# Mock FreeRTOS functionality
class MockFreeRTOS:
    """Mock class for FreeRTOS functionality"""
    
    def __init__(self):
        self.timers = {}
        self.timer_id = 0
        self.current_time_ms = 0
    
    def xTimerCreate(self, name, period_ticks, auto_reload, timer_id, callback):
        """Create a timer"""
        self.timer_id += 1
        timer = {
            'id': self.timer_id,
            'name': name,
            'period_ms': period_ticks * 10,  # Convert ticks to ms (assuming 100Hz tick rate)
            'auto_reload': auto_reload,
            'timer_id': timer_id,
            'callback': callback,
            'running': False,
            'expiry_time': 0
        }
        self.timers[self.timer_id] = timer
        print(f"DEBUG: Timer created: {self.timer_id}, name: {name}, period: {period_ticks * 10}ms")
        return self.timer_id
    
    def xTimerStart(self, timer_id, block_time):
        """Start a timer"""
        if timer_id in self.timers:
            self.timers[timer_id]['running'] = True
            self.timers[timer_id]['expiry_time'] = self.current_time_ms + self.timers[timer_id]['period_ms']
            print(f"DEBUG: Timer {timer_id} started, will expire at {self.timers[timer_id]['expiry_time']}ms")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerStart")
        return 0  # pdFAIL
    
    def xTimerStop(self, timer_id, block_time):
        """Stop a timer"""
        if timer_id in self.timers:
            self.timers[timer_id]['running'] = False
            print(f"DEBUG: Timer {timer_id} stopped")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerStop")
        return 0  # pdFAIL
    
    def xTimerDelete(self, timer_id, block_time):
        """Delete a timer"""
        if timer_id in self.timers:
            del self.timers[timer_id]
            print(f"DEBUG: Timer {timer_id} deleted")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerDelete")
        return 0  # pdFAIL
    
    def xTimerReset(self, timer_id, block_time):
        """Reset a timer"""
        if timer_id in self.timers:
            self.timers[timer_id]['expiry_time'] = self.current_time_ms + self.timers[timer_id]['period_ms']
            self.timers[timer_id]['running'] = True
            print(f"DEBUG: Timer {timer_id} reset, will expire at {self.timers[timer_id]['expiry_time']}ms")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerReset")
        return 0  # pdFAIL
    
    def xTimerResetFromISR(self, timer_id, higher_priority_task_woken):
        """Reset a timer from ISR"""
        result = self.xTimerReset(timer_id, 0)
        print(f"DEBUG: Timer {timer_id} reset from ISR, result: {result}")
        return result
    
    def pvTimerGetTimerID(self, timer_id):
        """Get timer ID"""
        if timer_id in self.timers:
            return self.timers[timer_id]['timer_id']
        print(f"DEBUG: Timer {timer_id} not found in pvTimerGetTimerID")
        return None
    
    def xTaskGetTickCount(self):
        """Get current tick count"""
        return self.current_time_ms // 10  # Convert ms to ticks (assuming 100Hz tick rate)
    
    def advance_time(self, ms):
        """Advance time and process timers"""
        print(f"DEBUG: Advancing time by {ms}ms from {self.current_time_ms}ms to {self.current_time_ms + ms}ms")
        self.current_time_ms += ms
        
        # Check for expired timers
        for timer_id, timer in list(self.timers.items()):
            if timer['running'] and self.current_time_ms >= timer['expiry_time']:
                print(f"DEBUG: Timer {timer_id} expired at {self.current_time_ms}ms")
                timer['running'] = not timer['auto_reload']
                if timer['auto_reload']:
                    timer['expiry_time'] = self.current_time_ms + timer['period_ms']
                
                # Call the callback
                if timer['callback']:
                    print(f"DEBUG: Calling callback for timer {timer_id}")
                    timer['callback'](timer_id)
                else:
                    print(f"DEBUG: No callback for timer {timer_id}")

# Create a global instance of MockFreeRTOS
freertos = MockFreeRTOS()

# Mock GPIO functionality
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
                self.pins[pin] = {
                    'mode': config.mode,
                    'pull_up_en': config.pull_up_en,
                    'pull_down_en': config.pull_down_en,
                    'intr_type': config.intr_type,
                    'level': 0  # Default level is low
                }
                print(f"DEBUG: Configured GPIO {pin}, pull_up: {config.pull_up_en}, pull_down: {config.pull_down_en}")
            pin_bit_mask >>= 1
            pin += 1
        
        return esp.ESP_OK
    
    def gpio_get_level(self, gpio_num):
        """Get the level of a GPIO pin"""
        if gpio_num in self.pins:
            return self.pins[gpio_num]['level']
        return 0
    
    def gpio_set_level(self, gpio_num, level):
        """Set the level of a GPIO pin"""
        if gpio_num in self.pins:
            old_level = self.pins[gpio_num]['level']
            self.pins[gpio_num]['level'] = level
            print(f"DEBUG: Setting GPIO {gpio_num} from {old_level} to {level}")
            
            # Trigger ISR if level changed and there's a handler
            if old_level != level and gpio_num in self.isr_handlers:
                print(f"DEBUG: Level changed, triggering ISR for GPIO {gpio_num}")
                self.isr_handlers[gpio_num](self.isr_args[gpio_num])
            else:
                if old_level == level:
                    print(f"DEBUG: Level didn't change, not triggering ISR")
                elif gpio_num not in self.isr_handlers:
                    print(f"DEBUG: No ISR handler for GPIO {gpio_num}")
            
            return esp.ESP_OK
        print(f"DEBUG: GPIO {gpio_num} not found in gpio_set_level")
        return esp.ESP_ERR_INVALID_ARG
    
    def gpio_install_isr_service(self, intr_alloc_flags):
        """Install GPIO ISR service"""
        if self.isr_service_installed:
            print("DEBUG: ISR service already installed")
            return esp.ESP_ERR_INVALID_STATE
        
        self.isr_service_installed = True
        print("DEBUG: ISR service installed")
        return esp.ESP_OK
    
    def gpio_isr_handler_add(self, gpio_num, isr_handler, args):
        """Add an ISR handler for a GPIO pin"""
        if gpio_num >= esp.GPIO_NUM_MAX:
            print(f"DEBUG: Invalid GPIO number: {gpio_num}")
            return esp.ESP_ERR_INVALID_ARG
        
        self.isr_handlers[gpio_num] = isr_handler
        self.isr_args[gpio_num] = args
        print(f"DEBUG: ISR handler added for GPIO {gpio_num}")
        return esp.ESP_OK
    
    def gpio_isr_handler_remove(self, gpio_num):
        """Remove an ISR handler for a GPIO pin"""
        if gpio_num in self.isr_handlers:
            del self.isr_handlers[gpio_num]
            del self.isr_args[gpio_num]
            print(f"DEBUG: ISR handler removed for GPIO {gpio_num}")
            return esp.ESP_OK
        print(f"DEBUG: No ISR handler for GPIO {gpio_num}")
        return esp.ESP_ERR_INVALID_ARG

# Create a global instance of MockGPIO
gpio = MockGPIO()

# Mock button_longpress component
class ButtonConfig(ctypes.Structure):
    """Button configuration structure"""
    _fields_ = [
        ("gpio_num", ctypes.c_int),
        ("active_level", ctypes.c_bool),
        ("debounce_time_ms", ctypes.c_uint32),
        ("long_press_time_ms", ctypes.c_uint32),
        ("double_click_time_ms", ctypes.c_uint32),
        ("callback", ctypes.c_void_p)
    ]

# Mock the button_longpress component
@pytest.fixture
def mock_button_component(monkeypatch):
    """Mock the button_longpress component"""
    
    # Import the module here to avoid circular imports
    import button_longpress
    
    # Mock ESP-IDF functions
    monkeypatch.setattr('button_longpress.esp_log_write', MagicMock())
    monkeypatch.setattr('button_longpress.gpio_config', gpio.gpio_config)
    monkeypatch.setattr('button_longpress.gpio_get_level', gpio.gpio_get_level)
    monkeypatch.setattr('button_longpress.gpio_set_level', gpio.gpio_set_level)
    monkeypatch.setattr('button_longpress.gpio_install_isr_service', gpio.gpio_install_isr_service)
    monkeypatch.setattr('button_longpress.gpio_isr_handler_add', gpio.gpio_isr_handler_add)
    monkeypatch.setattr('button_longpress.gpio_isr_handler_remove', gpio.gpio_isr_handler_remove)
    
    # Mock FreeRTOS functions
    monkeypatch.setattr('button_longpress.xTimerCreate', freertos.xTimerCreate)
    monkeypatch.setattr('button_longpress.xTimerStart', freertos.xTimerStart)
    monkeypatch.setattr('button_longpress.xTimerStop', freertos.xTimerStop)
    monkeypatch.setattr('button_longpress.xTimerDelete', freertos.xTimerDelete)
    monkeypatch.setattr('button_longpress.xTimerReset', freertos.xTimerReset)
    monkeypatch.setattr('button_longpress.xTimerResetFromISR', freertos.xTimerResetFromISR)
    monkeypatch.setattr('button_longpress.pvTimerGetTimerID', freertos.pvTimerGetTimerID)
    monkeypatch.setattr('button_longpress.xTaskGetTickCount', freertos.xTaskGetTickCount)
    
    # Reset mock state
    gpio.pins = {}
    gpio.isr_handlers = {}
    gpio.isr_args = {}
    gpio.isr_service_installed = False
    freertos.timers = {}
    freertos.timer_id = 0
    freertos.current_time_ms = 0
    
    return {
        'gpio': gpio,
        'freertos': freertos,
        'esp': esp
    }

@pytest.fixture
def button_callback():
    """Create a button callback function"""
    # Define a C-compatible callback function type
    BUTTON_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)
    
    # Create a callback function that does nothing
    @BUTTON_CALLBACK
    def callback(event):
        return None
    
    return callback

@pytest.fixture
def button_config(button_callback):
    """Create a button configuration"""
    config = {
        'gpio_num': 4,
        'active_level': True,
        'debounce_time_ms': 20,
        'long_press_time_ms': 1000,
        'double_click_time_ms': 300,
        'callback': button_callback
    }
    return config

# Add metadata to test report
def pytest_configure(config):
    """Add metadata to pytest HTML report"""
    # Add environment info
    config._metadata = {
        'Project': 'ESP-IDF Button Component',
        'Python': sys.version,
        'Platform': sys.platform,
        'CI': os.environ.get('CI', 'false')
    }
    
    # Create results directory if it doesn't exist
    if not os.path.exists('results'):
        os.makedirs('results')

# Custom hook for test results
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect test results for reporting"""
    outcome = yield
    report = outcome.get_result()
    
    # Store test results for later use
    if report.when == 'call':
        test_result = {
            'name': item.name,
            'outcome': report.outcome,
            'duration': report.duration,
            'longrepr': str(report.longrepr) if report.longrepr else None
        }
        
        # Save to file for CI/CD reporting
        results_file = os.path.join('results', 'test_results.json')
        
        # Read existing results if file exists
        results = []
        if os.path.exists(results_file):
            with open(results_file, 'r') as f:
                try:
                    results = json.load(f)
                except json.JSONDecodeError:
                    results = []
        
        # Add new result
        results.append(test_result)
        
        # Write updated results
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
