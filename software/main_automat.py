import time
import re
import sys
import json

from array import array

from sm.state_machine import SM_16bits
from stepper.motor import A4988, TMC2208, TMC2209
     

class Seq():
    
    def __init__(self, gcode_seq: str) ->None:
        self.gcode_seq = gcode_seq
    
    def parse(self) -> dict|None:
        """parse gcode_seq into a full sequence to run
        seq is made in this order:
            - _a followed by 1 to move, or 0 to stop the motor
            - _s followed by number of steps to run 
            - _d followed by direction either 1(forward) or 0(backward)
            - _v speed factor to run at (0=highest speed)
            
        Args:
            gcode_seq (str): sequence to parse, example: a1s200d0v1

        Returns:
            dict: dictionary of sequence
        """
        pattern = r'^a([01])_s(\d+)_d([01])_v(\d+)$'
        match = re.match(pattern, self.gcode_seq)

        if match:
            groups = match.groups()
            return {
                'action': int(groups[0]),
                'step'  : int(groups[1]),
                'dir'   : int(groups[2]),
                'speed' : int(groups[3]),
            }
        else:
            print(f'ERROR: seq {self.gcode_seq} is not understood, should be a[0..1]_s*_d[0..1]_v*)')
            return None
    
    def test(self):
        self.gcode_seq='fake'
        print(self.parse())
        self.gcode_seq='a1_s400_d1_v2'
        print(self.parse())
        

class Automat():
    
    def __init__(self, gcode_file: str) -> None:
        
        self._driver, self._mode, self._freq_sm , self._gcode_seq = self.read_gcode(gcode_file)
        self._nb_motors = len([gcode for gcode in self._gcode_seq.values() if len(gcode)>0])
        print(f'Found {self._nb_motors} motor(s) to animate.')
        if self._nb_motors > 8:
            print('Maximum number of motors is 8.')
            self.exit()
        
        #start the state machine
        self._sm = SM_16bits(self._freq_sm)    
        
        #motor configuration
        self._motors: list[A4988|TMC2208|TMC2209]
        if self._driver=='A4988':
            self._motors = [A4988(id=i, pin_sleep=18, sm=self._sm) for i in range(self._nb_motors)]
        elif self._driver=='TMC2208':
            self._motors = [TMC2208(id=i, pin_sleep=18, sm=self._sm) for i in range(self._nb_motors)]
        elif self._driver=='TMC2209':
            self._motors = [TMC2209(id=i, pin_sleep=18, sm=self._sm) for i in range(self._nb_motors)]
        else:
            print('Error: driver should be A4988 or TMC2208 or TMC2209.')
            self.exit()

        
        self._seq16bits = array("I") #16bits words to sent to the sm   
        self._motors_len_seq={0:0, 1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0} # length of sequence to run for each motor 
        
        #setup sequence to run
        for i in range(self._nb_motors):
            gcodes = self._gcode_seq[str(i)]
            for gcode in gcodes:
                self.add_seq(id_motor=i, seq=Seq(gcode))
        
        if self._mode=='LOOP':
            self.animate_infinite_loop()
        elif self._mode=='ONE':
            self.animate()
        else:
            print('"MODE" should be "LOOP" or "ONE".')
            self.exit()
            
        
    def read_gcode(self, gcode_file:str) -> tuple:
        """read .gcode file located into /gcode
            set nb of motors, driver, microstepping, run mode and read sequences of gcode.
            run the animation
        Args:  file (str): gcode file to read
        Returns: tuple of driver(str), microstep(str), mode(str), freq_sm: int, gcode_seq: dict    
        """
        #read json gcode file
        try:
            with open(gcode_file, 'r') as file:
                data = json.load(file)
                #print(f'gcode read: {data}')
                driver, mode, freq_sm =  data['DRIVER'], data['MODE'], int(data['FREQ_SM'])
                gcode_seq =  data['GCODE_SEQ'] # gcode_seq[i] is the gcode of motor i
        except OSError:
            print(f'failed to read file {gcode_file}')
            self.exit()
        except KeyError:
            print('json file is not following the right template.')
            self.exit()
        
        return driver, mode, freq_sm, gcode_seq
                
        
    def wake_motors(self):
        for i in range(self._nb_motors):
            self._motors[i].wake()
            
    def sleep_motors(self):
        for i in range(self._nb_motors):
            self._motors[i].sleep()
            
    def set_microstep(self, ms_str: str) -> None:
        """set same microstepping on all motors

        Args:
            ms_str (str): 'full', '1/2', '1/4', '1/8', '1/16', '1/32'
        """
        print(f'Micostepping used: {ms_str}')
        ms = self._motors[0].MICROSTEPS[ms_str]
        for i  in range(self._nb_motors):
            self._motors[i].set_microstep(ms)
    
    def add_seq(self, id_motor: int, seq: Seq) -> None:
        """ Add a sequence  into self._seq to run the motor id_motor
            Args: seq (Seq): Sequence to add
        """
        dic_seq:dict|None = seq.parse()
        if dic_seq==None:
            self.exit()   
        #print(f'sequence added on motor {id_motor}: {dic_seq}')
        action, steps, dir, speed = dic_seq['action'], dic_seq['step'], dic_seq['dir'], dic_seq['speed']    
        steps = steps * (1+speed)
        
        #extend sequence if need be
        if steps + self._motors_len_seq[id_motor] > len(self._seq16bits): 
            for i in range(steps):
                self._seq16bits.append(0)
        
        #initialize direction & stop on all steps
        for i in range(steps):
            self._seq16bits[self._motors_len_seq[id_motor]+i] |= self._motors[id_motor].convert_step(
                dir=dir, 
                action=0
            )
        
        #set direction and action every "1+speed" steps. Other steps are stopped
        for i in range(0,steps,1+speed):
            self._seq16bits[self._motors_len_seq[id_motor]+i] |= self._motors[id_motor].convert_step(
                dir=dir,
                action=action
            )
        
        #extend _motors_len_seq of Motor id-motor
        self._motors_len_seq[id_motor] += steps
        
    
    def animate(self):
        self.wake_motors()
        print('Start animation.')        
        self._sm.put(self._seq16bits) 
        print('Animation complete.')        

        
    def animate_infinite_loop(self):
        self.wake_motors()
        print('Start animation.')        
        try:
            while True:
                self._sm.put(self._seq16bits) 
        except KeyboardInterrupt:
            pass
        print('Animation complete.')        
        self.exit()
    
    def exit(self):
        if hasattr(self, '_sm'):
            self._sm.stop()
        if hasattr(self, '_motors'):
            self.sleep_motors()
        print('Program stopped.')
        sys.exit(1)


appl = Automat(gcode_file='gcode/test_automat.json')
