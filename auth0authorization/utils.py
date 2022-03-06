import json
import os

from django.contrib.auth import authenticate
import jwt
import requests

from SpineSplinr import settings


def jwt_get_username_from_payload_handler(payload):
    username = payload.get('sub').replace('|', '.')
    authenticate(remote_user=username)
    return username


def jwt_decode_token(token):
    header = jwt.get_unverified_header(token)
    auth0_domain = os.environ.get('AUTH0_DOMAIN')
    jwks = requests.get('https://{}/.well-known/jwks.json'.format(auth0_domain)).json()
    public_key = None
    for jwk in jwks['keys']:
        if jwk['kid'] == header['kid']:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    if public_key is None:
        raise Exception('Public key not found.')
    settings.PUBLIC_KEY=public_key
    api_identifier = os.environ.get('API_IDENTIFIER')
    issuer = 'https://{}/'.format(auth0_domain)
    return jwt.decode(token, public_key, audience=api_identifier, issuer=issuer, algorithms=['RS256'])

def get_token_auth_header(request):
    """Obtains the access token from the Authorization Header
    """
    auth = request.META.get("HTTP_AUTHORIZATION", None)
    parts = auth.split()
    token = parts[1]

    return token
