import boto3
import os
from dotenv import load_dotenv
from app.models.models import REGISTRATION_REQUESTS_TABLE

# Load environment variables
load_dotenv()

def create_tables():
    try:
        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
        
        # Get existing tables
        existing_tables = dynamodb.meta.client.list_tables()['TableNames']
        
        # Create registration requests table if it doesn't exist
        if REGISTRATION_REQUESTS_TABLE['TableName'] not in existing_tables:
            table = dynamodb.create_table(**REGISTRATION_REQUESTS_TABLE)
            table.wait_until_exists()
            print(f"Created table: {REGISTRATION_REQUESTS_TABLE['TableName']}")
        else:
            print(f"Table {REGISTRATION_REQUESTS_TABLE['TableName']} already exists")
            
        print("Tables setup completed")
        
    except Exception as e:
        print(f"Error creating tables: {str(e)}")

if __name__ == "__main__":
    create_tables()