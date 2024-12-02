from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
import jwt
import os
from jwt.algorithms import RSAAlgorithm
import requests
from functools import wraps

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["RS256"])
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {
            "id": payload["sub"],
            "email": payload.get("email", ""),
            "role": payload.get("custom:role", "participant")
        }
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(required_role: str):
    async def dependency(request: Request):
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                raise HTTPException(status_code=401, detail="No valid token provided")

            token = auth_header.split(' ')[1]
            try:
                payload = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
                if payload.get('role') != required_role:
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                return payload
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token has expired")
            except jwt.JWTError:
                raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            print(f"Auth error: {str(e)}")
            raise
    return dependency

def get_cognito_public_keys():
    region = os.getenv('AWS_REGION')
    pool_id = os.getenv('COGNITO_USER_POOL_ID')
    url = f'https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json'
    response = requests.get(url)
    return response.json()['keys']

def require_role(role: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = next(arg for arg in args if isinstance(arg, Request))
            auth_header = request.headers.get('Authorization')
            
            if not auth_header or not auth_header.startswith('Bearer '):
                raise HTTPException(status_code=401, detail="Invalid authorization header")
            
            token = auth_header.split(' ')[1]
            
            try:
                # Decode JWT token header to get kid
                header = jwt.get_unverified_header(token)
                kid = header['kid']
                
                # Get public keys from Cognito
                keys = get_cognito_public_keys()
                key = next((k for k in keys if k['kid'] == kid), None)
                
                if not key:
                    raise HTTPException(status_code=401, detail="Invalid token key")
                
                # Convert JWK to PEM format
                public_key = RSAAlgorithm.from_jwk(key)
                
                # Verify and decode token
                decoded = jwt.decode(
                    token,
                    public_key,
                    algorithms=['RS256'],
                    audience=os.getenv('COGNITO_USER_POOL_CLIENT_ID')
                )
                
                # Check user role
                user_role = decoded.get('custom:role')
                if user_role != role:
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                
                # Add user info to request state
                request.state.user = {
                    'id': decoded['sub'],
                    'email': decoded['email'],
                    'role': user_role
                }
                
                return await func(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token has expired")
            except jwt.InvalidTokenError as e:
                raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
            except Exception as e:
                raise HTTPException(status_code=401, detail=str(e))
        return wrapper
    return decorator