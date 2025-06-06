from my_toolbox  import light_toolbox
import time

@light_toolbox
def do_something(name):
    time.sleep(0.2)
    print(f"Doing something with {name}")
    return f"Processed {name}"

@light_toolbox
def do_failing_task():
    raise ValueError("Oops!")

do_something("test-file.txt")
do_failing_task()
