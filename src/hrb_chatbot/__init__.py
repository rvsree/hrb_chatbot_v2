import warnings

from pydantic.warnings import UnsupportedFieldAttributeWarning

# llama-index-core 0.13.6's own IdFuncCallable type alias attaches
# Field(validate_default=True) directly inside Annotated[...] rather than to
# a model field, which pydantic 2.13.5 (bumped for llama-index-core, see
# requirements.txt) now warns about the first time that schema is built.
# It's llama-index's own code, harmless, and not something this project can
# fix from the caller side. Registered here (not main.py) so it's in effect
# before any submodule import, no matter which one runs first (main.py,
# a test, etc.).
warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)
