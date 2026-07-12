import json
from pathlib import Path
from typing import Any

def read_json(file_path: str | Path) -> Any:
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in '{file_path}': {e}")

def write_json(file_path: str | Path, data: Any) -> None:
    
    path = Path(file_path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

    except TypeError as e:
        raise TypeError(f"Data is not JSON serializable: {e}") from e
    except OSError as e:
        raise OSError(f"Failed to write to '{path}': {e}") from e


