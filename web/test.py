import Communication
import time

def main():
    for i in range(0,100):
        Communication.write_var(i,1)
        print(f"已写入{i},1")
        time.sleep(2)
        Communication.write_var(i,0)
        print(f"已写入{i},0")
        time.sleep(2)

if __name__ == "__main__":
    main()