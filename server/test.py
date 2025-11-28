import Communication
import random

rw = int(input("读/写,r/w:"))
var = int(input("地址:"))
num = int(input("测试次数:"))
test_max = int(input("测试上限"))
test_min = int(input("测试下限"))

if rw == "r":
    for i in range(0,num):
        Communication.read_var(random.uniform())