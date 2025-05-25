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
    return None

class TestButtonLongPress:
    """Test class for button_longpress component"""
    
    def setup_method(self):
        """Setup method called before each test"""
        # Clear the callback calls
        callback_calls.clear()
        
        # Reset mock state
        gpio.pins = {}
        gpio.isr_handlers = {}
        gpio.isr_args = {}
        gpio.isr_service_installed = False
        freertos.timers = {}
        freertos.timer_id = 0
        freertos.current_time_ms = 0
    
    def test_button_create_valid_config(self, mock_button_component, button_config):
        """Test button creation with valid configuration"""
        # Create button configuration with C-compatible callback
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=button_config['active_level'],
            debounce_time_ms=button_config['debounce_time_ms'],
            long_press_time_ms=button_config['long_press_time_ms'],
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        # Create button
        button = button_longpress.button_create(ctypes.byref(config))
        
        # Verify button was created
        assert button is not None
        
        # Verify GPIO was configured
        assert button_config['gpio_num'] in gpio.pins
        assert gpio.pins[button_config['gpio_num']]['mode'] == esp.GPIO_MODE_INPUT
        
        # Verify timers were created (now 3 timers including double click)
        assert len(freertos.timers) == 3
        
        # Clean up
        result = button_longpress.button_delete(button)
        assert result == esp.ESP_OK
    
    def test_button_create_invalid_gpio(self, mock_button_component, button_config):
        """Test button creation with invalid GPIO number"""
        # Create button configuration with invalid GPIO
        config = ButtonConfig(
            gpio_num=esp.GPIO_NUM_MAX + 1,  # Invalid GPIO number
            active_level=button_config['active_level'],
            debounce_time_ms=button_config['debounce_time_ms'],
            long_press_time_ms=button_config['long_press_time_ms'],
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        # Create button
        button = button_longpress.button_create(ctypes.byref(config))
        
        # Verify button was not created
        assert button is None
    
    def test_button_create_null_config(self, mock_button_component):
        """Test button creation with NULL configuration"""
        # Create button with NULL config
        button = button_longpress.button_create(None)
        
        # Verify button was not created
        assert button is None
    
    def test_button_delete_null_handle(self, mock_button_component):
        """Test button deletion with NULL handle"""
        # Delete button with NULL handle
        result = button_longpress.button_delete(None)
        
        # Verify error was returned
        assert result == esp.ESP_ERR_INVALID_ARG
    
    def test_button_press_active_high(self, mock_button_component, button_config):
        """Test button press detection with active high configuration"""
        # Create button configuration (active high)
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,  # Active high
            debounce_time_ms=button_config['debounce_time_ms'],
            long_press_time_ms=button_config['long_press_time_ms'],
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        # Create button
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Simulate button press (set GPIO high)
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance time past debounce period
        freertos.advance_time(button_config['debounce_time_ms'] + 10)
        
        # Verify callback was called with BUTTON_EVENT_PRESSED
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_PRESSED
        assert button_longpress.button_is_pressed(button) == True
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_long_press_callback_invocation(self, mock_button_component, button_config):
        """Test that long press callback is invoked after the configured time"""
        # Create button with specific long press time
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # Simulate button press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time to just before long press threshold
        freertos.advance_time(long_press_time_ms - 50)
        
        # Verify no LONG_PRESS event yet
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time past long press threshold
        freertos.advance_time(100)
        
        # Verify LONG_PRESS event was triggered
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        assert len(callback_calls) == 2
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_LONG_PRESS
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_short_press_no_long_press_callback(self, mock_button_component, button_config):
        """Test that short presses don't trigger the long press callback"""
        # Create button with specific long press time
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # Simulate button press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time but not enough for long press (half the long press time)
        freertos.advance_time(long_press_time_ms / 2)
        
        # Release button
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify RELEASED event was triggered but not LONG_PRESS
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        assert len(callback_calls) == 2
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_contact_bounce_handling(self, mock_button_component, button_config):
        """Test that contact bounce doesn't cause spurious callbacks"""
        # Create button with specific debounce time
        debounce_time_ms = 50
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=debounce_time_ms,
            long_press_time_ms=1000,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # Simulate contact bounce (rapidly toggle button state)
        for i in range(10):
            # Toggle button state
            gpio.gpio_set_level(button_config['gpio_num'], i % 2)
            # Advance time a small amount (less than debounce time)
            freertos.advance_time(5)
        
        # Verify no callbacks were triggered during bounce
        assert len(callback_calls) == 0
        
        # Set button to pressed state
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance time past debounce period
        freertos.advance_time(debounce_time_ms + 10)
        
        # Verify only one PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_varying_short_press_durations(self, mock_button_component, button_config):
        """Test different short press durations to ensure they don't trigger long press"""
        # Create button with specific long press time
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Test various short press durations
        short_press_durations = [100, 300, 500, long_press_time_ms - 50]
        
        for duration in short_press_durations:
            # Clear previous callbacks
            callback_calls.clear()
            
            # Simulate button press
            gpio.gpio_set_level(button_config['gpio_num'], 1)
            
            # Advance time past debounce period
            freertos.advance_time(30)
            
            # Verify PRESSED event was triggered
            assert esp.BUTTON_EVENT_PRESSED in callback_calls
            assert len(callback_calls) == 1
            
            # Advance time for the current duration
            freertos.advance_time(duration)
            
            # Release button
            gpio.gpio_set_level(button_config['gpio_num'], 0)
            
            # Advance time past debounce period
            freertos.advance_time(30)
            
            # Verify RELEASED event was triggered but not LONG_PRESS
            assert esp.BUTTON_EVENT_RELEASED in callback_calls
            assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
            assert len(callback_calls) == 2
            
            # Verify button state
            assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
            
            # Advance time past double click window to reset state
            freertos.advance_time(500)
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_press_release_before_long_press(self, mock_button_component, button_config):
        """Test pressing and releasing just before long press time elapses"""
        # Create button with specific long press time
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # Simulate button press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time to just before long press threshold
        freertos.advance_time(long_press_time_ms - 30)
        
        # Release button just before long press would trigger
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        
        # Advance time past debounce period
        freertos.advance_time(50)
        
        # Verify RELEASED event was triggered but not LONG_PRESS
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        assert len(callback_calls) == 2
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_active_low_long_press(self, mock_button_component, button_config):
        """Test long press detection with active low configuration"""
        # First, create the button with active low configuration
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=False,  # Active low
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Now the GPIO pin is configured, set it to released state (high for active low)
        gpio_num = button_config['gpio_num']
        gpio.gpio_set_level(gpio_num, 1)
        
        # Advance time past debounce period to register the release
        freertos.advance_time(30)
        
        # Clear any callbacks from the initial setup
        callback_calls.clear()
        
        # Simulate button press (set GPIO low for active low)
        gpio.gpio_set_level(gpio_num, 0)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time past long press threshold
        freertos.advance_time(long_press_time_ms + 50)
        
        # Verify LONG_PRESS event was triggered
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        assert len(callback_calls) == 2
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_LONG_PRESS
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_active_low_short_press(self, mock_button_component, button_config):
        """Test short press detection with active low configuration"""
        # First, create the button with active low configuration
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=False,  # Active low
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Now the GPIO pin is configured, set it to released state (high for active low)
        gpio_num = button_config['gpio_num']
        gpio.gpio_set_level(gpio_num, 1)
        
        # Advance time past debounce period to register the release
        freertos.advance_time(30)
        
        # Clear any callbacks from the initial setup
        callback_calls.clear()
        
        # Simulate button press (set GPIO low for active low)
        gpio.gpio_set_level(gpio_num, 0)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance time but not enough for long press
        freertos.advance_time(long_press_time_ms / 2)
        
        # Release button (set GPIO high for active low)
        gpio.gpio_set_level(gpio_num, 1)
        
        # Advance time past debounce period
        freertos.advance_time(30)
        
        # Verify RELEASED event was triggered but not LONG_PRESS
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        assert len(callback_calls) == 2
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_complex_bounce_scenario(self, mock_button_component, button_config):
        """Test a complex scenario with multiple bounces and press/release cycles"""
        # Create button with specific debounce and long press times
        debounce_time_ms = 50
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=debounce_time_ms,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=300,  # Add double click time
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # Scenario 1: Initial bounce, then stable press, then release before long press
        
        # Simulate initial contact bounce
        for i in range(10):
            gpio.gpio_set_level(button_config['gpio_num'], i % 2)
            freertos.advance_time(5)
        
        # Stable press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(debounce_time_ms + 10)
        
        # Verify PRESSED event was triggered once
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert callback_calls.count(esp.BUTTON_EVENT_PRESSED) == 1
        
        # Hold for a while but not long enough for long press
        freertos.advance_time(long_press_time_ms / 2)
        
        # Release with bounce
        for i in range(8):
            gpio.gpio_set_level(button_config['gpio_num'], (i + 1) % 2)
            freertos.advance_time(5)
        
        # Stable release
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(debounce_time_ms + 10)
        
        # Verify RELEASED event was triggered once and no LONG_PRESS
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert callback_calls.count(esp.BUTTON_EVENT_RELEASED) == 1
        assert esp.BUTTON_EVENT_LONG_PRESS not in callback_calls
        
        # Reset for next scenario
        callback_calls.clear()
        
        # Scenario 2: Press, bounce during long press threshold, then stable long press
        
        # Press with bounce
        for i in range(6):
            gpio.gpio_set_level(button_config['gpio_num'], i % 2)
            freertos.advance_time(5)
        
        # Stable press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(debounce_time_ms + 10)
        
        # Verify PRESSED event was triggered
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert len(callback_calls) == 1
        
        # Advance to near long press threshold
        freertos.advance_time(long_press_time_ms - 100)
        
        # Simulate some noise/bounce without fully releasing
        for i in range(4):
            # Toggle between high and slightly lower (but still considered high)
            level = 1 if i % 2 == 0 else 0
            gpio.gpio_set_level(button_config['gpio_num'], level)
            freertos.advance_time(10)
        
        # Ensure it's pressed
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        
        # Advance past long press threshold
        freertos.advance_time(150)
        
        # Verify LONG_PRESS event was triggered exactly once
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        assert callback_calls.count(esp.BUTTON_EVENT_LONG_PRESS) == 1
        assert len(callback_calls) == 2  # PRESSED and LONG_PRESS
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_double_click_detection(self, mock_button_component, button_config):
        """Test double click detection"""
        # Create button with specific double click time
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
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # First click - press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # First click - release
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Verify PRESSED and RELEASED events
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert len(callback_calls) == 2
        
        # Wait a short time (less than double click timeout)
        freertos.advance_time(double_click_time_ms / 2)
        
        # Second click - press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # Second click - release
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Verify DOUBLE_CLICK event was triggered
        assert esp.BUTTON_EVENT_DOUBLE_CLICK in callback_calls
        # Updated expectation: PRESSED, RELEASED, PRESSED, RELEASED, DOUBLE_CLICK
        assert len(callback_calls) == 5
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_DOUBLE_CLICK
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_double_click_timeout(self, mock_button_component, button_config):
        """Test that double click is not detected if second click comes too late"""
        # Create button with specific double click time
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
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # First click - press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # First click - release
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Verify PRESSED and RELEASED events
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert len(callback_calls) == 2
        
        # Wait longer than double click timeout
        freertos.advance_time(double_click_time_ms + 50)
        
        # Reset callback calls to make verification clearer
        callback_calls.clear()
        
        # Second click - press (too late to be a double click)
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # Second click - release
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Verify normal PRESSED and RELEASED events, but no DOUBLE_CLICK
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        assert esp.BUTTON_EVENT_DOUBLE_CLICK not in callback_calls
        assert len(callback_calls) == 2
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_IDLE
        
        # Clean up
        button_longpress.button_delete(button)
        
    def test_long_press_cancels_double_click(self, mock_button_component, button_config):
        """Test that a long press cancels double click detection"""
        # Create button with specific times
        double_click_time_ms = 300
        long_press_time_ms = 1000
        config = ButtonConfig(
            gpio_num=button_config['gpio_num'],
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=long_press_time_ms,
            double_click_time_ms=double_click_time_ms,
            callback=ctypes.cast(button_callback_func, ctypes.c_void_p)
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None
        
        # Clear any initial callbacks
        callback_calls.clear()
        
        # First click - press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # First click - release
        gpio.gpio_set_level(button_config['gpio_num'], 0)
        freertos.advance_time(30)  # Past debounce
        
        # Verify PRESSED and RELEASED events
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_RELEASED in callback_calls
        # Updated expectation: PRESSED, RELEASED
        assert len(callback_calls) == 2
        
        # Wait a short time (less than double click timeout)
        freertos.advance_time(double_click_time_ms / 2)
        
        # Second click - press but hold for long press
        gpio.gpio_set_level(button_config['gpio_num'], 1)
        freertos.advance_time(30)  # Past debounce
        
        # Hold for long press duration
        freertos.advance_time(long_press_time_ms + 50)
        
        # Verify PRESSED and LONG_PRESS events, but no DOUBLE_CLICK
        assert esp.BUTTON_EVENT_PRESSED in callback_calls
        assert esp.BUTTON_EVENT_LONG_PRESS in callback_calls
        assert esp.BUTTON_EVENT_DOUBLE_CLICK not in callback_calls
        assert len(callback_calls) == 4  # PRESSED, RELEASED, PRESSED, LONG_PRESS
        
        # Verify button state
        assert button_longpress.button_get_state(button) == esp.BUTTON_STATE_LONG_PRESS
        
        # Clean up
        button_longpress.button_delete(button)
