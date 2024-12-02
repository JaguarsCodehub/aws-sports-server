import boto3
import os
from .models.models import REGISTRATION_REQUESTS_TABLE

def create_tables():
    dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
    
    tables = dynamodb.meta.client.list_tables()['TableNames']
    
    # # Create events table if it doesn't exist
    # if EVENTS_TABLE['TableName'] not in tables:
    #     dynamodb.create_table(**EVENTS_TABLE)
    #     print(f"Created table: {EVENTS_TABLE['TableName']}")
    
    # Create registration requests table if it doesn't exist
    if REGISTRATION_REQUESTS_TABLE['TableName'] not in tables:
        dynamodb.create_table(**REGISTRATION_REQUESTS_TABLE)
        print(f"Created table: {REGISTRATION_REQUESTS_TABLE['TableName']}")

    print("Tables setup completed")