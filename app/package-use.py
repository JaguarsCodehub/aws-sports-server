from sports_event_utils import generate_secret_hash, validate_event_data

secret_hash = generate_secret_hash(username, client_id, client_secret)
# This is the secret hash that my package will generate based upon the username, client_id, and client_secret of our Cognito user pool




