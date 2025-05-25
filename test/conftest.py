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
            'period_ms': period_ticks * (1000 // self.tick_rate_hz),  # Convert ticks to ms
            'auto_reload': auto_reload,
            'timer_id': timer_id,
            'callback': callback,
            'running': False,
            'expiry_time': 0,
            'created_time': self.current_time_ms
        }
        self.timers[self.timer_id] = timer
        print(f"DEBUG: Timer created: {self.timer_id}, name: {name}, period: {timer['period_ms']}ms")
        return self.timer_id
    
    def xTimerStart(self, timer_id, block_time):
        """Start a timer"""
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            timer['running'] = True
            timer['expiry_time'] = self.current_time_ms + timer['period_ms']
            print(f"DEBUG: Timer {timer_id} ({timer['name']}) started, will expire at {timer['expiry_time']}ms")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerStart")
        return 0  # pdFAIL
    
    def xTimerStop(self, timer_id, block_time):
        """Stop a timer"""
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            timer['running'] = False
            print(f"DEBUG: Timer {timer_id} ({timer['name']}) stopped")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerStop")
        return 0  # pdFAIL
    
    def xTimerDelete(self, timer_id, block_time):
        """Delete a timer"""
        if timer_id in self.timers:
            timer_name = self.timers[timer_id]['name']
            del self.timers[timer_id]
            print(f"DEBUG: Timer {timer_id} ({timer_name}) deleted")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerDelete")
        return 0  # pdFAIL
    
    def xTimerReset(self, timer_id, block_time):
        """Reset a timer"""
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            timer['expiry_time'] = self.current_time_ms + timer['period_ms']
            timer['running'] = True
            print(f"DEBUG: Timer {timer_id} ({timer['name']}) reset, will expire at {timer['expiry_time']}ms")
            return 1  # pdPASS
        print(f"DEBUG: Timer {timer_id} not found in xTimerReset")
        return 0  # pdFAIL
    
    def xTimerResetFromISR(self, timer_id, higher_priority_task_woken):
        """Reset a timer from ISR"""
        result = self.xTimerReset(timer_id, 0)
        if result and higher_priority_task_woken:
            # Simulate setting the higher priority task woken flag
            try:
                higher_priority_task_woken.contents = ctypes.c_int(1)
            except:
                pass
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
        return self.current_time_ms * self.tick_rate_hz // 1000  # Convert ms to ticks
    
    def advance_time(self, ms):
        """Advance time and process timers"""
        if ms <= 0:
            return
            
        print(f"DEBUG: Advancing time by {ms}ms from {self.current_time_ms}ms to {self.current_time_ms + ms}ms")
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
                
                print(f"DEBUG: Timer {next_timer} ({timer['name']}) expired at {self.current_time_ms}ms")
                
                # Stop the timer (one-shot behavior)
                timer['running'] = False
                
                # Handle auto-reload
                if timer['auto_reload']:
                    timer['expiry_time'] = self.current_time_ms + timer['period_ms']
                    timer['running'] = True
                    print(f"DEBUG: Timer {next_timer} auto-reloaded, next expiry: {timer['expiry_time']}ms")
                
                # Call the callback
                if timer['callback']:
                    print(f"DEBUG: Calling callback for timer {next_timer}")
                    try:
                        timer['callback'](next_timer)
                    except Exception as e:
                        print(f"DEBUG: Error in timer callback: {e}")
                else:
                    print(f"DEBUG: No callback for timer {next_timer}")
            else:
                # No more timers to process, advance to target time
                self.current_time_ms = target_time
    
    def get_running_timers(self):
        """Get list of currently running timers (for debugging)"""
        running = []
        for timer_id, timer in self.timers.items():
            if timer['running']:
                running.append({
                    'id': timer_id,
                    'name': timer['name'],
                    'expiry_time': timer['expiry_time'],
                    'time_remaining': max(0, timer['expiry_time'] - self.current_time_ms)
                })
        return running

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
                print(f"DEBUG: Configured GPIO {pin}, pull_up: {config.pull_up_en}, pull_down: {config.pull_down_en}, initial_level: {initial_level}")
            pin_bit_mask >>= 1
            pin += 1
        
        return esp.ESP_OK
    
    def gpio_get_level(self, gpio_num):
        """Get the level of a GPIO pin"""
        if gpio_num in self.pins:
            level = self.pins[gpio_num]['level']
            print(f"DEBUG: GPIO {gpio_num} level read: {level}")
            return level
        print(f"DEBUG: GPIO {gpio_num} not configured, returning 0")
        return 0
    
    def gpio_set_level(self, gpio_num, level):
        """Set the level of a GPIO pin (simulates external button press/release)"""
        if gpio_num in self.pins:
            old_level = self.pins[gpio_num]['level']
            self.pins[gpio_num]['level'] = level
            print(f"DEBUG: Setting GPIO {gpio_num} from {old_level} to {level}")
            
            # Trigger ISR if level changed and there's a handler
            if old_level != level and gpio_num in self.isr_handlers:
                print(f"DEBUG: Level changed, triggering ISR for GPIO {gpio_num}")
                try:
                    self.isr_handlers[gpio_num](self.isr_args[gpio_num])
                except Exception as e:
                    print(f"DEBUG: Error in ISR handler: {e}")
            else:
                if old_level == level:
                    print(f"DEBUG: Level didn't change, not triggering ISR")
                elif gpio_num not in self.isr_handlers:
                    print(f"DEBUG: No ISR handler for GPIO {gpio_num}")
            
            return esp.ESP_OK
        print(f"DEBUG: GPIO {gpio_num} not configured in gpio_set_level")
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
        
        if not self.isr_service_installed:
            print(f"DEBUG: ISR service not installed")
            return esp.ESP_ERR_INVALID_STATE
        
        self.isr_handlers[gpio_num] = isr_handler
        self.isr_args[gpio_num] = args
        print(f"DEBUG: ISR handler added for GPIO {gpio_num}")
        return esp.ESP_OK
    
    def gpio_isr_handler_remove(self, gpio_num):
        """Remove an ISR handler for a GPIO pin"""
        if gpio_num in self.isr_handlers:
            del self.isr_handlers[gpio_num]
            if gpio_num in self.isr_args:
                del self.isr_args[gpio_num]
            print(f"DEBUG: ISR handler removed for GPIO {gpio_num}")
            return esp.ESP_OK
        print(f"DEBUG: No ISR handler for GPIO {gpio_num}")
        return esp.ESP_ERR_INVALID_ARG
    
    def reset(self):
        """Reset GPIO state"""
        self.pins = {}
        self.isr_handlers = {}
        self.isr_args = {}
        self.isr_service_installed = False

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
    
    # Button states - соответствуют C реализации
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
