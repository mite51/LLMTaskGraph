import importlib
import json
from typing import Any, Dict, Type, TypeVar, List
from pxr import Usd, Sdf
import datetime

T = TypeVar('T', bound='ISerializable')

class SerializationError(Exception):
    """Custom exception for serialization errors"""
    pass

class ISerializable:
    _class_registry = {}
    _exclude_from_json: List[str] = []
    _exclude_from_properties: List[str] = []
    _readonly_properties: List[str] = []
    _exclude_from_usd: List[str] = []

    @classmethod
    def register_class(cls):
        cls._class_registry[f"{cls.__module__}.{cls.__name__}"] = cls

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.register_class()

    def get_properties(self) -> Dict[str, Any]:
        return {
            key: value for key, value in self.__dict__.items()
            if not key.startswith('_') and key not in self._exclude_from_properties
        }
    
    def is_property_readonly(self, property_name) -> bool:
        return property_name in self._readonly_properties
    
    def set_property(self, name: str, value: Any):  
        if name not in self._exclude_from_properties:  
            setattr(self, name, value)
    
    @classmethod
    def post_deserialize(self):
        pass

    def to_dict(self) -> Dict[str, Any]:
        data = {
            key: self._serialize_value(value) for key, value in self.__dict__.items()
            if not key.startswith('_') and key not in self._exclude_from_json
        }
        data['__type__'] = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return data

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        if '__type__' in data:
            class_type = cls._get_class(data['__type__'])
            if not issubclass(class_type, cls):
                raise TypeError(f"Class {data['__type__']} is not a subclass of {cls.__name__}")
            instance = class_type()
        else:
            instance = cls()
        
        for name, value in data.items():
            if name != '__type__' and not name.startswith('_') and name not in cls._exclude_from_json:
                setattr(instance, name, cls._deserialize_value(value))

        instance.post_deserialize()

        return instance

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=self._json_default)

    @classmethod
    def from_json_file(cls: Type[T], filepath: str) -> T:
        try:
            with open(filepath, 'r') as f:
                json_data = json.load(f)
                return cls.from_dict(json_data)
        except Exception as e:
            print(f"from_json_file failed to read {filepath}: {e}")
        return None

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_usd(self, stage: Usd.Stage, path: str) -> Usd.Prim:
        prim = stage.DefinePrim(path)
        for name, value in self.__dict__.items():
            if not name.startswith('_') and name not in self._exclude_from_usd:
                try:
                    self._set_usd_attribute(prim, name, value)
                except SerializationError as e:
                    print(f"Warning: {e}")
                except Exception as e:
                    print(f"Unexpected error serializing {name}: {e}")
        return prim

    @classmethod
    def from_usd(cls: Type[T], prim: Usd.Prim) -> T:
        instance = cls.__new__(cls)
        for attr in prim.GetAttributes():
            name = attr.GetName()
            if not name.startswith('_') and name not in cls._exclude_from_usd:
                value = cls._get_usd_attribute(attr)
                setattr(instance, name, value)
        return instance

    @classmethod
    def _get_class(cls, full_class_name: str) -> Type:
        if full_class_name in cls._class_registry:
            return cls._class_registry[full_class_name]
        
        module_name, class_name = full_class_name.rsplit('.', 1)
        try:
            module = importlib.import_module(module_name)
            class_type = getattr(module, class_name)
            cls._class_registry[full_class_name] = class_type  # Cache the class for future use
            return class_type
        except (ImportError, AttributeError):
            raise TypeError(f"Class {full_class_name} not found")

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if isinstance(value, ISerializable):
            return value.to_dict()
        elif isinstance(value, list):
            return [ISerializable._serialize_value(item) for item in value]
        elif isinstance(value, datetime.datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _deserialize_value(value: Any) -> Any:
        if isinstance(value, dict) and '__type__' in value:
            class_type = ISerializable._get_class(value['__type__'])
            if issubclass(class_type, ISerializable):
                return class_type.from_dict(value)
        elif isinstance(value, list):
            return [ISerializable._deserialize_value(item) for item in value]
        elif isinstance(value, str):
            # TODO: There has to be a better way to do this
            # Check if this is an ISO formatted datetime string
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, ISerializable):
            return obj.to_dict()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    def _set_usd_attribute(self, prim: Usd.Prim, name: str, value: Any):
        try:
            if isinstance(value, ISerializable):
                child_prim = prim.GetStage().DefinePrim(f"{prim.GetPath()}/{name}")
                value.to_usd(prim.GetStage(), str(child_prim.GetPath()))
            elif isinstance(value, list):
                if all(isinstance(item, ISerializable) for item in value):
                    for i, item in enumerate(value):
                        child_prim = prim.GetStage().DefinePrim(f"{prim.GetPath()}/{name}_{i}")
                        item.to_usd(prim.GetStage(), str(child_prim.GetPath()))
                else:
                    attr = prim.CreateAttribute(name, self._get_usd_type(value))
                    attr.Set(value)
            elif isinstance(value, datetime.datetime):
                attr = prim.CreateAttribute(name, Sdf.ValueTypeNames.String)
                attr.Set(value.isoformat())
            elif value is None:
                # Skip None values
                return
            else:
                attr = prim.CreateAttribute(name, self._get_usd_type(value))
                attr.Set(value)
        except Exception as e:
            print(f"Error serializing property {name} = {value} in {self.__class__.__name__}: {str(e)}")
            raise SerializationError(f"Error serializing property {name} = {value} in {self.__class__.__name__}: {str(e)}")

    @staticmethod
    def _get_usd_type(value: Any) -> Sdf.ValueTypeNames:
        if isinstance(value, bool):
            return Sdf.ValueTypeNames.Bool
        elif isinstance(value, int):
            return Sdf.ValueTypeNames.Int
        elif isinstance(value, float):
            return Sdf.ValueTypeNames.Double
        elif isinstance(value, str):
            return Sdf.ValueTypeNames.String
        elif isinstance(value, datetime.datetime):
            return Sdf.ValueTypeNames.String
        elif isinstance(value, list):
            if all(isinstance(item, (int, float)) for item in value):
                return Sdf.ValueTypeNames.DoubleArray
            elif all(isinstance(item, str) for item in value):
                return Sdf.ValueTypeNames.StringArray
            else:
                return Sdf.ValueTypeNames.TokenArray
        elif value is None:
            return Sdf.ValueTypeNames.Token  # Use Token for None values
        else:
            raise SerializationError(f"Unsupported type for USD serialization: {type(value)}")

    @classmethod
    def _get_usd_attribute(cls, attr: Usd.Attribute) -> Any:
        value = attr.Get()
        if isinstance(value, Usd.Prim):
            return cls.from_usd(value)
        elif isinstance(value, Sdf.PathListOp):
            return [cls._get_usd_attribute(attr.GetStage().GetPrimAtPath(path)) for path in value.explicitItems]
        elif attr.GetTypeName() == Sdf.ValueTypeNames.String:
            # TODO: There has to be a better way to do this
            # Check if this is an ISO formatted datetime string
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                return value
        return value