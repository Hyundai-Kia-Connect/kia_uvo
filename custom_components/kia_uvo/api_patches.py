"""
Patches for hyundai_kia_connect_api library to fix Kia USA OTP authentication.

The Kia USA API changed its authentication flow. After OTP verification, the API
no longer returns an 'rmtoken' in the response headers. The original code requires
both 'sid' and 'rmtoken' to complete login, causing authentication to fail.

This patch fixes the issue by:
1. Using the 'sid' from OTP verification directly as the session token
2. Testing if the sid works for API calls before attempting the problematic
   second authentication step
3. Falling back gracefully if the standard flow fails

See: https://github.com/Hyundai-Kia-Connect/kia_uvo/issues/1221
"""

import datetime as dt
import logging

_LOGGER = logging.getLogger(__name__)
_PATCHES_APPLIED = False


def _patched_verify_otp(self, otp_key: str, otp_code: str, xid: str) -> tuple[str, str]:
    """
    Verify OTP code and return sid and rmtoken.

    Handles the case where rmtoken is not returned by using sid as fallback.
    """
    from hyundai_kia_connect_api.const import DOMAIN

    url = self.API_URL + "cmm/verifyOTP"
    headers = self.api_headers()
    headers["otpkey"] = otp_key
    headers["xid"] = xid
    data = {"otp": otp_code}

    response = self.session.post(url, json=data, headers=headers)
    _LOGGER.debug(f"{DOMAIN} - Verify OTP response: {response.text}")

    response_json = response.json()

    status_code = response_json.get("status", {}).get("statusCode", -1)
    if status_code != 0:
        error_msg = response_json.get("status", {}).get("errorMessage", "Unknown error")
        raise Exception(f"{DOMAIN} - OTP verification failed: {error_msg}")

    # Extract sid from headers or response body
    sid = response.headers.get("sid")
    if not sid:
        sid = response_json.get("sid")
    if not sid:
        payload = response_json.get("payload", {})
        if payload:
            sid = payload.get("sid")

    if not sid:
        raise Exception(
            f"{DOMAIN} - No sid in OTP verification response. "
            f"Headers: {dict(response.headers)}"
        )

    # Try to get rmtoken, fall back to sid if not present
    rmtoken = response.headers.get("rmtoken")
    if not rmtoken:
        rmtoken = response_json.get("rmtoken")
    if not rmtoken:
        payload = response_json.get("payload", {})
        if payload:
            rmtoken = payload.get("rmtoken")

    if not rmtoken:
        _LOGGER.debug(f"{DOMAIN} - No rmtoken in response, using sid as fallback")
        rmtoken = sid

    return sid, rmtoken


def _patched_verify_otp_and_complete_login(
    self,
    username: str,
    password: str,
    otp_code: str,
    otp_request,
    pin: str | None,
):
    """
    Verify OTP and complete login.

    The Kia USA API no longer returns rmtoken after OTP verification, which breaks
    the standard login flow. This patch tests if the sid from OTP verification
    can be used directly as a session token, bypassing the problematic second
    authentication step.
    """
    from hyundai_kia_connect_api.Token import Token
    from hyundai_kia_connect_api.const import DOMAIN, LOGIN_TOKEN_LIFETIME

    sid, rmtoken = self._verify_otp(
        otp_request.otp_key, otp_code, otp_request.request_id
    )

    _LOGGER.debug(f"{DOMAIN} - OTP verified, testing if sid works as session")

    valid_until = dt.datetime.now(dt.timezone.utc) + LOGIN_TOKEN_LIFETIME

    # Test if the OTP sid works directly for API calls
    try:
        url = self.API_URL + "ownr/gvl"
        headers = self.api_headers()
        headers["sid"] = sid

        response = self.session.get(url, headers=headers)
        response_json = response.json()
        payload = response_json.get("payload")

        if payload and payload.get("vehicleSummary"):
            _LOGGER.info(f"{DOMAIN} - OTP sid works as session, login successful")
            return Token(
                username=username,
                password=password,
                access_token=sid,
                refresh_token=rmtoken,
                valid_until=valid_until,
                device_id=self.device_id,
                pin=pin,
            )
    except Exception as e:
        _LOGGER.debug(f"{DOMAIN} - Direct sid test failed: {e}")

    # Fall back to trying the complete login flow
    _LOGGER.debug(f"{DOMAIN} - Trying standard complete login flow")
    try:
        final_sid = self._complete_login_with_otp(username, password, sid, rmtoken)
    except Exception as e:
        _LOGGER.warning(
            f"{DOMAIN} - Standard login flow failed ({e}), using OTP sid as session"
        )
        final_sid = sid

    return Token(
        username=username,
        password=password,
        access_token=final_sid,
        refresh_token=rmtoken,
        valid_until=valid_until,
        device_id=self.device_id,
        pin=pin,
    )


def apply_patches():
    """Apply patches to fix Kia USA OTP authentication."""
    global _PATCHES_APPLIED

    if _PATCHES_APPLIED:
        return

    from hyundai_kia_connect_api.KiaUvoApiUSA import KiaUvoApiUSA

    KiaUvoApiUSA._verify_otp = _patched_verify_otp
    KiaUvoApiUSA.verify_otp_and_complete_login = _patched_verify_otp_and_complete_login

    _PATCHES_APPLIED = True
    _LOGGER.debug("Applied Kia USA OTP authentication patches")
