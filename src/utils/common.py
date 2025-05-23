

def format_dict_for_debug(data, max_len: int = 20, head_len: int = 10, tail_len: int = 10):
    """
    Recursively formats a dictionary or list for debugging, truncating long string values.

    Args:
        data: The dictionary or list to format.
        max_len: The maximum length a string can be before truncation.
        head_len: The number of characters to show from the beginning of a long string.
        tail_len: The number of characters to show from the end of a long string.

    Returns:
        A new dictionary or list with long strings truncated, or the original value
        if it's not a dict or list.
    """
    if isinstance(data, dict):
        formatted_data = {}
        for key, value in data.items():
            formatted_data[key] = format_dict_for_debug(value, max_len, head_len, tail_len) # Recurse on value
        return formatted_data
    elif isinstance(data, list):
        formatted_list = []
        for item in data:
            formatted_list.append(format_dict_for_debug(item, max_len, head_len, tail_len)) # Recurse on list item
        return formatted_list
    elif isinstance(data, str) and len(data) > max_len:
        # Apply truncation logic to the string
        if head_len + tail_len < len(data):
             return data[:head_len] + "..." + data[-tail_len:]
        else:
             # Simple truncation if head+tail >= len(data) but len(data) > max_len
             # This case handles strings that are longer than max_len but not long enough
             # for the head+tail truncation to be shorter than the original string.
             # We still want to truncate them to max_len for brevity.
             return data[:max_len] + "..."
    else:
        # Return other data types as is
        return data