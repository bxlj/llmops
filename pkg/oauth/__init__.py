"""
@Time    : 2026-06-29 16:02
@Author  : JiaChengJie
@File    : __init__.py.py
"""
from .github_oauth import GithubOAuth
from .oauth import OAuthUserInfo, OAuth

__all__ = ["OAuthUserInfo", "OAuth", "GithubOAuth"]
