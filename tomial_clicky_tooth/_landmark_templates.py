import io
import operator
import re

import strictyaml
from pangolin import JawType, tooth_kinds


class LandmarksContext(dict):
    """A dict subclass containing information about a part of the mouth for
    which a template should be evaluated.

    As an example, a rule (which is just a string) may contain the sub-string
    '(S)' which should be replaced with either 'left' or 'right'. This object
    both holds the value (either left or right) and performs the substitution::

        from pangolin import JawType

        # Create a context signifying the upper left quadrant of a mouth.
        context = LandmarksContext(JawType(arch_type="U"), side="L")

    ::

        >> context("The (A) (S) canine")
        "The upper left canine"
        >> context("The (a)(s)3")
        "The UL3"

    """
    def __init__(self, jaw_type: JawType, side):
        super().__init__()
        self.jaw_type = jaw_type
        self.arch_type = jaw_type.arch_type
        self.side = side
        self.primary = jaw_type.primary

        self["a"] = jaw_type.arch_type
        self["A"] = "upper" if jaw_type.arch_type == "U" else "lower"
        self["s"] = side
        self["S"] = "left" if side == "L" else "right"

        self._tag_re = re.compile(r"\(([" + "".join(self) + r"])\)")

    def __call__(self, rule: str):
        out = self._tag_re.sub(lambda m: self[m[1]], rule)
        match = re.search(r"\(([^)]+)\)", out)
        if match:
            return [(out[:match.start()] + str(i) + out[match.end():])
                    for i in self._sequence(match[1])]
        else:
            out = [out]
        return [i[0].upper() + i[1:] if i[0].islower() else i for i in out]

    def _sequence(self, text: str):
        """Expand number ranges (e.g. 1-3) and sequences (e.g. 1,3,4) to an
        iterable of tooth numbers (for adult teeth) or tooth letters for
        deciduous teeth)."""
        out = self.__sequence(text)
        if self.primary:
            out = (chr(0x40 + i) for i in out)
        return out

    def __sequence(self, text: str):
        for chunk in re.split(" *, *", text):
            match = re.fullmatch(r"(\d+)?-(\d+)?", chunk)
            if match:
                yield from range(
                    int(match[1] or 1),
                    int(match[2] or len(tooth_kinds(self.jaw_type))) + 1)
            else:
                yield int(chunk)


_scope_keys = {
    "adult": operator.methodcaller("with_", primary=False),
    "primary": operator.methodcaller("with_", primary=True),
    "upper": operator.methodcaller("with_", arch_type="U"),
    "lower": operator.methodcaller("with_", arch_type="L"),
    "any": operator.methodcaller("with_"),
}


def expand_scope_modifiers(template):
    return list(_expand_scope_modifiers(template))


def _expand_scope_modifiers(template, jaw_type=JawType(primary="*"), *path):
    if isinstance(template, dict):
        for (key, sub_template) in template.items():
            if key in ("name", "description"):
                continue
            try:
                yield from _expand_scope_modifiers(
                    sub_template, _scope_keys[key](jaw_type), *path, key)
            except KeyError:
                raise InvalidKey(key, path, _scope_keys) from None

    elif isinstance(template, list):
        yield jaw_type, template

    else:
        raise ParseError(f"Value at {'->'.join(path)} should be a list of "
                         f"landmarks - not a {type(template).__name__}.")


class LandmarksTemplate:
    """A generator for dental feature names.

    This object provides a declarative way of listing landmarks optionally
    capable of exploiting symmetry - be that symmetry between the upper and
    lower jaw, the left and right sides of an arch, adult/primary teeth,
    identical features repeated across ranges of teeth, or any combination of
    the above.

    """
    def __init__(self, template):
        self.template = template
        self.rules = expand_scope_modifiers(template)

    @classmethod
    def from_file(cls, file):
        """Create from a yaml file."""
        if isinstance(file, io.IOBase):
            return cls(strictyaml.load(file.read()).data)
        with open(file, "r", encoding="utf-8") as f:
            return cls.from_file(f)

    def evaluate(self, jaw_type: JawType):
        """Generate the landmark names for a given jaw type."""
        for (_jaw_type, rules) in self.rules:
            if _jaw_type.match(jaw_type, strict=True):
                break
        else:
            raise LandmarksUndefined(jaw_type)

        symmetric, asymmetric = [], []
        for rule in rules:
            (symmetric if "(s)" in rule else asymmetric).append(rule)
        landmarks = []

        for i in map(LandmarksContext(jaw_type, "L"), symmetric[::-1]):
            landmarks += i[::-1]
        for i in map(LandmarksContext(jaw_type, None), asymmetric):
            landmarks += i
        for i in map(LandmarksContext(jaw_type, "R"), symmetric):
            landmarks += i

        return landmarks


class ParseError(Exception):
    pass


class InvalidKey(ParseError):
    def __init__(self, key, path, valid):
        self.key = key
        self.path = path
        self.valid = valid

    def __str__(self):
        valid = ", ".join(f"'{i}'" for i in self.valid)
        if self.path:
            at = f" (located at {'->'.join((*self.path, self.key))})"
        else:
            at = ""
        return f"'{self.key}'{at} is not a valid key. " \
               f"Each key must be one of {valid}."


class LandmarksUndefined(Exception):
    def __init__(self, jaw_type):
        self.jaw_type = jaw_type

    def __str__(self):
        return f"No landmarks defined for jaw_type {self.jaw_type}"
