import os
import json
import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from src.core.account_manager import AccountManager

class TestAccountManager:
    """Cookie 管理测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录用于测试"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def account_manager(self, temp_dir):
        """创建AccountManager实例用于测试"""
        return AccountManager(master_key="test_key", storage_path=temp_dir)
    
    @pytest.fixture
    def sample_cookies(self):
        """创建示例Cookie列表"""
        return [
            {
                "name": "session_id",
                "value": "test_session_123",
                "domain": "xiaohongshu.com",
                "path": "/",
                "expires": (datetime.now() + timedelta(days=30)).timestamp(),
                "httpOnly": True,
                "secure": True
            },
            {
                "name": "user_token",
                "value": "token_456",
                "domain": ".xiaohongshu.com",
                "path": "/",
                "expires": (datetime.now() + timedelta(days=30)).timestamp(),
                "httpOnly": True,
                "secure": True
            },
            {
                "name": "other_cookie",
                "value": "other_value",
                "domain": "other-domain.com",
                "path": "/",
                "expires": (datetime.now() + timedelta(days=30)).timestamp(),
                "httpOnly": False,
                "secure": False
            }
        ]
    
    def test_init_platforms(self, account_manager):
        """测试初始化时是否正确加载了平台定义"""
        # 验证预设平台是否存在
        assert "xiaohongshu" in account_manager.platforms
        assert "weibo" in account_manager.platforms
        assert "bilibili" in account_manager.platforms
        
        # 验证平台定义字段
        platform = account_manager.platforms["xiaohongshu"]
        assert platform["name"] == "小红书"
        assert "cookie_domains" in platform
        assert "login_url" in platform
        assert "requires_login" in platform
    
    def test_add_platform(self, account_manager):
        """测试添加平台功能"""
        result = account_manager.add_platform(
            platform_id="test_platform",
            name="测试平台",
            cookie_domains=["test.com", ".test.com"],
            login_url="https://test.com/login",
            requires_login=True
        )
        
        assert result is True
        assert "test_platform" in account_manager.platforms
        
        platform = account_manager.platforms["test_platform"]
        assert platform["name"] == "测试平台"
        assert platform["cookie_domains"] == ["test.com", ".test.com"]
        assert platform["login_url"] == "https://test.com/login"
        assert platform["requires_login"] == True
    
    def test_filter_platform_cookies(self, account_manager, sample_cookies):
        """测试Cookie过滤功能"""
        # 过滤小红书域名的Cookie
        domains = ["xiaohongshu.com", ".xiaohongshu.com"]
        filtered = account_manager._filter_platform_cookies(sample_cookies, domains)
        
        assert len(filtered) == 2
        assert filtered[0]["name"] == "session_id"
        assert filtered[1]["name"] == "user_token"
    
    def test_add_and_get_cookie_bundle(self, account_manager, sample_cookies):
        """测试添加 Cookie 组并读取"""
        cookie_id = account_manager.add_cookies("xiaohongshu", sample_cookies, name="cookie1")
        assert cookie_id is not None
        bundle = account_manager.get_cookie_bundle(cookie_id)
        assert bundle is not None
        assert bundle["platform_id"] == "xiaohongshu"
        assert len(bundle["cookies"]) == 2
        meta_list = account_manager.list_cookies("xiaohongshu")
        assert any(m["id"] == cookie_id for m in meta_list)

    def test_cookie_validity_and_prune(self, account_manager, sample_cookies):
        """测试 Cookie 有效性与过期清理"""
        # 有效 cookie
        cookie_id1 = account_manager.add_cookies("xiaohongshu", sample_cookies, name="valid")
        ok, msg = account_manager.check_cookie_validity(cookie_id1)
        assert ok is True
        # 过期 cookie（所有 expires 设为过去）
        expired = []
        for c in sample_cookies:
            c2 = dict(c)
            c2["expires"] = (datetime.now() - timedelta(days=1)).timestamp()
            expired.append(c2)
        cookie_id2 = account_manager.add_cookies("xiaohongshu", expired, name="expired")
        ok2, _ = account_manager.check_cookie_validity(cookie_id2)
        assert ok2 is False
        removed = account_manager.prune_expired_cookies()
        assert removed >= 1
        assert account_manager.get_cookie_bundle(cookie_id2) is None

    def test_merge_cookies(self, account_manager, sample_cookies):
        """测试合并多组 Cookie"""
        cookie_id1 = account_manager.add_cookies("xiaohongshu", sample_cookies, name="A")
        cookie_id2 = account_manager.add_cookies("xiaohongshu", sample_cookies, name="B")
        merged = account_manager.merge_cookies([cookie_id1, cookie_id2])
        # 两组相同 cookie 合并后按唯一键去重
        assert isinstance(merged, list)
        # 小红书相关的两条 cookie，合并仍为 2
        assert len([c for c in merged if c.get("domain") and "xiaohongshu" in c["domain"]]) == 2

    def test_detected_accounts(self, account_manager):
        """测试从 Cookie 检测账号信息"""
        cookies = [
            {"name": "uid", "value": "123", "domain": "xiaohongshu.com", "path": "/"},
            {"name": "username", "value": "tester", "domain": ".xiaohongshu.com", "path": "/"},
        ]
        cookie_id = account_manager.add_cookies("xiaohongshu", cookies, name="detected")
        bundle = account_manager.get_cookie_bundle(cookie_id)
        assert bundle is not None
        det = bundle.get("detected_accounts") or []
        assert len(det) == 1
        assert det[0]["id"] == "123"
        assert det[0]["name"] == "tester"