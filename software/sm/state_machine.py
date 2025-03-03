import time
from array import array
from machine import Pin
from rp2 import PIO, asm_pio, StateMachine
 
DELAY = 14 #calibrate between 10 and 31 max

class SM_16bits():
    ''' this state machine is listening to FIFO and map 16bits word to 16 pins output
        Pin 2*i is for motor i direction control
        Pin 2*i+1 is for motor i step control
        1st 16bit word is to push a step up/down on motor based on direction & step
        2nd 16bit word is to push down steps on all motors, same direction than 1st 16bit word.
        a DELAY occurs between 2 16bit word, it can be updated to low speed, medium speed, high speed.
    '''
    
    def __init__(self, freq: int=400_000) -> None:
        self._sm = StateMachine(0, self._fifo_read, freq=freq, out_base=Pin(0))
        # irq call for testing: print pins output.
        self._sm.irq(lambda sm :print(f'Pins out={[Pin(x).value() for x in range(16)]}') )
        self.start()	# Starts the state machine
        
    @asm_pio(out_init=[PIO.OUT_LOW]*16,
        autopull=True, out_shiftdir=PIO.SHIFT_RIGHT,
        fifo_join=PIO.JOIN_TX,
    )
    def _fifo_read(DELAY=DELAY) -> None:
        pull()						# Stall here if there is no TX data
        wrap_target()				# principal loop
        set(y,1)					# count for 2 jumps						1 cycle
        label("word_16b")
        out(pins,16)				# Shift 16 bits from OSR to PINS		1 cycle
        #irq(rel(0))				# call IRQ								1 cycle, remove comment for testing
        set(x, DELAY)	    		# count for delay						1 cycle
        label("delay")				
        nop()					[29] 
        jmp(x_dec, "delay")			# do nothing 10 * (30+1)				310 cycles
        jmp(y_dec, "word_16b")		# 2 * ((310+1+1+1) + 1)=				2 * 314 cycles
        wrap()						#										1+ 2*314 +1 = 630 cycles
    

    
    def start(self) -> None:
        self._sm.active(1)	# Starts the state machine
        print('State machine started, listening to FIFO.')
        
    def stop(self) -> None:
        self._sm.active(0)	# Stops the state machine
        print('State machine stopped.')
        
    def put(self, ar:array) -> None:
        #print(f'Words sent: {ar}')
        self._sm.put(ar)
    
    def test(self) -> None:
        ''' set freq to 3_000 instead of 400_000
            remove comment tag # line 34, so that irq(rel(0)) is active.
            this test will print on screen pins output based on bellow array send to the sm
        '''
        ar = array("I", [1, 0, 1, 1, 1+(1<<16), 0b10, 0b10+(1<<17), 0b11, 0b11+(1<<18), (1<<16)-1, 0b1110000000000011+(1<<31)])    
        self.put(ar)		#stall here if FIFO is full
        time.sleep(1)
        self.put(ar)		#stall here if FIFO is full
        time.sleep(1)
        
if __name__ == '__main__':
    sm = SM_16bits(freq=3_000)
    sm.test()
    
    