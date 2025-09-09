# expose the ASGI app for Vercel's Python runtime
from main import app as fastapi_app
app = fastapi_app
