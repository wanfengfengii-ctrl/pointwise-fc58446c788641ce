import hashlib
import json

from errors import ValidationError


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{label} must be nonempty text')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValidationError(f'{label} must be valid Unicode') from error
    return value


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json(value).encode('ascii')).hexdigest()
    return f'{prefix}-{digest}'


def expect_fields(data: object, fields: set[str], label: str) -> dict:
    if not isinstance(data, dict) or data.keys() != fields:
        raise ValidationError(f'invalid {label} fields')
    return data


def expect_list(data: object, label: str) -> list:
    if not isinstance(data, list):
        raise ValidationError(f'{label} must be an ordered list')
    return data
