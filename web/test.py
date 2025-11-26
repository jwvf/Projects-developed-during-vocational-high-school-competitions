import Communication
import time

for i in range(0,4):
    Communication.write_var(i,1)
    time.sleep(5)