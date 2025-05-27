from toolbox.core import light_toolbox

@light_toolbox
def do_something(name):
    print(f"Doing something with {name}")
    return f"Processed {name}"

@light_toolbox
def do_failing_task():
    raise ValueError("Oops!")

do_something("test-file.txt")
do_failing_task()
