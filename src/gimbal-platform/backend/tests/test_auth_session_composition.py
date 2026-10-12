"""W20(B-5):AuthSession 组合生成物 UserCredential 的契约测试。

M2 §9.2:凭证定义归 M2(UserCredential),运行态(token/expires_at)与
方法留在平台运行时类。本文件钉住三件事:
1. 值的唯一权威 = credential 字段(平铺属性是薄投影,不另立状态);
2. 历史平铺 kwargs 构造形态不破(构造点零改动过波);
3. extra=forbid 红线不随组合放松。
"""
from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from app.auth.schema import AuthSession
from app.schemas._m2 import UserCredential


def test_flat_kwargs_fold_into_credential():
    """平铺 kwargs(历史构造形态)折叠进 credential;属性读回同值。"""
    a = AuthSession(url="http://u", username="n", password="p",
                    token_type="Bearer", expires_in=100, refresh_token="r")
    assert isinstance(a.credential, UserCredential)
    assert a.credential.url == "http://u"
    assert a.url == "http://u" and a.username == "n" and a.password == "p"
    assert a.token_type == "Bearer" and a.expires_in == 100
    assert a.refresh_token == "r"


def test_property_writes_land_on_credential():
    """属性写回委托到 credential(唯一权威,无第二份状态)。"""
    a = AuthSession(url="http://u", username="n", password="p")
    a.url = "http://v"
    a.refresh_token = "r2"
    assert a.credential.url == "http://v"
    assert a.credential.refresh_token == "r2"


def test_nested_credential_construction_and_precedence():
    """显式 credential 子键胜出平铺键(平铺只补缺)。"""
    a = AuthSession(url="http://flat", credential={"url": "http://nested",
                                                   "username": "x"})
    assert a.url == "http://nested"
    assert a.username == "x"


def test_runtime_state_and_methods():
    """运行态/方法不受组合影响(apply_token/clear_*/is_same_credential)。"""
    a = AuthSession(url="http://u", username="n", password="p")
    a.apply_token("tok", 50)
    assert a.is_authenticated
    assert a.token == "tok" and a.expires_at is not None
    # apply_token(expires_in>0) 写 credential.expires_in
    assert a.credential.expires_in == 50
    a.clear_token()
    assert a.token is None and a.expires_at is None
    assert a.credential.expires_in is None
    assert not a.is_authenticated
    b = AuthSession(url="http://u", username="n", password="p2")
    assert a.is_same_credential(AuthSession(url="http://u", username="n",
                                            password="p"))
    assert not a.is_same_credential(b)
    a.clear_password()
    assert a.password == "" and a.credential.password == ""


def test_expired_token_not_authenticated():
    a = AuthSession()
    a.apply_token("t", 10)
    a.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=5)
    assert not a.is_authenticated


def test_extra_forbid_still_enforced():
    """组合不放松 forbid:未知键仍拒(与生成物 UserCredential 同红线)。"""
    with pytest.raises(ValidationError):
        AuthSession(bogus=1)
    with pytest.raises(ValidationError):
        AuthSession(credential={"url": "http://u", "bogus": 1})


def test_from_dict_flat_form():
    a = AuthSession.from_dict({"url": "http://fd", "username": "u",
                               "password": "p"})
    assert a.url == "http://fd" and a.credential.username == "u"
