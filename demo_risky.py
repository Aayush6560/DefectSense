"""Complex data transformation with nested logic and high branching."""


def parse_and_validate_data(raw_data, strict_mode=False, allow_nulls=True, debug=False):
    """Parse complex nested data structure with extensive validation.
    
    Args:
        raw_data: Nested dictionary/list structure.
        strict_mode: If True, fail on any inconsistency.
        allow_nulls: If True, permit None values.
        debug: If True, print debug output.
    
    Returns:
        Validated data or None if validation fails.
    """
    if not raw_data:
        if strict_mode:
            return None
        return {}
    
    if isinstance(raw_data, dict):
        result = {}
        for key, value in raw_data.items():
            if value is None:
                if allow_nulls:
                    result[key] = None
                elif strict_mode:
                    return None
                else:
                    result[key] = ""
            elif isinstance(value, str):
                if len(value) == 0:
                    if strict_mode:
                        return None
                    result[key] = "EMPTY"
                elif value.startswith("#"):
                    result[key] = value[1:]
                elif value.startswith("@"):
                    if strict_mode and not validate_identifier(value[1:]):
                        return None
                    result[key] = value[1:]
                else:
                    result[key] = value.strip()
            elif isinstance(value, (int, float)):
                if value < 0:
                    if strict_mode:
                        return None
                    result[key] = abs(value)
                else:
                    result[key] = value
            elif isinstance(value, list):
                nested = []
                for item in value:
                    if item is None:
                        if allow_nulls:
                            nested.append(None)
                    elif isinstance(item, dict):
                        if all(k in item for k in ['id', 'name']):
                            nested.append(parse_and_validate_data(item, strict_mode, allow_nulls))
                        elif strict_mode:
                            return None
                    elif isinstance(item, str):
                        if item and item[0].isupper():
                            nested.append(item)
                        elif strict_mode:
                            return None
                result[key] = nested
            elif isinstance(value, dict):
                nested_result = parse_and_validate_data(value, strict_mode, allow_nulls)
                if nested_result is None and strict_mode:
                    return None
                result[key] = nested_result
        return result
    elif isinstance(raw_data, list):
        results = []
        for item in raw_data:
            if isinstance(item, dict):
                parsed = parse_and_validate_data(item, strict_mode, allow_nulls)
                if parsed is not None:
                    results.append(parsed)
                elif not strict_mode:
                    results.append({})
            elif isinstance(item, str):
                if item.strip():
                    results.append(item.strip())
        return results
    
    return raw_data


def validate_identifier(identifier):
    """Check if identifier follows naming rules.
    
    Args:
        identifier: String to validate.
    
    Returns:
        True if valid, False otherwise.
    """
    if not identifier:
        return False
    if not identifier[0].isalpha() and identifier[0] != '_':
        return False
    for char in identifier:
        if not (char.isalnum() or char == '_'):
            return False
    return True


def transform_nested_records(data, transformers=None):
    """Apply transformations to deeply nested record structures.
    
    Args:
        data: Nested data structure.
        transformers: Dict of field transformations.
    
    Returns:
        Transformed data structure.
    """
    transformers = transformers or {}
    
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in transformers:
                transform_func = transformers[key]
                result[key] = transform_func(value)
            elif isinstance(value, (dict, list)):
                result[key] = transform_nested_records(value, transformers)
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        results = []
        for item in data:
            if isinstance(item, (dict, list)):
                results.append(transform_nested_records(item, transformers))
            else:
                results.append(item)
        return results
    
    return data
