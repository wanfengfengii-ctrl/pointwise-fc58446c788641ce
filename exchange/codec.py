import json
from dataclasses import dataclass

from errors import ValidationError
from exchange.manifest import Manifest, validate_manifest
from identity import canonical_json, expect_fields, fingerprint


PACKAGE_VERSION = 1


@dataclass(frozen=True, slots=True)
class Package:
    package_id: str
    manifest: Manifest
    wire: bytes


def package_number(manifest: Manifest) -> str:
    return fingerprint('package', [PACKAGE_VERSION, manifest.as_data()])


def _envelope(manifest: Manifest, package_id: str) -> bytes:
    return canonical_json({
        'version': PACKAGE_VERSION, 'package_id': package_id, 'manifest': manifest.as_data(),
    }).encode('ascii')


def encode_package(manifest: Manifest) -> bytes:
    validate_manifest(manifest)
    return _envelope(manifest, package_number(manifest))


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f'repeated package field: {key}')
        result[key] = value
    return result


def decode_package(wire: bytes) -> Package:
    if not isinstance(wire, bytes):
        raise ValidationError('package must be UTF-8 bytes')
    try:
        raw = json.loads(wire.decode('utf-8'), object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError) as error:
        raise ValidationError('package contains invalid UTF-8 or JSON') from error
    data = expect_fields(raw, {'version', 'package_id', 'manifest'}, 'package envelope')
    if type(data['version']) is not int or data['version'] != PACKAGE_VERSION:
        raise ValidationError('unsupported package version')
    manifest = Manifest.from_data(data['manifest'])
    package_id = package_number(manifest)
    if package_id != data['package_id']:
        raise ValidationError('package number does not bind its manifest')
    return Package(package_id, manifest, _envelope(manifest, package_id))
