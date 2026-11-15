"""Strict TikTok transport: no synthetic success, no secrets in exceptions."""
import os
from urllib.parse import urlencode
import httpx


class TikTokError(Exception):
    def __init__(self, code, ambiguous=False):
        self.code, self.ambiguous = code, ambiguous
        super().__init__('TikTok: ' + code)


class TikTokV2:
    base = 'https://open.tiktokapis.com'

    def request(self, path, token=None, payload=None, form=False, initializing=False):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        try:
            with httpx.Client(timeout=35, trust_env=False, follow_redirects=False) as client:
                response = client.post(self.base + path, headers=headers,
                                       **({'data': payload} if form else {'json': payload or {}}))
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise TikTokError('connection_uncertain', ambiguous=initializing) from None
        if not isinstance(data,dict):
            raise TikTokError('invalid_response',ambiguous=initializing)
        error = data.get('error')
        code = error.get('code') if isinstance(error, dict) else error
        if not response.is_success or code not in (None, '', 'ok', 0):
            # Only bounded error codes; error descriptions may contain credentials.
            import re
            safe = str(code or response.status_code)
            safe = safe if re.fullmatch(r'[a-zA-Z0-9_]{1,100}', safe) else 'request_failed'
            raise TikTokError(safe, ambiguous=initializing and response.status_code >= 500)
        result=data.get('data',data)
        if not isinstance(result,dict):raise TikTokError('invalid_response',ambiguous=initializing)
        return result

    def authorization_url(self, state):
        return 'https://www.tiktok.com/v2/auth/authorize/?' + urlencode({
            'client_key': os.environ['TIKTOK_CLIENT_KEY'], 'scope': 'user.info.basic,video.publish',
            'response_type': 'code', 'redirect_uri': os.environ['TIKTOK_V2_REDIRECT_URI'], 'state': state})

    def exchange(self, code):
        return self.request('/v2/oauth/token/', payload={
            'client_key': os.environ['TIKTOK_CLIENT_KEY'], 'client_secret': os.environ['TIKTOK_CLIENT_SECRET'],
            'code': code, 'grant_type': 'authorization_code', 'redirect_uri': os.environ['TIKTOK_V2_REDIRECT_URI']}, form=True)

    def refresh(self, token):
        return self.request('/v2/oauth/token/', payload={
            'client_key': os.environ['TIKTOK_CLIENT_KEY'], 'client_secret': os.environ['TIKTOK_CLIENT_SECRET'],
            'refresh_token': token, 'grant_type': 'refresh_token'}, form=True)

    def creator(self, token):
        return self.request('/v2/post/publish/creator_info/query/', token)

    def publish(self, token, post, url):
        return self.request('/v2/post/publish/video/init/', token,
            {'post_info': post, 'source_info': {'source': 'PULL_FROM_URL', 'video_url': url}}, initializing=True)

    def status(self, token, publish_id):
        return self.request('/v2/post/publish/status/fetch/', token, {'publish_id': publish_id})

    def revoke(self, token):
        return self.request('/v2/oauth/revoke/', payload={
            'client_key': os.environ['TIKTOK_CLIENT_KEY'], 'client_secret': os.environ['TIKTOK_CLIENT_SECRET'],
            'token': token}, form=True)
