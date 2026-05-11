"""Tool preset for testing NPU tool calling."""

system_instruction = "You are a helpful assistant with access to tools."


def get_weather(city: str) -> str:
    """Gets the current weather for a given city.

    Args:
        city: The name of the city to get weather for.

    Returns:
        A string describing the current weather.
    """
    return f"The weather in {city} is sunny, 22°C with light winds."


def calculate(expression: str) -> str:
    """Evaluates a mathematical expression.

    Args:
        expression: A mathematical expression to evaluate (e.g. '2 + 2').

    Returns:
        The result of the calculation as a string.
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error: {e}"


tools = [get_weather, calculate]
