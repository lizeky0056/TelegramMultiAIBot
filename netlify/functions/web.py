import sys
import os

# Agregar directorio raíz al sys.path usando la ubicación exacta de este archivo
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from web import app
from mangum import Mangum

handler = Mangum(app)

