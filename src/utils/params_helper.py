from dataclasses import dataclass, fields, is_dataclass, MISSING, Field
from typing import Any, Dict, Type, get_origin, get_args, Union, List, Tuple
from functools import lru_cache


class ParamsHelper:
    """
    辅助类：递归构造 dataclass params 实例，带缓存优化
    """

    # 缓存 dataclass 字段信息 (cls -> List[Field])
    @classmethod
    @lru_cache(maxsize=None)
    def _get_fields(cls, dc_cls: Type) -> Tuple[Field, ...]:
        if not is_dataclass(dc_cls):
            raise TypeError(f"{dc_cls} 必须是 dataclass")
        return fields(dc_cls)

    @classmethod
    def build_params(cls, params_cls: Type, source: Dict[str, Any]):
        """递归构造 dataclass 实例"""
        kwargs = {}
        for f in cls._get_fields(params_cls):
            if f.name in source:
                raw = source[f.name]
                kwargs[f.name] = cls._coerce(f.type, raw)
            else:
                # 缺失时交给 dataclass 默认值处理
                if f.default is not MISSING or f.default_factory is not MISSING:
                    continue
        return params_cls(**kwargs)

    @classmethod
    def _coerce(cls, typ: Any, value: Any):
        if value is None:
            return None

        # dataclass
        if is_dataclass(typ):
            if isinstance(value, typ):
                return value
            if isinstance(value, dict):
                return cls.build_params(typ, value)
            raise TypeError(f"不能把 {type(value)} 转为 {typ}")

        origin = get_origin(typ)

        # list
        if origin in (list, List):
            (elem_type,) = get_args(typ) or (Any,)
            return [cls._coerce(elem_type, v) for v in value]

        # dict
        if origin is dict:
            key_t, val_t = get_args(typ) or (Any, Any)
            return {cls._coerce(key_t, k): cls._coerce(val_t, v) for k, v in value.items()}

        # Union / Optional
        if origin is Union:
            for candidate in get_args(typ):
                try:
                    return cls._coerce(candidate, value)
                except Exception:
                    pass
            return value

        # 基础类型
        try:
            return typ(value)
        except Exception:
            return value
