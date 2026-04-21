import requests

from modulus_cli.constants import MODULUS_API_KEY_VERIFY_URL, MODULUS_INDEX_URL


def verify_api_key(api_key: str) -> requests.Response:
    response = requests.post(MODULUS_API_KEY_VERIFY_URL, json={"api_key": api_key})
    return response


def index_repo(repo_data: dict, api_key: str) -> requests.Response:
    return requests.post(
        MODULUS_INDEX_URL,
        json={"repo_data": repo_data, "api_key": api_key},
        headers={"Content-Type": "application/json"},
    )
