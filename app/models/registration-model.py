REGISTRATION_REQUESTS_TABLE = {
    'TableName': 'registration-requests',
    'KeySchema': [
        {
            'AttributeName': 'id',
            'KeyType': 'HASH'  # Partition key
        }
    ],
    'AttributeDefinitions': [
        {
            'AttributeName': 'id',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'event_id',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'status',
            'AttributeType': 'S'
        }
    ],
    'GlobalSecondaryIndexes': [
        {
            'IndexName': 'event-status-index',
            'KeySchema': [
                {
                    'AttributeName': 'event_id',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'status',
                    'KeyType': 'RANGE'
                }
            ],
            'Projection': {
                'ProjectionType': 'ALL'
            },
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        }
    ],
    'ProvisionedThroughput': {
        'ReadCapacityUnits': 5,
        'WriteCapacityUnits': 5
    }
}