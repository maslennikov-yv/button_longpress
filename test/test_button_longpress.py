"""
Comprehensive tests for ESP-IDF button component
"""
import pytest
import ctypes
import sys
import os

# Ensure proper imports
sys.path.insert(0, os.path.dirname(__file__))

# Import the conftest module to access the mock objects
from conftest import esp, gpio, freertos, ButtonConfig

# Import the button_longpress module
import button_longpress

# Define a C-compatible callback function type
BUTTON_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)

# Global variable to track callback calls
callback_calls = []

# C-compatible callback function that records calls
@BUTTON_CALLBACK
def button_callback_func(event):
    callback_calls.append(event)
    return None

class TestButtonLongPress:
    """Test class for button_longpress component"""
    
    def setup_method(self):
        """Setup method called before each test"""
        # Clear the callback calls
        callback_calls.clear()
        
        # Reset mock state
        gpio.reset()
        freertos.timers = {}
        freertos.timer_id = 0
        freertos.current_time_ms = 0
        
        # Clear button instances
        button_longpress.button_instances = {}
        button_longpress.next_button_id = 1
        
        # Install ISR service
        gpio.gpio_install_isr_service(0)
    
    def test_button_create_valid_config(self, mock_button_component, button_config):
        """Test button creation with valid configuration"""
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=button_config['active_level'],
            debounce_time_ms=button_config['debounce_time_ms'],
            long_press_time_ms=button_config['long_press_time_ms'],
            double_click_time_ms=button_config['double_click_time_ms'],
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        
        # Verify button was created
        assert button is not None
        assert button in button_longpress.button_instances
        
        # Verify GPIO was configured
        assert button_config['gpio_num'] in gpio.pins
        assert gpio.pins[button_config['gpio_num']]['mode'] == esp.GPIO_MODE_INPUT
        
        # Verify timers were created (3 timers: debounce, long press, double click)
        assert len(freertos.timers) == 3
        
        # Verify initial state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        assert button_longpress.button_is_pressed(button) == False
        
        # Clean up
        result = button_longpress.button_delete(button)
        assert result == esp.ESP_OK
    
    def test_button_create_invalid_gpio(self, mock_button_component):
        """Test button creation with invalid GPIO number"""
        config = ButtonConfig(
            gpio_num=esp.GPIO_NUM_MAX + 1,  # Invalid GPIO number
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is None
    
    def test_button_create_null_config(self, mock_button_component):
        """Test button creation with NULL configuration"""
        button = button_longpress.button_create(None)
        assert button is None
    
    def test_button_delete_null_handle(self, mock_button_component):
        """Test button deletion with NULL handle"""
        result = button_longpress.button_delete(None)
        assert result == esp.ESP_ERR_INVALID_ARG
    
    def test_button_delete_invalid_handle(self, mock_button_component):
        """Test button deletion with invalid handle"""
        result = button_longpress.button_delete(999)  # Non-existent button
        assert result == esp.ESP_ERR_INVALID_ARG
    
    def test_button_press_active_high(self, mock_button_component, button_config):
        """Test button press detection with active high configuration"""
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=button_config['debounce_time_ms'],
            long_press_time_ms=button_config['long_press_time_ms'],
            double_click_time_ms=button_config['double_click_time_ms'],
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Simulate button press (set GPIO high)
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance time past debounce period
        freertos.advance_time(button_config['debounce_time_ms'] + 10)
        
        # Verify callback was called with BUTTON_EVENT_PRESSED
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_PRESSED
        assert button_longpress.button_is_pressed(button) == True
        
        button_longpress.button_delete(button)
    
    def test_button_press_active_low(self, mock_button_component, button_config):
        """Test button press detection with active low configuration"""
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=False,  # Active low
            debounce_time_ms=button_config['debounce_time_ms'],
            long_press_time_ms=button_config['long_press_time_ms'],
            double_click_time_ms=button_config['double_click_time_ms'],
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # GPIO should be initially high due to pull-up
        assert gpio.gpio_get_level(button_config['gpio_num']) == 1
        
        callback_calls.clear()
        
        # Simulate button press (set GPIO low for active low)
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        
        # Advance time past debounce period
        freertos.advance_time(button_config['debounce_time_ms'] + 10)
        
        # Verify callback was called with BUTTON_EVENT_PRESSED
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_PRESSED
        assert button_longpress.button_is_pressed(button) == True
        
        button_longpress.button_delete(button)
    
    def test_long_press_detection(self, mock_button_component, button_config):
        """Test long press detection with precise timing"""
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Simulate button press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # Verify PRESSED event
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time to just before long press threshold
        freertos.advance_time(long_press_time_ms - 50)
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        
        # Advance time past long press threshold
        freertos.advance_time(100)
        
        # Verify LONG_PRESS event
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        assert len(callback_calls) == 2
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_LONG_PRESS
        
        button_longpress.button_delete(button)
    
    def test_double_click_detection(self, mock_button_component, button_config):
        """Test double click detection with proper timing"""
        double_click_time_ms = 300
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=double_click_time_ms,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # First click
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)
        
        # Verify first click events
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert len(callback_calls) == 2
        
        # Wait short time (within double click window)
        freertos.advance_time(double_click_time_ms // 2)
        
        # Second click
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)
        
        # Verify double click was detected
        assert esp.BUTTON_EVENT_DOUBLE_CLICK in callback_calls
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_DOUBLE_CLICK
        
        button_longpress.button_delete(button)
    
    def test_short_press_sequence(self, mock_button_component, button_config):
        """Test short press sequence with state verification"""
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Press button
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # Verify PRESSED event and PRESSED state
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_PRESSED
        assert button_longpress.button_is_pressed(button) == True
        
        # Hold for short duration
        freertos.advance_time(500)  # Less than long press time
        
        # Verify still in PRESSED state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_PRESSED
        
        # Release button
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Verify RELEASED event
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        assert len(callback_calls) == 2
        assert button_longpress.button_is_pressed(button) == False
        
        # Wait for double click timeout
        freertos.advance_time(400)
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        button_longpress.button_delete(button)
    
    def test_debounce_filtering(self, mock_button_component, button_config):
        """Test that debouncing filters out noise"""
        debounce_time_ms = 50
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=debounce_time_ms,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Simulate contact bounce (rapid toggles)
        for i in range(10):
            gpio.gpio_set_level(button_config['gpio_num'], i % 2)
            freertos.advance_time(5)  # Less than debounce time
        
        # No callbacks should have been triggered
        assert len(callback_calls) == 0
        
        # Set stable press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(debounce_time_ms + 10)
        
        # Now callback should be triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        button_longpress.button_delete(button)
    
    def test_multiple_buttons(self, mock_button_component):
        """Test creating and managing multiple buttons"""
        # Create first button (active high)
        config1 = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button1 = button_longpress.button_create(ctypes.byref(config1))
        assert button1 is not None
        
        # Create second button (active low)
        config2 = ButtonConfig(
            gpio_num=5,
            active_level=False,
            debounce_time_ms=30,
            long_press_time_ms=1500,
            double_click_time_ms=400,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button2 = button_longpress.button_create(ctypes.byref(config2))
        assert button2 is not None
        
        # Verify both buttons exist
        assert len(button_longpress.button_instances) == 2
        assert button1 != button2
        
        # Test independent operation
        callback_calls.clear()
        
        # Press button1
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        
        # Press button2
        gpio.gpio_set_level(5, 0)  # Active low
        freertos.advance_time(40)
        
        # Both should have triggered PRESSED events
        assert callback_calls.count(esp.BUTTON_EVENT_PRESSED) == 2
        
        # Clean up
        assert button_longpress.button_delete(button1) == esp.ESP_OK
        assert button_longpress.button_delete(button2) == esp.ESP_OK
    
    def test_get_state_null_handle(self, mock_button_component):
        """Test get_state with null handle"""
        state = button_longpress.button_get_state(None)
        assert state == esp.BUTTON_STATE_IDLE
        
    def test_is_pressed_null_handle(self, mock_button_component):
        """Test is_pressed with null handle"""
        pressed = button_longpress.button_is_pressed(None)
        assert pressed == False
        
    def test_get_state_invalid_handle(self, mock_button_component):
        """Test get_state with invalid handle"""
        state = button_longpress.button_get_state(999)
        assert state == esp.BUTTON_STATE_IDLE
        
    def test_is_pressed_invalid_handle(self, mock_button_component):
        """Test is_pressed with invalid handle"""
        pressed = button_longpress.button_is_pressed(999)
        assert pressed == False
