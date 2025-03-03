import time
from machine import Pin
from sm.state_machine import SM_16bits

class Motor():
    
    ACTION = {'move':1, 'stop':0}
    MODE = {'wake': 1, 'sleep': 0} # Overridden in child class.
    DIRECTION = {'forward': True, 'backward': False} # Overridden in child class.
    MICROSTEPS = {'full': 0b000, #default values for A4988
                  '1/2':  0b100, 
                  '1/4':  0b010, 
                  '1/8':  0b110, 
                  '1/16': 0b111, 
                  '1/32': None,
    } # Overridden in child class.
    
    def __init__(self, id: int, pin_sleep: int, sm: SM_16bits|None) -> None:    
        self.name = f'Motor {id}'
        self._sm = sm
        
        # pinout to raspberry pico
        self._pin_dir = id*2    # managed by sm
        self._pin_step = id*2+1 # managed by sm
        self._pin_sleep = Pin(pin_sleep, Pin.OUT) # NOT managed by sm
        self._pin_sleep.value(self.MODE['sleep'])
        print(f'Pinout motor {self.name}: DIR={self.pin_dir}, STEP={self.pin_step}, SLEEP={self.pin_sleep}.')
        self.sleep()
        
        # pinout microstep resolution
        self._pin_MS1 = Pin(19, Pin.OUT)
        self._pin_MS2 = Pin(20, Pin.OUT)
        self._pin_MS3 = Pin(21, Pin.OUT)
    
    @property
    def pin_dir(self) -> int:
        return self._pin_dir
    
    @property
    def pin_step(self) -> int:
        return self._pin_step
    
    @property
    def pin_sleep(self) -> Pin:
        return self._pin_sleep
    
    
    def set_microstep(self, ms: int) -> None:
        self._pin_MS1.value(ms & 0b100)
        self._pin_MS2.value(ms & 0b010)
        self._pin_MS3.value(ms & 0b001)
        print(f'microsteps: MS1:{self._pin_MS1.value()}, MS2:{self._pin_MS2.value()}, MS3:{self._pin_MS3.value()}')

    
    def sleep(self) -> None :
        print(f'{self.name} in sleep mode.')
        self.pin_sleep.value(self.MODE['sleep'])
        
    def wake(self) -> None :
        print(f'{self.name} wake up.')
        self.pin_sleep.value(self.MODE['wake'])

    def convert_step(self, dir: int, action: int) -> int:
        """Calculate 32b word to send to the SM 
            in order to move step in the direction dir.

        Args:
            dir (int): direction 0|1
            step (int): step to move 0|1

        Returns:
            int: 32b word to sent to the SM
        """
        word32b = ( (dir<<self.pin_dir) + (action<<self.pin_step)  # 1st 16b word: pull up pin step and set direction
                + (dir<<(16+self.pin_dir))                         # 2nd 16b word: pull down pin step, same direction
        )
        #print(f'word32b: {bin(word32b)}')
        return word32b        
    
    
    def test(self):
        """test wiring to driver without using sm"""
        pin_dir=Pin(self.pin_dir, Pin.OUT)
        pin_step=Pin(self.pin_step, Pin.OUT)
        self.wake()
        pin_dir.value(self.DIRECTION['forward'])   # direction forward
        for i in range(5): # slowly move 5 steps
            print('move 1 step')
            pin_step.value(self.ACTION['move'])
            time.sleep(0.5)
            pin_step.value(self.ACTION['stop'])
            time.sleep(0.5)
        print('Move 400 steps forward and backward, Ctrl-C to interrupt.')           
        forward=self.DIRECTION['forward']
        pin_dir.value(forward)
        try:
            while True:
                for i in range(400): # move 400 steps forwards
                    pin_step.value(self.ACTION['move'])
                    time.sleep(0.0015)
                    pin_step.value(self.ACTION['stop'])
                    time.sleep(0.001)
                time.sleep(0.5)
                forward = not forward
                pin_dir.value(forward)    # direction opposite
        except KeyboardInterrupt:
            self.sleep()

class A4988(Motor):
    
    MODE = {'wake': 0, 'sleep':1}
    MICROSTEPS = {'full': 0b000, 
                  '1/2':  0b100, 
                  '1/4':  0b010, 
                  '1/8':  0b110, 
                  '1/16': 0b111, 
                  '1/32': None,
    }    
    def __init__(self, id: int, pin_sleep: int, sm: SM_16bits) -> None:
        super().__init__(id, pin_sleep, sm)
        #self.set_microstep(self.MICROSTEPS['full'])
        

class TMC2208(Motor):
    
    MODE = {'wake': 0, 'sleep':1}
    MICROSTEPS = {'full': None, 
                  '1/2':  0b100, 
                  '1/4':  0b010, 
                  '1/8':  0b000, 
                  '1/16': 0b110, 
                  '1/32': None,
    }
    def __init__(self, id: int, pin_sleep: int, sm: SM_16bits) -> None:
        super().__init__(id, pin_sleep, sm)
        #self.set_microstep(self.MICROSTEPS['1/2'])


class TMC2209(Motor):
    
    MODE = {'wake': 1, 'sleep':0}
    def __init__(self, id: int, pin_sleep: int, sm: SM_16bits) -> None:
        super().__init__(id, pin_sleep, sm)


if __name__ == '__main__':
    motor=TMC2208(id=0, pin_sleep=18, sm=None)
    motor.test()
