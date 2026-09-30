"""Small example functions used by the test suite."""


def hello_world(name, company):
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    if not isinstance(company, str):
        raise TypeError("company must be a string")
    return f"Hello {name} and hello everyone at {company}"


def print_string(text):
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    print(text)


def print_favourite_number(number, name):
    if not isinstance(number, int):
        raise TypeError("number must be an int")
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    print(f"{name}'s favourite number is {number}!")
