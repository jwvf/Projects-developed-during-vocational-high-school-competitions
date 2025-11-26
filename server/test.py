import Communication
import random

rw = input("读/写,r/w:")
test_len = input("测试次数:")

if rw == "r":
    for _ in range(0,int(test_len)):
        print(Communication.read_var(int(random.uniform(0,100))))

if rw == "w":
    max_len = input("数据最大值:")
    for _ in range(0,int(test_len)):
        Communication.write_var(int(random.uniform(0,100)),int(random.uniform(0,10000)))

