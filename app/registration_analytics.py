import json
import boto3
from datetime import datetime
from collections import defaultdict

dynamodb = boto3.resource('dynamodb')
registration_table = dynamodb.Table('registration-requests')

def lambda_handler(event, context):
    try:
        # Scan registration requests
        response = registration_table.scan()
        registrations = response.get('Items', [])
        
        # Initialize analytics data
        analytics = {
            'total_registrations': len(registrations),
            'status_distribution': defaultdict(int),
            'college_distribution': defaultdict(int),
            'year_distribution': defaultdict(int),
            'timestamp': datetime.now().isoformat()
        }
        
        # Process registrations
        for reg in registrations:
            analytics['status_distribution'][reg['status']] += 1
            analytics['college_distribution'][reg['college_name']] += 1
            analytics['year_distribution'][reg['year_of_study']] += 1
        
        # Convert defaultdict to regular dict for JSON serialization
        analytics['status_distribution'] = dict(analytics['status_distribution'])
        analytics['college_distribution'] = dict(analytics['college_distribution'])
        analytics['year_distribution'] = dict(analytics['year_distribution'])
        
        return {
            'statusCode': 200,
            'body': json.dumps(analytics)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }