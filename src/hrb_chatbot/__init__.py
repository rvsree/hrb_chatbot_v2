import warnings

from pydantic.warnings import UnsupportedFieldAttributeWarning

# llama-index-core's IdFuncCallable type alias triggers a harmless pydantic
# warning it can't itself avoid - suppressed here (not main.py) so it's in effect before any submodule imports.
warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)
