from enum import Enum
from typing import Union, List
from pydantic import BaseModel

class Operator(str, Enum):
    equals = "equals"
    not_equal = "not_equal"
    greater_equal = "greater_equal"
    greater_than = "greater_than"
    less_equal = "less_equal"
    less_than = "less_than"
    between = "between"
    in_ = "in"
    starts_with = "starts_with"

class Value(BaseModel):
    operator: Operator
    value: Union[str, int, float, List[Union[str, int]]]

class Filter(BaseModel):
    key: str
    value: Value
