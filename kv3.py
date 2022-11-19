import dataclasses
from pathlib import Path
from typing import Iterable, Protocol, Sequence, overload
from uuid import UUID
import enum

@dataclasses.dataclass(frozen=True)
class KV3Header:
    encoding: str = 'text'
    encoding_ver: str = 'e21c7f3c-8a33-41c5-9977-a76d3a32aa0d'
    format: str = 'generic'
    format_ver: str = '7412167c-06e9-4698-aff2-e63eb59037e7'
    _common = '<!-- kv3 encoding:%s:version{%s} format:%s:version{%s} -->'
    def __str__(self):
        return self._common % (self.encoding, self.encoding_ver, self.format, self.format_ver)

class str_multiline(str):
    pass

simple_types = None | bool | int | float | enum.Enum | str | str_multiline
container_types = list[simple_types] | dict[str, simple_types]
value_types = simple_types | container_types

def resource(path: Path) -> str:
    return flagged_value(path.as_posix().lower(), flag.resource)

@enum.global_enum
class flag(enum.Flag):
    resource = enum.auto()
    resourcename = enum.auto()
    panorama = enum.auto()
    soundevent = enum.auto()
    subclass = enum.auto()
    def __str__(self):
        return "+".join(val.name for val in self.__class__ if self.value & val)

@dataclasses.dataclass(slots=True)
class flagged_value:
    value: value_types
    flags: flag = flag(0)
    #def __str__(self):
    #    if not self.flags:
    #        return str(self.value)
    #    return f"{self.flags}:{self.value}"

value_types = value_types | flagged_value

class Dataclass(Protocol):
    # checking for this attribute is currently
    # the most reliable way to ascertain that something is a dataclass
    __dataclass_fields__: dict[str, dataclasses.Field]

class KV3File(dict):
    @overload
    def __init__(self):
        """Create an empty dict-based KV3File""" # TODO: null?
        ...
    @overload
    def __init__(self, **keywordargs):
        """Create a dict-based KV3File from keyword arguments"""
        ...
    @overload
    def __init__(self, kv3_dataclass: Dataclass):
        """Create a dict-based KV3File from a dataclass"""
        ...
    @overload
    def __init__(self, keyvaluepairs: Iterable[tuple[str, value_types]]):
        """Create a dict-based KV3File from a list of key-value pairs"""
        ...

    def __init__(self, *args, **kwargs):
        if len(args) and dataclasses.is_dataclass(args[0]):
            super().__init__(dataclasses.asdict(args[0]))
        else:
            super().__init__(*args, **kwargs)
        self.header = KV3Header()

    def __str__(self):
        kv3 = str(self.header) + '\n'
        def obj_serialize(obj, indent = 1, dictKey = False):
            preind = ('\t' * (indent-1))
            ind = ('\t' * indent)
            match obj:
                case flagged_value(value, flags):
                    if flags:
                        return f"{flags}:{obj_serialize(value)}"
                    return obj_serialize(value)
                case None:
                    return 'null'
                case False:
                    return 'false'
                case True:
                    return 'true'
                case str():
                    return '"' + obj + '"'
                case str_multiline():
                    return '"""' + obj + '"""'
                case list():
                    s = '['
                    if any(isinstance(item, dict) for item in obj):  # TODO: only non numbers
                        s = f'\n{preind}[\n'
                        for item in obj:
                            s += (obj_serialize(item, indent+1) + ',\n')
                        return s + preind + ']\n'

                    return f'[{", ".join((obj_serialize(item, indent+1) for item in obj))}]'
                case dict():
                    s = preind + '{\n'
                    if dictKey:
                        s = '\n' + s
                    for key, value in obj.items():
                        #if value == [] or value == "" or value == {}: continue
                        if not isinstance(key, str):
                            key = f'"{key}"'
                        s +=  ind + f"{key} = {obj_serialize(value, indent+1, dictKey=True)}\n"
                    return s + preind + '}'
                case _: # int, float, resource
                    # round off inaccurate dmx floats
                    if type(obj) == float:
                        obj = round(obj, 6)
                    return str(obj)

        kv3 += obj_serialize(self)

        return kv3

    def ToString(self):
        return self.__str__()

if __name__ == '__main__':
    import unittest
    class Test_KV3(unittest.TestCase):
        default_header = '<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->'
        def test_default_header(self):
            self.assertEqual(str(KV3Header()), self.default_header)

        def test_custom_header(self):
            header = KV3Header('text2', '123-123', 'generic2', '234-234')
            headertext = '<!-- kv3 encoding:text2:version{123-123} format:generic2:version{234-234} -->'
            self.assertEqual(str(header), headertext)
        
        def test_empty_instantiated_kv3file(self):
            self.assertEqual(
                KV3File().ToString(),
                self.default_header + "\n{\n}"
            )

        def test_kwargs_instantiated_kv3file(self):
            expect_text = self.default_header + '\n{'+\
                '\n\ta = "asd asd"'+\
                '\n\tb = \n\t{\n\t\tinner_b = 3\n\t}'+\
                '\n\tc = ["listed_text1", "listed_text2"]\n}'
            self.assertEqual(
                KV3File(
                    a='asd asd',
                    b={"inner_b":3},
                    c=["listed_text1", "listed_text2"]
                ).ToString(),
                expect_text
            )

        def test_dataclass_instantiated_kv3file(self):
            @dataclasses.dataclass
            class MyKV3Format:
                a: str = 'asd asd'
                b: dict = dataclasses.field(default_factory=lambda: {"inner_b":3})
            self.assertEqual(
                KV3File(MyKV3Format()).ToString(),
                self.default_header + '\n{'+\
                    '\n\ta = "asd asd"'+\
                    '\n\tb = \n\t{\n\t\tinner_b = 3\n\t}\n}'
            )
        
        def test_dict_instantiated_kv3file(self):
            self.assertEqual(
                KV3File({
                    'a': 'asd asd',
                    'b': {"inner_b":3},
                    'c': ["listed_text1", "listed_text2"]
                }).ToString(),
                self.default_header + '\n{'+\
                    '\n\ta = "asd asd"'+\
                    '\n\tb = \n\t{\n\t\tinner_b = 3\n\t}'+\
                    '\n\tc = ["listed_text1", "listed_text2"]\n}'
            )
        
        def test_keyvaluepairs_kv3file(self):
            self.assertEqual(
                KV3File([('a', 'asd asd'), ('b', {'inner_b':3})]).ToString(),
                self.default_header + '\n{'+\
                    '\n\ta = "asd asd"'+\
                    '\n\tb = \n\t{\n\t\tinner_b = 3\n\t}\n}'
            )

    unittest.main()
