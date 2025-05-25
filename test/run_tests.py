#!/usr/bin/env python3
"""
Optimized test runner for ESP-IDF button component
"""
import sys
import os
import subprocess

def main():
    """Main test runner function"""
    print("=== ESP-IDF Button Component Test Suite ===")
    
    # Ensure we're in the test directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(test_dir)
    
    # Add test directory to Python path
    sys.path.insert(0, test_dir)
    
    try:
        # Test 1: Verify imports work
        print("\n1. Verifying imports...")
        from conftest import esp, gpio, freertos, ButtonConfig
        import button_longpress
        print("   ✓ All imports successful")
        
        # Test 2: Quick functionality test
        print("\n2. Quick functionality test...")
        
        # Reset state
        gpio.reset()
        freertos.timers = {}
        freertos.timer_id = 0
        freertos.current_time_ms = 0
        button_longpress.button_instances = {}
        button_longpress.next_button_id = 1
        
        # Install ISR service
        gpio.gpio_install_isr_service(0)
        
        # Create button
        import ctypes
        config = ButtonConfig(
            gpio_num=4,
            active_level=True,
            debounce_time_ms=20,
            long_press_time_ms=1000,
            double_click_time_ms=300,
            callback=None
        )
        
        button = button_longpress.button_create(ctypes.byref(config))
        assert button is not None, "Button creation failed"
        print(f"   ✓ Button created: {button}")
        
        # Test basic functions
        state = button_longpress.button_get_state(button)
        pressed = button_longpress.button_is_pressed(button)
        print(f"   ✓ State: {state}, Pressed: {pressed}")
        
        # Clean up
        result = button_longpress.button_delete(button)
        assert result == esp.ESP_OK, "Button deletion failed"
        print(f"   ✓ Button deleted successfully")
        
        # Test 3: Run pytest if available
        print("\n3. Running pytest...")
        
        # Run main test suite
        cmd = [sys.executable, "-m", "pytest", "test_button_longpress.py", "-v", "--tb=short"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✓ Main test suite PASSED")
            # Count passed tests
            lines = result.stdout.split('\n')
            for line in lines:
                if 'passed' in line and '::' not in line:
                    print(f"   {line.strip()}")
        else:
            print("   ✗ Main test suite FAILED")
            print("   Error output:")
            for line in result.stderr.split('\n')[:10]:  # Show first 10 lines
                if line.strip():
                    print(f"     {line}")
            return 1
        
        # Run click test suite
        cmd = [sys.executable, "-m", "pytest", "test_button_click.py", "-v", "--tb=short"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✓ Click test suite PASSED")
            # Count passed tests
            lines = result.stdout.split('\n')
            for line in lines:
                if 'passed' in line and '::' not in line:
                    print(f"   {line.strip()}")
        else:
            print("   ✗ Click test suite FAILED")
            print("   Error output:")
            for line in result.stderr.split('\n')[:10]:  # Show first 10 lines
                if line.strip():
                    print(f"     {line}")
            return 1
        
        print("\n=== ALL TESTS PASSED ===")
        print("✓ Test suite is working correctly!")
        return 0
        
    except Exception as e:
        print(f"\n=== TEST FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
