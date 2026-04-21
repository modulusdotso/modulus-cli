import requests

from modulus_cli.constants import MODULUS_API_KEY_VERIFY_URL


def verify_api_key(api_key: str) -> requests.Response:
    response = requests.post(MODULUS_API_KEY_VERIFY_URL, json={"api_key": api_key})
    return response
