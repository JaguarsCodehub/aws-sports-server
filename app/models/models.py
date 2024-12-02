from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class EventStatus(str, Enum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"

class Event(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    date: datetime
    location: str
    max_participants: int
    organizer_id: str
    banner_url: Optional[str] = None
    status: EventStatus = EventStatus.UPCOMING
    participants: List[str] = []


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
        }
    ],
    'ProvisionedThroughput': {
        'ReadCapacityUnits': 5,
        'WriteCapacityUnits': 5
    }
}