from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv
import hmac
import base64
import hashlib
from enum import Enum

# Load environment variables
load_dotenv()

router = APIRouter()

# Initialize Cognito client
cognito_client = boto3.client(
    "cognito-idp",
    region_name="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

class UserRole(str, Enum):
    ORGANIZER = "organizer"
    PARTICIPANT = "participant"

class UserAuth(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.PARTICIPANT  # Default role is participant

def get_secret_hash(username: str) -> str:
    msg = username + os.getenv("COGNITO_USER_POOL_CLIENT_ID")
    dig = hmac.new(
        str(os.getenv("COGNITO_CLIENT_SECRET")).encode('utf-8'), 
        msg=msg.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

@router.post("/signup")
async def sign_up(user: UserAuth):
    try:
        secret_hash = get_secret_hash(user.email)
        response = cognito_client.sign_up(
            ClientId=os.getenv("COGNITO_USER_POOL_CLIENT_ID"),
            Username=user.email,
            Password=user.password,
            SecretHash=secret_hash,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': user.email
                },
                {
                    'Name': 'custom:role',
                    'Value': user.role
                }
            ]
        )
        
        # Auto-confirm the user (for development)
        try:
            cognito_client.admin_confirm_sign_up(
                UserPoolId=os.getenv("COGNITO_USER_POOL_ID"),
                Username=user.email
            )
            
            # Add user to appropriate group based on role
            if user.role == UserRole.ORGANIZER:
                cognito_client.admin_add_user_to_group(
                    UserPoolId=os.getenv("COGNITO_USER_POOL_ID"),
                    Username=user.email,
                    GroupName='organizers'
                )
        except ClientError as e:
            print(f"Error in post-signup operations: {e}")
            
        return {"message": "User registered successfully", "userSub": response["UserSub"]}
    except ClientError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/signin")
async def sign_in(user: UserAuth):
    try:
        secret_hash = get_secret_hash(user.email)
        response = cognito_client.initiate_auth(
            ClientId=os.getenv("COGNITO_USER_POOL_CLIENT_ID"),
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': user.email,
                'PASSWORD': user.password,
                'SECRET_HASH': secret_hash
            }
        )
        return {
            "message": "Login successful",
            "token": response["AuthenticationResult"]["AccessToken"]
        }
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        raise HTTPException(
            status_code=401, 
            detail=f"Authentication failed: {error_message}"
        )

@router.post("/create-organizer")
async def create_organizer(
    user: UserAuth, 
    admin_key: str = Query(..., description="Admin secret key")
):
    if admin_key != os.getenv("ADMIN_SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid admin key")
    
    user.role = UserRole.ORGANIZER
    return await sign_up(user)

@router.post("/admin/signin")
async def admin_signin(user_data: UserAuth):
    try:
        # Generate SECRET_HASH
        message = user_data.email + os.getenv("COGNITO_USER_POOL_CLIENT_ID")
        key = os.getenv("COGNITO_CLIENT_SECRET").encode('utf-8')
        secret_hash = base64.b64encode(
            hmac.new(
                key,
                message.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
        ).decode()

        response = cognito_client.initiate_auth(
            ClientId=os.getenv("COGNITO_USER_POOL_CLIENT_ID"),
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": user_data.email,
                "PASSWORD": user_data.password,
                "SECRET_HASH": secret_hash
            }
        )
        
        # Verify user is in organizer group
        user_groups = cognito_client.admin_list_groups_for_user(
            Username=user_data.email,
            UserPoolId=os.getenv("COGNITO_USER_POOL_ID")
        )
        
        is_organizer = any(group['GroupName'] == 'organizers' for group in user_groups['Groups'])
        
        if not is_organizer:
            raise HTTPException(
                status_code=403,
                detail="User is not authorized as an organizer"
            )
        
        return {
            "message": "Login successful",
            "token": response["AuthenticationResult"]["AccessToken"]
        }
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {error_message}"
        )
