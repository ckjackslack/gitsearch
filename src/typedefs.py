from typing import Callable, Union


ProcessFn = Callable[[object], str]
GroupKey = Union[str, ProcessFn]