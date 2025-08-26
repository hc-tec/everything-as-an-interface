import pytest
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Union
from src.utils.params_helper import ParamsHelper


# ====== 测试用 dataclass 定义 ======

@dataclass
class ChildParams:
    x: int
    y: str = "default"


@dataclass
class ParentParams:
    a: int
    b: str
    child: ChildParams
    tags: List[str] = field(default_factory=list)
    mapping: Dict[str, int] = field(default_factory=dict)
    optional_val: Optional[int] = None
    union_val: Union[int, str, None] = None


# ====== 单元测试 ======

def test_basic_types():
    params = ParamsHelper.build_params(ChildParams, {"x": "123", "y": "hello", "z": 1})
    assert isinstance(params, ChildParams)
    assert params.x == 123  # 转换成 int
    assert params.y == "hello"


def test_nested_dataclass():
    data = {
        "a": 1,
        "b": "test",
        "child": {"x": "42"},
    }
    params = ParamsHelper.build_params(ParentParams, data)
    assert isinstance(params.child, ChildParams)
    assert params.child.x == 42
    assert params.child.y == "default"  # 使用默认值


def test_list_and_dict():
    data = {
        "a": 1,
        "b": "bval",
        "child": {"x": 7},
        "tags": ["one", "two"],
        "mapping": {"k1": "10", "k2": 20},
    }
    params = ParamsHelper.build_params(ParentParams, data)
    assert params.tags == ["one", "two"]
    assert params.mapping == {"k1": 10, "k2": 20}  # 值强制转 int


def test_optional_and_union():
    data = {
        "a": 1,
        "b": "bval",
        "child": {"x": 5},
        "optional_val": "123",
        "union_val": "hello",
    }
    params = ParamsHelper.build_params(ParentParams, data)
    assert params.optional_val == 123
    assert params.union_val == "hello"

    data2 = {
        "a": 2,
        "b": "bval",
        "child": {"x": 9},
        "union_val": 88,
    }
    params2 = ParamsHelper.build_params(ParentParams, data2)
    assert params2.union_val == 88


def test_default_values():
    data = {
        "a": 10,
        "b": "bbb",
        "child": {"x": 1},
    }
    params = ParamsHelper.build_params(ParentParams, data)
    assert params.tags == []  # 默认 factory
    assert params.mapping == {}  # 默认 factory
    assert params.optional_val is None


def test_invalid_type_error():
    data = {
        "a": 1,
        "b": "bval",
        "child": 123,  # 错误：应为 dict
    }
    with pytest.raises(TypeError):
        ParamsHelper.build_params(ParentParams, data)


def test_cache_behavior():
    # 触发 _get_fields 缓存
    fields1 = ParamsHelper._get_fields(ParentParams)
    fields2 = ParamsHelper._get_fields(ParentParams)
    assert fields1 is fields2  # lru_cache 生效（同一个对象）


