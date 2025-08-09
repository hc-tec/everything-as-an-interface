import logging
import json
import base64
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("account_manager")

class AccountManager:
    """基于 Cookie 的账号管理器：负责管理各平台的登录 Cookie 集合"""

    def __init__(self, master_key: Optional[str] = None, storage_path: str = "./accounts"):
        """
        初始化 Cookie 管理器

        Args:
            master_key: 主密钥，用于加密本地 Cookie 存储
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.platforms: Dict[str, Dict[str, Any]] = {}
        # cookies_by_id: {cookie_id: cookie_bundle}
        self.cookies_by_id: Dict[str, Dict[str, Any]] = {}

        os.makedirs(storage_path, exist_ok=True)

        self._init_encryption(master_key)
        self._load_platforms()
        self._load_cookies()
        # 自动清理过期 Cookie
        try:
            removed = self.prune_expired_cookies()
            if removed:
                logger.info(f"启动时已清理过期 Cookie 数量: {removed}")
        except Exception:
            pass

    def _init_encryption(self, master_key: Optional[str]) -> None:
        if master_key:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"everything-as-an-interface",
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        else:
            key = Fernet.generate_key()
        self.cipher = Fernet(key)
        logger.info("加密系统已初始化")

    def _load_platforms(self) -> None:
        platform_file = os.path.join(self.storage_path, "platforms.json")
        if os.path.exists(platform_file):
            try:
                with open(platform_file, "r", encoding="utf-8") as f:
                    self.platforms = json.load(f)
                logger.info(f"已加载 {len(self.platforms)} 个平台定义")
            except Exception as e:
                logger.error(f"加载平台定义失败: {str(e)}")
                self.platforms = {}
        else:
            self.platforms = {
                "xiaohongshu": {
                    "name": "小红书",
                    "icon": "xiaohongshu.png",
                    "cookie_domains": ["xiaohongshu.com", ".xiaohongshu.com"],
                    "login_url": "https://www.xiaohongshu.com/login",
                    "requires_login": True
                },
                "weibo": {
                    "name": "微博",
                    "icon": "weibo.png",
                    "cookie_domains": ["weibo.com", ".weibo.com"],
                    "login_url": "https://weibo.com/login.php",
                    "requires_login": True
                },
                "bilibili": {
                    "name": "哔哩哔哩",
                    "icon": "bilibili.png",
                    "cookie_domains": ["bilibili.com", ".bilibili.com"],
                    "login_url": "https://passport.bilibili.com/login",
                    "requires_login": True
                }
            }
            self._save_platforms()

    def _save_platforms(self) -> None:
        platform_file = os.path.join(self.storage_path, "platforms.json")
        try:
            with open(platform_file, "w", encoding="utf-8") as f:
                json.dump(self.platforms, f, ensure_ascii=False, indent=2)
            logger.info("平台定义已保存")
        except Exception as e:
            logger.error(f"保存平台定义失败: {str(e)}")

    def _load_cookies(self) -> None:
        """加载本地 Cookie 集合"""
        file_path = os.path.join(self.storage_path, "cookies.enc")
        if not os.path.exists(file_path):
            self.cookies_by_id = {}
            return
        try:
            with open(file_path, "rb") as f:
                encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            data = json.loads(decrypted.decode("utf-8"))
            # 允许历史结构为空
            self.cookies_by_id = data if isinstance(data, dict) else {}
            logger.info(f"已加载 {len(self.cookies_by_id)} 组 Cookie, {self.cookies_by_id.keys()}")
        except Exception as e:
            logger.error(f"加载 Cookie 存储失败: {str(e)}")
            self.cookies_by_id = {}

    def _save_cookies(self) -> None:
        """保存本地 Cookie 集合"""
        try:
            serialized = json.dumps(self.cookies_by_id, ensure_ascii=False)
            encrypted = self.cipher.encrypt(serialized.encode("utf-8"))
            with open(os.path.join(self.storage_path, "cookies.enc"), "wb") as f:
                f.write(encrypted)
            logger.info("Cookie 存储已保存")
        except Exception as e:
            logger.error(f"保存 Cookie 存储失败: {str(e)}")

    def add_platform(self, platform_id: str, name: str, cookie_domains: List[str], login_url: str,
                     requires_login: bool = True, icon: Optional[str] = None) -> bool:
        if platform_id in self.platforms:
            logger.warning(f"平台已存在: {platform_id}")
            return False
        self.platforms[platform_id] = {
            "name": name,
            "icon": icon or f"{platform_id}.png",
            "cookie_domains": cookie_domains,
            "login_url": login_url,
            "requires_login": requires_login,
        }
        self._save_platforms()
        logger.info(f"添加平台: {platform_id} ({name})")
        return True

    def remove_platform(self, platform_id: str) -> bool:
        if platform_id in self.platforms:
            del self.platforms[platform_id]
            self._save_platforms()
            logger.info(f"移除平台: {platform_id}")
            return True
        return False

    def get_platform(self, platform_id: str) -> Optional[Dict[str, Any]]:
        return self.platforms.get(platform_id)

    def get_all_platforms(self) -> List[Dict[str, Any]]:
        result = []
        for pid, p in self.platforms.items():
            d = p.copy()
            d["id"] = pid
            result.append(d)
        return result

    def _filter_platform_cookies(self, cookies: List[Dict[str, Any]], domains: List[str]) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for cookie in cookies:
            domain = cookie.get("domain")
            if not domain:
                continue
            if any(domain.endswith(d) for d in domains):
                filtered.append(cookie)
        return filtered

    def add_cookies(self, platform_id: str, cookies: List[Dict[str, Any]], name: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """新增一组 Cookie（表示一个网站的登录状态）"""
        platform = self.get_platform(platform_id)
        if not platform:
            logger.error(f"添加 Cookie 失败: 平台 {platform_id} 不存在")
            return None

        relevant_cookies = self._filter_platform_cookies(cookies, platform.get("cookie_domains", []))
        if not relevant_cookies:
            logger.error("添加 Cookie 失败: 未找到平台相关 Cookie")
            return None

        cookie_id = str(uuid.uuid4())
        bundle = {
            "id": cookie_id,
            "platform_id": platform_id,
            "name": name or f"{platform['name']}登录",
            "cookies": relevant_cookies,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "status": "valid",
            "detected_accounts": self._detect_accounts_from_cookies(relevant_cookies),
            "metadata": metadata or {},
        }
        self.cookies_by_id[cookie_id] = bundle
        self._save_cookies()
        logger.info(f"新增 Cookie 组: {cookie_id} (平台: {platform_id})")
        return cookie_id

    def update_cookie_cookies(self, cookie_id: str, cookies: List[Dict[str, Any]]) -> bool:
        """更新已有 Cookie 组中的 Cookie 列表"""
        bundle = self.cookies_by_id.get(cookie_id)
        if not bundle:
            logger.error(f"更新 Cookie 失败: 组 {cookie_id} 不存在")
            return False
        platform = self.get_platform(bundle["platform_id"]) or {}
        relevant_cookies = self._filter_platform_cookies(cookies, platform.get("cookie_domains", []))
        if not relevant_cookies:
            logger.error("更新 Cookie 失败: 未找到平台相关 Cookie")
            return False
        bundle["cookies"] = relevant_cookies
        bundle["status"] = "valid"
        bundle["detected_accounts"] = self._detect_accounts_from_cookies(relevant_cookies)
        self._save_cookies()
        logger.info(f"更新 Cookie 组: {cookie_id}")
        return True

    def get_cookie_bundle(self, cookie_id: str) -> Optional[Dict[str, Any]]:
        bundle = self.cookies_by_id.get(cookie_id)
        if not bundle:
            return None
        # 更新使用时间与有效性
        bundle["last_used"] = datetime.now().isoformat()
        valid, _ = self.check_cookie_validity(cookie_id)
        if not valid:
            # 按需删除过期 Cookie
            try:
                del self.cookies_by_id[cookie_id]
                self._save_cookies()
            except Exception:
                pass
            return None
        self._save_cookies()
        return bundle

    def get_cookie_cookies(self, cookie_id: str) -> Optional[List[Dict[str, Any]]]:
        valid, _ = self.check_cookie_validity(cookie_id)
        if not valid:
            return None
        bundle = self.cookies_by_id.get(cookie_id)
        return (bundle or {}).get("cookies")

    def list_cookies(self, platform_id: Optional[str] = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for b in self.cookies_by_id.values():
            if platform_id and b.get("platform_id") != platform_id:
                continue
            items.append(self._safe_cookie_info(b))
        return items

    def remove_cookie(self, cookie_id: str) -> bool:
        if cookie_id in self.cookies_by_id:
            del self.cookies_by_id[cookie_id]
            self._save_cookies()
            logger.info(f"移除 Cookie 组: {cookie_id}")
            return True
        return False

    def merge_cookies(self, cookie_ids: List[str]) -> List[Dict[str, Any]]:
        """合并多组 Cookie，用于在浏览器中一次性注入多站点登录"""
        merged: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        for cid in cookie_ids:
            bundle = self.cookies_by_id.get(cid)
            if not bundle or not bundle.get("cookies"):
                continue
            for ck in bundle["cookies"]:
                key = (ck.get("name", ""), ck.get("domain", ""), ck.get("path", "/"))
                merged[key] = ck
        return list(merged.values())

    def check_cookie_validity(self, cookie_id: str) -> Tuple[bool, str]:
        """基于 Cookie 的 expires 字段进行有效性判断"""
        bundle = self.cookies_by_id.get(cookie_id)
        if not bundle:
            return False, "Cookie 组不存在"
        cookies = bundle.get("cookies") or []
        if not cookies:
            return False, "无 Cookie 内容"
        # 统计有 expires 的 cookie 中的过期比例
        has_expires = [c for c in cookies if c.get("expires") is not None]
        if not has_expires:
            # 无显式过期时间，视为未知但有效，由站点自行判定
            return True, "有效（无明确过期）"
        now_ts = datetime.now().timestamp()
        expired_count = sum(1 for c in has_expires if float(c.get("expires", 0)) < now_ts)
        ratio = expired_count / max(1, len(has_expires))
        if ratio >= 0.8:  # 80% 的可过期 Cookie 已过期，认为整组失效
            return False, "Cookie 已过期"
        return True, "Cookie 有效"

    def prune_expired_cookies(self) -> int:
        """清理过期的 Cookie 组，返回删除数量"""
        to_delete: List[str] = []
        for cid in list(self.cookies_by_id.keys()):
            valid, _ = self.check_cookie_validity(cid)
            if not valid:
                to_delete.append(cid)
        for cid in to_delete:
            del self.cookies_by_id[cid]
        if to_delete:
            self._save_cookies()
        return len(to_delete)

    def _safe_cookie_info(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        info = {k: v for k, v in bundle.items() if k != "cookies"}
        info["has_cookies"] = bool(bundle.get("cookies"))
        info["cookie_count"] = len(bundle.get("cookies", []))
        platform = self.get_platform(bundle.get("platform_id", ""))
        info["platform_name"] = (platform or {}).get("name", bundle.get("platform_id"))
        return info

    def _detect_accounts_from_cookies(self, cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """通过常见 Cookie 键名从 Cookie 中提取账号标识，用于告知有哪些账号已登录"""
        id_keys = {"uid", "user_id", "userid", "mid", "DedeUserID", "aid"}
        name_keys = {"username", "user_name", "nick", "nickname", "uname"}
        found: Dict[str, Dict[str, Any]] = {}
        for c in cookies:
            name = c.get("name")
            value = c.get("value")
            if not name:
                continue
            if name in id_keys:
                entry = found.get("default") or {"id": None, "name": None}
                entry["id"] = value
                found["default"] = entry
            if name in name_keys:
                entry = found.get("default") or {"id": None, "name": None}
                entry["name"] = value
                found["default"] = entry
        results: List[Dict[str, Any]] = []
        if "default" in found:
            entry = found["default"]
            if entry["id"] or entry["name"]:
                results.append({
                    "id": entry["id"],
                    "name": entry["name"],
                    "detected_at": datetime.now().isoformat(),
                })
        return results