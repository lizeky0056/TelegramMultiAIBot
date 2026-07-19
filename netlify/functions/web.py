import sys
import os

# Add root directory to path to import web.py
sys.path.append(os.path.join(os.getcwd(), '..', '..'))

from web import app
from mangum import Mangum

handler = Mangum(app)
