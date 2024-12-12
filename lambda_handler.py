from mangum import Mangum
import os

# Set environment variable before importing FastAPI app
os.environ['LAMBDA_RUNTIME'] = '1'

from app.main import app

# Create handler for Lambda
handler = Mangum(app, lifespan="off")