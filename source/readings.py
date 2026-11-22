from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from errors import ValidationError
from identity import require_text


@dataclass(frozen=True, slots=True)
class Reading:
    name: str
    value: int | None

    def __post_init__(self) -> None:
        require_text(self.name, 'reading name')
        if self.value is not None and type(self.value) is not int:
            raise ValidationError('reading value must be an integer or null')

    def as_data(self) -> dict:
        return {'name': self.name, 'value': self.value}


def parse_reading(raw: object) -> Reading:
    if isinstance(raw, Reading):
        return raw
    if not isinstance(raw, Mapping) or raw.keys() != {'name', 'value'}:
        raise ValidationError('reading requires name and value fields')
    return Reading(raw['name'], raw['value'])


def parse_rows(raw: Iterable[object]) -> tuple[Reading, ...]:
    if isinstance(raw, (str, bytes, bytearray, Mapping, set, frozenset)):
        raise ValidationError('readings require an ordered sequence')
    try:
        iterator = iter(raw)
    except TypeError as error:
        raise ValidationError('readings require an ordered sequence') from error
    return tuple(parse_reading(item) for item in iterator)
