import pytest
import ctypes
import time
from unittest.mock import MagicMock, patch
import sys
import os

# Import the conftest module to access the mock objects
from conftest import esp, gpio, freertos, ButtonConfig

# Import the button_longpress module (this will be mocked)
import button_longpress

# Define a C-compatible callback function type
BUTTON_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)

# Global variable to track callback calls
callback_calls = []

# C-compatible callback function that records calls
@BUTTON_CALLBACK
def button_callback_func(event):
    callback_calls.append(event)
    print(f"DEBUG: Callback received event: {event}")
    return None

class TestButtonClick:
    """Test class specifically for BUTTON_EVENT_CLICK functionality"""
    
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
        
        print("DEBUG: Test setup completed")
    
    def test_single_click_basic(self, mock_button_component):
        """Test basic single click detection"""
        config = ButtonConfig(
            gpio_num=4,
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
        gpio.gpio_set_level(4, 1)  # Press
        freertos.advance_time(30)  # Past debounce
        
        gpio.gpio_set_level(4, 0)  # Release
        freertos.advance_time(30)  # Past debounce
        
        # Should have PRESSED and RELEASED events
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert len(callback_calls) == 2
        
        # Wait for double click timeout to expire
        freertos.advance_time(350)  # Past double click timeout (300ms)
        
        # Should now have CLICK event
        assert esp.BUTTON_EVENT_CLICK in callback_calls
        assert len(callback_calls) == 3
        
        # Should not have double click or long press
        assert esp.BUTTON_EVENT_DOUBLE_CLICK not in callback_calls
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        
        # Button should be back to idle state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        button_longpress.button_delete(button)
    
    def test_click_vs_double_click(self, mock_button_component):
        """Test that single click is not triggered when double click occurs"""
        config = ButtonConfig(
            gpio_num=4,
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
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Wait within double click window
        freertos.advance_time(150)  # 150ms < 300ms
        
        # Second click
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Should have double click, not single click
        assert esp.BUTTON_EVENT_DOUBLE_CLICK in callback_calls
        assert esp.BUTTON_EVENT_CLICK not in callback_calls
        
        # Wait past double click timeout
        freertos.advance_time(350)
        
        # Still should not have single click
        assert esp.BUTTON_EVENT_CLICK not in callback_calls
        
        button_longpress.button_delete(button)
    
    def test_click_vs_long_press(self, mock_button_component):
        """Test that single click is not triggered when long press occurs"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Press and hold for long press
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)  # Past debounce
        
        # Hold for long press duration
        freertos.advance_time(1050)  # Past long press threshold
        
        # Should have long press
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        
        # Release
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Wait past double click timeout
        freertos.advance_time(350)
        
        # Should not have single click
        assert esp.BUTTON_EVENT_CLICK not in callback_calls
        assert esp.BUTTON_EVENT_DOUBLE_CLICK not in callback_calls
        
        button_longpress.button_delete(button)
    
    def test_multiple_single_clicks(self, mock_button_component):
        """Test multiple separate single clicks"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Perform 3 separate single clicks
        for i in range(3):
            callback_calls.clear()
            
            # Single click
            gpio.gpio_set_level(4, 1)
            freertos.advance_time(30)
            gpio.gpio_set_level(4, 0)
            freertos.advance_time(30)
            
            # Wait for click confirmation
            freertos.advance_time(350)
            
            # Should have click event
            assert esp.BUTTON_EVENT_CLICK in callback_calls
            assert esp.BUTTON_EVENT_DOUBLE_CLICK not in callback_calls
            assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
            
            # Wait between clicks
            freertos.advance_time(100)
        
        button_longpress.button_delete(button)
    
    def test_click_timing_precision(self, mock_button_component):
        """Test click timing with various double click timeouts"""
        double_click_times = [200, 300, 500, 800]
        
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
            print(f"DEBUG: Click confirmed with {double_click_time_ms}ms timeout")
            
            button_longpress.button_delete(button)
            
            # Reset for next iteration
            freertos.current_time_ms = 0
            freertos.timers = {}
            freertos.timer_id = 0
            button_longpress.button_instances = {}
            button_longpress.next_button_id = 1
    
    def test_click_active_low(self, mock_button_component):
        """Test single click with active low configuration"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=False,  # Active low
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Single click (active low)
        gpio.gpio_set_level(4, 0)  # Press (low for active low)
        freertos.advance_time(30)
        gpio.gpio_set_level(4, 1)  # Release (high for active low)
        freertos.advance_time(30)
        
        # Wait for click confirmation
        freertos.advance_time(350)
        
        # Should have click event
        assert esp.BUTTON_EVENT_CLICK in callback_calls
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        
        button_longpress.button_delete(button)
    
    def test_click_with_different_press_durations(self, mock_button_component):
        """Test single click with various press durations"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Test various press durations (all less than long press)
        press_durations = [50, 100, 200, 500, 800, 950]
        
        for duration in press_durations:
            callback_calls.clear()
            
            print(f"DEBUG: Testing click with {duration}ms press duration")
            
            # Press for specified duration
            gpio.gpio_set_level(4, 1)
            freertos.advance_time(30)
            freertos.advance_time(duration)
            gpio.gpio_set_level(4, 0)
            freertos.advance_time(30)
            
            # Wait for click confirmation
            freertos.advance_time(350)
            
            # Should have click event, not long press
            assert esp.BUTTON_EVENT_CLICK in callback_calls
            assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
            
            # Wait between tests
            freertos.advance_time(100)
        
        button_longpress.button_delete(button)
    
    def test_click_event_sequence(self, mock_button_component):
        """Test the complete event sequence for a single click"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Press
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        
        # Should have PRESSED event
        assert len(callback_calls) == 1
        assert callback_calls[0] == esp.BUTTON_EVENT_PRESSED
        
        # Release
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Should have RELEASED event
        assert len(callback_calls) == 2
        assert callback_calls[1] == esp.BUTTON_EVENT_RELEASED
        
        # Wait for click confirmation
        freertos.advance_time(350)
        
        # Should have CLICK event
        assert len(callback_calls) == 3
        assert callback_calls[2] == esp.BUTTON_EVENT_CLICK
        
        # Verify event order
        expected_sequence = [
            esp.BUTTON_EVENT_PRESSED,
            esp.BUTTON_EVENT_RELEASED,
            esp.BUTTON_EVENT_CLICK
        ]
        assert callback_calls == expected_sequence
        
        button_longpress.button_delete(button)
    
    def test_click_with_noise_immunity(self, mock_button_component):
        """Test single click detection with electrical noise"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=50,  # Longer debounce for noise testing
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        callback_calls.clear()
        
        # Simulate noisy press
        for i in range(5):
            gpio.gpio_set_level(4, i % 2)
            freertos.advance_time(5)
        
        # Stable press
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(60)  # Past debounce
        
        # Hold briefly
        freertos.advance_time(200)
        
        # Simulate noisy release
        for i in range(5):
            gpio.gpio_set_level(4, (i + 1) % 2)
            freertos.advance_time(5)
        
        # Stable release
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(60)  # Past debounce
        
        # Wait for click confirmation
        freertos.advance_time(350)
        
        # Should have clean single click despite noise
        assert esp.BUTTON_EVENT_CLICK in callback_calls
        assert callback_calls.count(esp.BUTTON_EVENT_PRESSED) == 1
        assert callback_calls.count(esp.BUTTON_EVENT_RELEASED) == 1
        assert callback_calls.count(esp.BUTTON_EVENT_CLICK) == 1
        
        button_longpress.button_delete(button)
    
    def test_click_boundary_conditions(self, mock_button_component):
        """Test click detection at timing boundaries"""
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Test 1: Release just before double click timeout
        callback_calls.clear()
        
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Wait just before timeout
        freertos.advance_time(299)  # 299ms < 300ms timeout
        assert esp.BUTTON_EVENT_CLICK not in callback_calls
        
        # Wait past timeout
        freertos.advance_time(2)  # Now 301ms total
        assert esp.BUTTON_EVENT_CLICK in callback_calls
        
        # Test 2: Second click exactly at timeout boundary
        callback_calls.clear()
        freertos.advance_time(100)  # Reset timing
        
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Second click exactly at timeout
        freertos.advance_time(300)  # Exactly at timeout
        gpio.gpio_set_level(4, 1)
        freertos.advance_time(30)
        gpio.gpio_set_level(4, 0)
        freertos.advance_time(30)
        
        # Should be treated as separate clicks, not double click
        # (depends on exact timing implementation)
        freertos.advance_time(350)
        
        # Should have at least one click event
        assert esp.BUTTON_EVENT_CLICK in callback_calls
        
        button_longpress.button_delete(button)
