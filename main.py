from my_toolbox import light_toolbox
import time
import random

@light_toolbox
def do_something(name):
    time.sleep(0.2)
    print(f"Doing something with {name}")
    return f"Processed {name}"

@light_toolbox
def do_failing_task():
    raise ValueError("Oops!")

@light_toolbox
def unreliable_api_call():
    print("Calling unreliable API...")
    if random.random() < 0.7:  # 70% chance to fail
        raise TimeoutError("API did not respond")
    return "API Success!"

if __name__ == "__main__":
    do_something("test-file.txt")
    
    try:
        do_failing_task()
    except Exception as e:
        print(f"Handled error from failing task: {e}")

    try:
        result = unreliable_api_call()
        print(f"Unreliable API result: {result}")
    except Exception as e:
        print(f"API call ultimately failed: {e}")
