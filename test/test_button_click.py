"""
Tests for button click functionality
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

class TestButtonClick:
    """Test class for button click functionality"""
    
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
    
    def test_single_click_event(self, mock_button_component, button_config):
        """Test that single click event is generated after timeout"""
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
        
        # Perform single click
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Should have PRESSED and RELEASED events
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert len(callback_calls) == 2
        
        # Wait for double click timeout
        freertos.advance_time(350)  # Past double click timeout
        
        # Should now have CLICK event
        assert esp.BUTTON_EVENT_CLICK in callback_calls
        assert len(callback_calls) == 3
        
        # Button should be in IDLE state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        button_longpress.button_delete(button)
    
    def test_double_click_prevents_single_click(self, mock_button_component, button_config):
        """Test that double click prevents single click event"""
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
        
        # First click
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)
        
        # Second click within timeout
        freertos.advance_time(100)  # Within double click window
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)
        
        # Should have double click event, not single click
        assert esp.BUTTON_EVENT_DOUBLE_CLICK in callback_calls
        assert esp.BUTTON_EVENT_CLICK not in callback_calls
        
        button_longpress.button_delete(button)
    
    def test_long_press_prevents_click_events(self, mock_button_component, button_config):
        """Test that long press prevents both single and double click events"""
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=500,  # Shorter for testing
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Press and hold for long press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # Hold for long press duration
        freertos.advance_time(550)  # Past long press threshold
        
        # Should have long press event
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        
        # Release button
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)
        
        # Wait past double click timeout
        freertos.advance_time(350)
        
        # Should not have click events
        assert esp.BUTTON_EVENT_CLICK not in callback_calls
        assert esp.BUTTON_EVENT_DOUBLE_CLICK not in callback_calls
        
        button_longpress.button_delete(button)
    
    def test_click_timing_precision(self, mock_button_component):
        """Test click timing with various double click timeouts"""
        double_click_times = [200, 300, 500]
        
        for double_click_time_ms in double_click_times:
            config = ButtonConfig(
                gpio_num=4,
                active_level=True,
                debounce_time_ms=20,
                long_press_time_ms=1000,
                double_click_time_ms=double_click_time_ms,
                callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
            )
            
            button = button_longpress.button_create(ctypes.byref(config))
            assert button is not None
            
            callback_calls.clear()
            
            # Single click
            gpio.gpio_set_level(4, 1)
            freertos.advance_time(30)
            gpio.gpio_set_level(4, 0)
            freertos.advance_time(30)
            
            # Wait just past the double click timeout
            freertos.advance_time(double_click_time_ms + 50)
            
            # Should have click event
            assert esp.BUTTON_EVENT_CLICK in callback_calls
            
            button_longpress.button_delete(button)
            
            # Reset for next iteration
            freertos.current_time_ms = 0
            freertos.timers = {}
            freertos.timer_id = 0
            button_longpress.button_instances = {}
            button_longpress.next_button_id = 1
            gpio.reset()
            gpio.gpio_install_isr_service(0)
