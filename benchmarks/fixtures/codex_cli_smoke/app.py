def add(a: int, b: int) -> int:
    return a + b


def format_total(items: list[int]) -> str:
    total = sum(items)
    return f"total={total}"
