import boto3
import os
from dotenv import load_dotenv
from app.models.models import REGISTRATION_REQUESTS_TABLE

load_dotenv()

def test_table_access():
    try:
        dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
        table = dynamodb.Table(REGISTRATION_REQUESTS_TABLE['TableName'])
        
        # Try to put a test item
        test_item = {
            'id': 'test-id',
            'test_field': 'test_value'
        }
        
        print(f"Attempting to access table: {REGISTRATION_REQUESTS_TABLE['TableName']}")
        print(f"In region: {os.getenv('AWS_REGION')}")
        
        # List all tables
        tables = dynamodb.meta.client.list_tables()['TableNames']
        print(f"Available tables: {tables}")
        
        # Try to put item
        table.put_item(Item=test_item)
        print("Successfully put test item")
        
        # Try to get item
        response = table.get_item(Key={'id': 'test-id'})
        print("Successfully retrieved item:", response.get('Item'))
        
    except Exception as e:
        print(f"Error testing table access: {str(e)}")

if __name__ == "__main__":
    test_table_access()