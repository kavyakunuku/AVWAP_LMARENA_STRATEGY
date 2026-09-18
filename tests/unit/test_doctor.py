import base64
import json
from app.data.doctor import _decode_jwt_payload_no_verify


def test_decode_jwt_payload_no_verify():
    payload = {"exp": 123, "dhanClientId": "abc"}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    token = "header." + encoded + ".sig"
    assert _decode_jwt_payload_no_verify(token)["exp"] == 123
