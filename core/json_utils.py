def strip_json_output(output: str) -> str:
    clean_output = output.strip()
    if clean_output.startswith("```json"):
        clean_output = clean_output[7:]
    if clean_output.startswith("```"):
        clean_output = clean_output[3:]
    if clean_output.endswith("```"):
        clean_output = clean_output[:-3]
    clean_output = clean_output.strip()
    return clean_output