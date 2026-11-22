from errors import ValidationError


def checked_range(length: int, start: int, delete_count: int) -> tuple[int, int]:
    if any(type(value) is not int or value < 0 for value in (length, start, delete_count)):
        raise ValidationError('row position and deletion count must be nonnegative integers')
    end = start + delete_count
    if start > length or end > length:
        raise ValidationError(f'row range [{start}, {end}) exceeds parent length {length}')
    return start, end
