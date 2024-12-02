from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form, Request, Query, Path
from boto3.dynamodb.conditions import Key
import boto3
import os
from uuid import uuid4
from datetime import datetime
from .models.models import Event, REGISTRATION_REQUESTS_TABLE
from .middleware import require_role, get_current_user
from enum import Enum
from pydantic import BaseModel
from typing import List
from fastapi.responses import JSONResponse
from botocore.exceptions import ClientError
import json

router = APIRouter()

# Initialize AWS clients with explicit region
dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION'))
s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION'))
events_table = dynamodb.Table(os.getenv('DYNAMODB_EVENTS_TABLE'))
registration_requests_table = dynamodb.Table(REGISTRATION_REQUESTS_TABLE['TableName'])
sns = boto3.client('sns', region_name=os.getenv('AWS_REGION'))
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN')

class RegistrationStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class RegistrationRequest(BaseModel):
    full_name: str
    email: str
    college_name: str
    year_of_study: str
    phone_number: str
    why_interested: str

@router.post("/")
async def create_event(
    title: str = Form(...),
    description: str = Form(...),
    date: str = Form(...),
    location: str = Form(...),
    max_participants: int = Form(...),
    organizer_id: str = Form(...),
    banner: UploadFile = File(None)  # Optional file upload
):
    try:
        # Convert the date string to a datetime object
        event_date = datetime.fromisoformat(date)
        event_date_str = event_date.isoformat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

    # Prepare event data
    event_data = {
        "id": str(uuid4()),  # Generate a unique ID
        "title": title,
        "description": description,
        "date": event_date_str,  # Store as string
        "location": location,
        "max_participants": max_participants,
        "organizer_id": organizer_id,
    }

    # Ensure all datetime fields are strings before storing
    for key, value in event_data.items():
        if isinstance(value, datetime):
            event_data[key] = value.isoformat()  # Convert to string if it's a datetime


    # Handle banner upload
    if banner:
        try:
            # Upload the file to S3
            s3_key = f"banners/{event_data['id']}/{banner.filename}"
            s3.upload_fileobj(banner.file, os.getenv('S3_BUCKET_NAME'), s3_key)
            # Store the S3 URL in the event data
            event_data['banner_url'] = f"https://{os.getenv('S3_BUCKET_NAME')}.s3.amazonaws.com/{s3_key}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploading banner: {e}")

    # Store event in DynamoDB
    try:
        events_table.put_item(Item=event_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing event: {e}")

    return {"message": "Event created successfully", "banner_url": event_data.get('banner_url')}

@router.get("/events/{event_id}")
async def get_event(event_id: str):
    try:
        response = events_table.get_item(Key={'id': event_id})
        if 'Item' not in response:
            raise HTTPException(status_code=404, detail="Event not found")
        return response['Item']
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{event_id}/register")
async def register_for_event(
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        # Get the event
        event = events_table.get_item(Key={'id': event_id})
        if 'Item' not in event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        event = event['Item']
        
        # Check if user is already registered
        participants = event.get('participants', [])
        if current_user['id'] in participants:
            raise HTTPException(status_code=400, detail="Already registered for this event")
            
        # Check if event is full
        if len(participants) >= event['max_participants']:
            raise HTTPException(status_code=400, detail="Event is full")
            
        # Add user to participants
        events_table.update_item(
            Key={'id': event_id},
            UpdateExpression="SET participants = list_append(if_not_exists(participants, :empty_list), :user)",
            ExpressionAttributeValues={
                ':user': [current_user['id']],
                ':empty_list': []
            }
        )
        
        return {"message": "Successfully registered for event"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events/organizer/{organizer_id}")
@require_role("organizer")
async def get_organizer_events(organizer_id: str):
    try:
        response = events_table.query(
            IndexName='organizer-index',
            KeyConditionExpression=Key('organizer_id').eq(organizer_id)
        )
        return response['Items']
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def get_all_events():
    try:
        response = events_table.scan()  # Use scan to get all items
        return response['Items']  # Return the list of events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{event_id}/register-request")
async def create_registration_request(
    event_id: str,
    registration_data: RegistrationRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        # First check if the event exists
        event = events_table.get_item(Key={'id': event_id})
        if 'Item' not in event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        event_data = event['Item']
        
        # Check if user is already registered
        participants = event_data.get('participants', [])
        if current_user['id'] in participants:
            raise HTTPException(status_code=400, detail="Already registered for this event")
            
        # Check if event is full
        if len(participants) >= event_data['max_participants']:
            raise HTTPException(status_code=400, detail="Event is full")

        request_id = str(uuid4())
        request_data = {
            "id": request_id,
            "event_id": event_id,
            "user_id": current_user['id'],
            "status": RegistrationStatus.APPROVED,
            "created_at": datetime.now().isoformat(),
            **registration_data.model_dump()
        }
            
        # Create registration request
        registration_requests_table.put_item(Item=request_data)
        
        # Add user to event participants
        events_table.update_item(
            Key={'id': event_id},
            UpdateExpression="SET participants = list_append(if_not_exists(participants, :empty_list), :user)",
            ExpressionAttributeValues={
                ':user': [current_user['id']],
                ':empty_list': []
            }
        )

        # Send confirmation email
        await send_registration_confirmation(
            email=registration_data.email,
            event_data=event_data,
            registration_data=request_data
        )
        
        return {"message": "Registration request submitted successfully", "request_id": request_id}
            
    except Exception as e:
        print(f"Error creating registration request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create registration request: {str(e)}")

@router.get("/registration-requests")
async def get_registration_requests(request: Request):
    """
    Get all registration requests regardless of status.
    """
    try:
        # Simple scan without any filters
        response = registration_requests_table.scan()
        return JSONResponse(content=response.get('Items', []))
        
    except Exception as e:
        print(f"Error in get_registration_requests: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

@router.put("/registration-requests/{request_id}")
async def update_registration_status(
    request_id: str,
    status: RegistrationStatus,
    user=Depends(require_role("organizer"))
):
    try:
        # Update the registration request status
        registration_requests_table.update_item(
            Key={'id': request_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': status}
        )
        
        # If approved, add to event participants
        if status == RegistrationStatus.APPROVED:
            request = registration_requests_table.get_item(Key={'id': request_id})['Item']
            events_table.update_item(
                Key={'id': request['event_id']},
                UpdateExpression="SET participants = list_append(if_not_exists(participants, :empty_list), :user)",
                ExpressionAttributeValues={
                    ':user': [request['user_id']],
                    ':empty_list': []
                }
            )
        
        return {"message": f"Registration request {status}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/registration-requests/debug/{status}")
async def debug_registration_requests(
    request: Request,
    status: str,
):
    print("Headers:", request.headers)
    print("Query Params:", request.query_params)
    print("Path Params:", request.path_params)
    return {
        "headers": dict(request.headers),
        "query_params": dict(request.query_params),
        "path_params": dict(request.path_params),
    }

@router.get("/registration-requests/debug/table")
async def debug_table():
    try:
        # List all tables
        tables = dynamodb.meta.client.list_tables()
        print("Available tables:", tables['TableNames'])
        
        # Get table info
        table_info = registration_requests_table.table_status
        print("Table status:", table_info)
        
        # Try a simple scan
        response = registration_requests_table.scan(Limit=1)
        print("Sample scan:", response)
        
        return {
            "tables": tables['TableNames'],
            "table_status": table_info,
            "sample_scan": response
        }
    except Exception as e:
        print(f"Debug error: {str(e)}")
        return {"error": str(e)}

async def send_registration_confirmation(email: str, event_data: dict, registration_data: dict):
    try:
        message = {
            "email": email,
            "subject": f"Registration Confirmation - {event_data['title']}",
            "message": f"""
            Dear {registration_data['full_name']},

            Thank you for registering for {event_data['title']}!

            Event Details:
            - Date: {event_data['date']}
            - Location: {event_data['location']}

            We're excited to have you join us!

            Best regards,
            The Event Team
            """
        }

        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            MessageStructure='string'
        )
        print(f"Sent confirmation email to {email}: {response['MessageId']}")
    except Exception as e:
        print(f"Error sending confirmation email: {str(e)}")

@router.get("/analytics/registrations")
async def get_registration_analytics(user=Depends(require_role("organizer"))):
    try:
        lambda_client = boto3.client('lambda')
        response = lambda_client.invoke(
            FunctionName='registration_analytics',
            InvocationType='RequestResponse'
        )
        
        payload = json.loads(response['Payload'].read())
        return JSONResponse(content=payload.get('body', {}))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
