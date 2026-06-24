# -*- coding: utf-8 -*-
"""
新设计的百度翻译API组件
基于百度翻译API v3官方文档重新设计
"""

import os
import sys
import json
import hashlib
import random
import time
import requests
import logging

try:
    import winsound
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False
from typing import List, Dict, Optional, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewBaiduTranslator:
    """
    新设计的百度翻译API组件
    遵循百度翻译API最新规范，提供更可靠、高效的翻译服务
    """
    
    # 百度翻译API v3版本的基础URL
    BASE_URL_V3 = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    
    # 支持的语言列表
    SUPPORTED_LANGUAGES = {
        'auto': '自动检测',
        'zh': '中文',
        'en': '英语',
        'ja': '日语',
        'ko': '韩语',
        'fr': '法语',
        'de': '德语',
        'ru': '俄语',
        'es': '西班牙语',
        'pt': '葡萄牙语',
        'it': '意大利语'
    }
    
    def __init__(self, app_id: str = None, secret_key: str = None, **kwargs): # type: ignore
        """
        初始化翻译器

        Args:
            app_id: 百度翻译API的App ID（可选，优先级最高）
            secret_key: 百度翻译API的Secret Key（可选，优先级最高）
            **kwargs:
                timeout: 请求超时时间（秒）
                max_retries: 最大重试次数
                retry_delay: 重试间隔（秒）
                cache_file: 缓存文件路径
                batch_size: 批量翻译的批次大小
                rate_limit: 每秒最大请求数
                glossary_file: 翻译词表文件路径
        """

        # 构建账号池：可以轮换使用多组 app_id/secret_key
        # 优先级：显式传入 > 环境变量 > 内置三组
        self._credential_pool = []  # List[Tuple[app_id, secret_key]]

        # 1) 显式传入的账号
        if app_id and secret_key:
            self._credential_pool.append((app_id, secret_key))

        # 2) 环境变量中的账号（需要成对存在）
        env_app_id = os.getenv('BAIDU_APP_ID')
        env_secret_key = os.getenv('BAIDU_SECRET_KEY')
        if env_app_id and env_secret_key:
            self._credential_pool.append((env_app_id, env_secret_key))

        # 3) 内置的三组账号（按顺序作为兜底）
        builtin_credentials = [
            ("20251223002525145", "qJUjEIkakgbtv47sjIue"),
            ("20251223002525151", "Z2FonSZRW8gyR8urobCy"),
            ("20251204002512307", "1oLDEbYOeYlgw0I0wYU1"),
        ]
        self._credential_pool.extend(builtin_credentials)

        # 去重，保持顺序（避免同一账号重复添加）
        seen = set()
        uniq_pool = []
        for aid, sk in self._credential_pool:
            key = (aid, sk)
            if aid and sk and key not in seen:
                seen.add(key)
                uniq_pool.append((aid, sk))
        self._credential_pool = uniq_pool

        if not self._credential_pool:
            raise ValueError(
                "百度翻译API凭证未设置！请提供app_id和secret_key参数，或设置环境变量BAIDU_APP_ID和BAIDU_SECRET_KEY"
            )

        # 当前使用的账号索引（本次请求用哪个）
        self._current_cred_index = 0
        # 轮询用的索引（下一次请求用哪个）
        self._rr_index = 0
        self.app_id, self.secret_key = self._credential_pool[self._current_cred_index]

        # 为每个账号维护重试次数和禁用标记（仅在当前进程/本轮运行有效）
        self._cred_retry_counter = {i: 0 for i in range(len(self._credential_pool))}
        self._cred_disabled = set()

        logger.info(
            f"🔐 使用百度翻译账号 1/{len(self._credential_pool)}，App ID 前缀: {self.app_id[:8]}..."
        )
        
        # 配置参数
        self.timeout = kwargs.get('timeout', 30)  # 增加超时时间到30秒
        self.max_retries = kwargs.get('max_retries', 5)  # 增加最大重试次数到5次
        self.retry_delay = kwargs.get('retry_delay', 5)  # 增加重试延迟到5秒
        self.batch_size = kwargs.get('batch_size', 10)
        self.rate_limit = kwargs.get('rate_limit', 0.5)  # 进一步降低请求频率到每2秒1个请求，避免触发API限制
        self.glossary_file = kwargs.get('glossary_file', 'translation_glossary.json')
        
        # 初始化
        self._initialize()

    def _rotate_credential(self) -> bool:
        """切换到账号池中的下一组账号。

        Returns:
            是否成功切换到新的账号。
        """
        total = len(self._credential_pool)
        if total <= 1:
            return False

        old_index = self._current_cred_index
        # 在账号池中查找下一个未被禁用的账号
        for _ in range(total - 1):  # 最多尝试其它所有账号
            self._current_cred_index = (self._current_cred_index + 1) % total
            if self._current_cred_index not in self._cred_disabled:
                break

        # 如果没找到可用账号，或绕了一圈又回到原账号，则表示无可用账号
        if self._current_cred_index == old_index or self._current_cred_index in self._cred_disabled:
            # 再次确认是否所有账号均已禁用
            if len(self._cred_disabled) >= total:
                logger.error("⛔ 所有百度翻译账号重试次数均已达到上限(100)，程序将退出")
                sys.exit(1)
            return False

        self.app_id, self.secret_key = self._credential_pool[self._current_cred_index]
        # 同步更新轮询索引，避免后续调用又回到旧账号
        self._rr_index = (self._current_cred_index + 1) % total
        logger.warning(
            f"🔁 切换到下一组百度翻译账号: index={self._current_cred_index + 1}/{len(self._credential_pool)}, "
            f"App ID 前缀: {self.app_id[:8]}..."
        )
        return True

    def _increase_retry_for_current_cred(self):
        """当前账号的重试计数加一，超过上限则禁用该账号并在必要时退出程序。"""
        if not hasattr(self, "_cred_retry_counter"):
            return
        idx = getattr(self, "_current_cred_index", None)
        if idx is None or idx not in self._cred_retry_counter:
            return

        self._cred_retry_counter[idx] += 1
        count = self._cred_retry_counter[idx]

        if count >= 100 and idx not in self._cred_disabled:
            self._cred_disabled.add(idx)
            logger.error(
                f"⛔ 百度翻译账号 index={idx + 1}/{len(self._credential_pool)} 重试次数已达到 {count}，本轮运行中将不再使用该账号"
            )

            # 如果全部账号均被禁用，则直接退出程序
            if len(self._cred_disabled) >= len(self._credential_pool):
                logger.error("⛔ 所有百度翻译账号重试次数均已达到上限(100)，程序将退出")
                sys.exit(1)
        
    def _initialize(self):
        """初始化翻译器的内部状态"""
        # 请求计数和时间戳（用于控制请求频率）
        self.request_count = 0
        self.last_request_time = time.time()
        
        # 翻译词表（永久保存）
        self.translation_glossary = {}
        self.glossary_hit_count = 0
        self.error_count = 0
        self.translation_count = 0  # 新增：用于统计翻译次数
        
        # 加载词表
        self._load_glossary()
        
        logger.info(f"✅ 百度翻译API组件初始化成功")
        logger.info(f"   App ID: {self.app_id[:8]}...")
        logger.info(f"   词表大小: {len(self.translation_glossary)} 条记录")
    

    
    def _load_glossary(self):
        """加载翻译词表"""
        try:
            if os.path.exists(self.glossary_file):
                with open(self.glossary_file, 'r', encoding='utf-8') as f:
                    self.translation_glossary = json.load(f)
                logger.info(f"📚 加载词表成功，共 {len(self.translation_glossary)} 条记录")
        except Exception as e:
            logger.warning(f"⚠️ 加载词表失败: {e}")
            self.translation_glossary = {}
    
    def _save_glossary(self):
        """保存翻译词表"""
        try:
            with open(self.glossary_file, 'w', encoding='utf-8') as f:
                json.dump(self.translation_glossary, f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 词表已保存")
        except Exception as e:
            logger.warning(f"⚠️ 保存词表失败: {e}")
    
    def add_to_glossary(self, source_text: str, translated_text: str, from_lang: str = 'zh', to_lang: str = 'en'):
        """
        添加翻译对到词表
        
        Args:
            source_text: 源文本
            translated_text: 翻译后的文本
            from_lang: 源语言
            to_lang: 目标语言
        """
        if not source_text or not translated_text:
            return
            
        source_text = source_text.strip()
        translated_text = translated_text.strip()
        
        if not source_text or not translated_text:
            return
            
        self.translation_glossary[source_text] = translated_text
        self._save_glossary()
    
    def remove_from_glossary(self, source_text: str, from_lang: str = 'zh', to_lang: str = 'en'):
        """
        从词表中移除翻译对
        
        Args:
            source_text: 源文本
            from_lang: 源语言
            to_lang: 目标语言
        """
        source_text = source_text.strip()
        if source_text in self.translation_glossary:
            del self.translation_glossary[source_text]
            self._save_glossary()
    
    def clear_glossary(self):
        """清空翻译词表"""
        self.translation_glossary = {}
        self._save_glossary()
        logger.info("🗑️  翻译词表已清空")
    
    def get_glossary_size(self):
        """获取词表大小"""
        return len(self.translation_glossary)
    

    
    def import_glossary(self, glossary_file: str, overwrite: bool = False) -> Dict:
        """
        从外部文件导入词表
        
        Args:
            glossary_file: 词表文件路径
            overwrite: 是否覆盖现有词表
            
        Returns:
            导入结果统计信息
        """
        logger.info(f"📥 开始导入词表: {glossary_file}")
        
        # 初始化统计信息
        stats = {
            'imported_entries': 0,
            'already_in_glossary': 0,
            'total_entries': 0
        }
        
        try:
            with open(glossary_file, 'r', encoding='utf-8') as f:
                imported_glossary = json.load(f)
            
            stats['total_entries'] = len(imported_glossary)
            
            # 如果覆盖现有词表，先清空
            if overwrite:
                self.clear_glossary()
            
            # 遍历导入的词表条目
            for glossary_key, translated_text in imported_glossary.items():
                if glossary_key in self.translation_glossary:
                    stats['already_in_glossary'] += 1
                else:
                    self.translation_glossary[glossary_key] = translated_text
                    stats['imported_entries'] += 1
            
            # 保存词表
            self._save_glossary()
            
            logger.info(f"✅ 词表导入完成")
            logger.info(f"   导入文件总条目: {stats['total_entries']}")
            logger.info(f"   新增到词表: {stats['imported_entries']} 条")
            logger.info(f"   已存在于词表: {stats['already_in_glossary']} 条")
            logger.info(f"   词表当前大小: {len(self.translation_glossary)} 条")
            
        except Exception as e:
            logger.error(f"❌ 词表导入失败: {e}")
            stats['error'] = str(e) # type: ignore
        
        return stats
    
    def export_glossary(self, export_file: str) -> bool:
        """
        导出词表到外部文件
        
        Args:
            export_file: 导出文件路径
            
        Returns:
            是否导出成功
        """
        try:
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(self.translation_glossary, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📤 词表导出成功: {export_file}")
            logger.info(f"   导出条目数: {len(self.translation_glossary)}")
            return True
        except Exception as e:
            logger.error(f"❌ 词表导出失败: {e}")
            return False
    
    def _generate_sign(self, text: str, salt: str) -> str:
        """
        生成API请求签名
        签名规则：MD5(app_id + text + salt + secret_key)
        
        Args:
            text: 待翻译文本
            salt: 随机数
            
        Returns:
            生成的签名
        """
        sign_str = f"{self.app_id}{text}{salt}{self.secret_key}"
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    def _check_rate_limit(self):
        """检查并控制请求频率"""
        current_time = time.time()
        time_elapsed = current_time - self.last_request_time
        
        # 计算平均请求间隔时间（秒）
        avg_interval = 1.0 / self.rate_limit if self.rate_limit > 0 else 1.0
        
        # 如果两次请求间隔小于平均间隔时间，等待
        if time_elapsed < avg_interval:
            wait_time = avg_interval - time_elapsed
            logger.debug(f"⏱️  请求频率过高，等待 {wait_time:.2f} 秒")
            time.sleep(wait_time)
            self.last_request_time = time.time()
        else:
            self.last_request_time = time.time()
        
        self.request_count += 1
    
    def _handle_api_response(self, response: requests.Response) -> Dict:
        """
        处理API响应
        
        Args:
            response: API响应对象
            
        Returns:
            解析后的响应数据
        """
        try:
            response.raise_for_status()
            result = response.json()
            
            # 检查是否有错误
            if 'error_code' in result:
                error_code = result['error_code']
                error_msg = result.get('error_msg', '未知错误')
                # 直接使用API返回的错误码
                raise ApiError(error_code, error_msg)
            
            return result
        except requests.exceptions.HTTPError as e:
            # 尝试解析响应内容获取详细错误信息
            try:
                error_data = response.json()
                error_code = error_data.get('error_code', 'HTTP_ERROR')
                error_msg = error_data.get('error_msg', str(e))
                raise ApiError(error_code, error_msg)
            except:
                raise ApiError('HTTP_ERROR', str(e))
        except json.JSONDecodeError:
            raise ApiError('JSON_DECODE_ERROR', '响应解析失败')
        except Exception as e:
            # 检查是否已经是ApiError异常
            if isinstance(e, ApiError):
                raise
            raise ApiError('UNKNOWN_ERROR', str(e))
    
    def translate(self, text: str, from_lang: str = 'auto', to_lang: str = 'zh', add_to_glossary: bool = False) -> str:
        """
        翻译单个文本
        
        Args:
            text: 待翻译文本
            from_lang: 源语言（默认自动检测）
            to_lang: 目标语言（默认中文）
            add_to_glossary: 是否将翻译结果添加到词表
            
        Returns:
            翻译后的文本
        """
        if not text or not isinstance(text, str):
            return text
        
        # 去除首尾空白
        text = text.strip()
        if not text:
            return text
        
        # 检查是否包含中文字符（如果目标语言是中文，跳过翻译）
        if to_lang == 'zh' and self._contains_chinese(text):
            return text
        
        # 检查词表（优先级最高）
        if text in self.translation_glossary:
            self.glossary_hit_count += 1
            logger.debug(f"📖 词表命中: '{text}' → '{self.translation_glossary[text]}'")
            return self.translation_glossary[text]

        # 每次调用按顺序轮换账号（跳过已禁用账号）
        if self._credential_pool:
            total = len(self._credential_pool)
            disabled = getattr(self, "_cred_disabled", set())

            if len(disabled) >= total:
                logger.error("⛔ 所有百度翻译账号重试次数均已达到上限(100)，程序将退出")
                sys.exit(1)

            idx = getattr(self, "_rr_index", 0) % total
            start_idx = idx
            while idx in disabled:
                idx = (idx + 1) % total
                if idx == start_idx:
                    logger.error("⛔ 所有百度翻译账号重试次数均已达到上限(100)，程序将退出")
                    sys.exit(1)

            self._current_cred_index = idx
            self.app_id, self.secret_key = self._credential_pool[self._current_cred_index]
            # 更新下次调用的轮询索引
            self._rr_index = (self._current_cred_index + 1) % total
            logger.info(
                f"🔐 本次使用百度翻译账号 index={self._current_cred_index + 1}/{len(self._credential_pool)}, "
                f"App ID 前缀: {self.app_id[:8]}..."
            )

        # 控制请求频率
        self._check_rate_limit()
        
        # 重试机制
        for attempt in range(self.max_retries):
            need_retry = False
            try:
                salt = str(random.randint(32768, 65536))
                sign = self._generate_sign(text, salt)
                
                params = {
                    'q': text,
                    'from': from_lang,
                    'to': to_lang,
                    'appid': self.app_id,
                    'salt': salt,
                    'sign': sign
                }
                
                logger.debug(f"📤 翻译请求: '{text}' -> {from_lang} → {to_lang}")
                response = requests.get(
                    self.BASE_URL_V3,
                    params=params,
                    timeout=self.timeout
                )
                
                # 处理响应
                result = self._handle_api_response(response)
                
                # 解析翻译结果
                if 'trans_result' in result and len(result['trans_result']) > 0:
                    translated_text = result['trans_result'][0]['dst']
                    
                    # 如果需要，将翻译结果添加到词表
                    if add_to_glossary:
                        self.add_to_glossary(text, translated_text, from_lang, to_lang)
                    
                    logger.debug(f"📥 翻译成功: '{text}' → '{translated_text}'")
                    return translated_text
                else:
                    raise ApiError('EMPTY_RESULT', '翻译结果为空')
                    
            except ApiError as e:
                logger.warning(f"⚠️ 翻译失败 [{attempt + 1}/{self.max_retries}]: {e}")
                
                # 如果是认证错误或请求参数错误，尝试切换账号后重试
                if e.error_code in ['52003', '54001', '54000', '58001']:
                    logger.error(f"❌ 致命错误或账号问题: {e}")
                    # 当前账号计一次重试
                    self._increase_retry_for_current_cred()
                    # 尝试切换到账号池中的下一组账号
                    if self._rotate_credential():
                        logger.info("🔁 尝试使用下一组账号重新翻译")
                        # 继续下一轮重试（使用新的账号）
                        continue
                    # 如果无法切换账号，只能返回原文本
                    logger.error("❌ 所有账号均不可用，返回原文本")
                    return text
                    
                # 如果是请求频率过高或额度限制，增加等待时间并重试
                if e.error_code in ['54003', '54005']:
                    # 当前账号计一次重试
                    self._increase_retry_for_current_cred()
                    # 出现重试时发出提示音
                    try:
                        if _HAS_WINSOUND:
                            winsound.Beep(1000, 500)  # 1kHz, 0.5 秒
                        else:
                            print('\a', end='', flush=True)  # 终端蜂鸣
                    except Exception:
                        pass

                    # 指数退避：(2^attempt) * 基础延迟时间 * 3
                    wait_time = min((2 ** attempt) * self.retry_delay * 3, 120)  # 最大延迟不超过120秒
                    logger.info(f"⏱️  API调用频率过高或额度限制，等待 {wait_time} 秒后重试")
                    time.sleep(wait_time)
                    continue
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ 翻译超时 [{attempt + 1}/{self.max_retries}]")
                need_retry = True
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️ 网络连接错误 [{attempt + 1}/{self.max_retries}]")
                need_retry = True
            except requests.exceptions.RequestException as e:
                # 捕获所有requests相关异常（包括连接错误、超时等）
                logger.warning(f"⚠️ 网络请求错误 [{attempt + 1}/{self.max_retries}]: {e}")
                need_retry = True
            except Exception as e:
                logger.warning(f"⚠️ 未知错误 [{attempt + 1}/{self.max_retries}]: {e}")
                need_retry = True
            
            # 重试前等待 - 实现指数退避策略
            if attempt < self.max_retries - 1 and need_retry:
                # 当前账号计一次重试
                self._increase_retry_for_current_cred()
                # 指数退避：(2^attempt) * 基础延迟时间
                wait_time = min((2 ** attempt) * self.retry_delay, 60)  # 最大延迟不超过60秒
                logger.debug(f"⏱️  等待 {wait_time} 秒后重试")
                time.sleep(wait_time)
        
        # 所有重试都失败
        logger.error(f"❌ 翻译失败（所有重试）: '{text}'")
        self.error_count += 1
        return text
    
    def batch_translate(self, texts: List[str], from_lang: str = 'auto', to_lang: str = 'zh', add_to_glossary: bool = False) -> List[str]:
        """
        批量翻译文本列表
        
        Args:
            texts: 待翻译文本列表
            from_lang: 源语言（默认自动检测）
            to_lang: 目标语言（默认中文）
            add_to_glossary: 是否将翻译结果添加到词表
            
        Returns:
            翻译后的文本列表
        """
        if not texts:
            return []
        
        logger.info(f"📋 开始批量翻译，共 {len(texts)} 条文本")
        logger.info(f"   源语言: {from_lang} → 目标语言: {to_lang}")
        
        translated_texts = []
        
        # 分批处理
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            # 翻译批次
            batch_translated = []
            for text in batch:
                translated_text = self.translate(text, from_lang, to_lang, add_to_glossary)
                batch_translated.append(translated_text)
            
            translated_texts.extend(batch_translated)
            
            # 显示进度
            progress = min(i + self.batch_size, len(texts))
            logger.info(f"   进度: {progress}/{len(texts)} ({progress / len(texts) * 100:.1f}%)")
        
        logger.info(f"✅ 批量翻译完成")
        logger.info(f"   翻译成功: {len(translated_texts)} 条")
        logger.info(f"   词表命中: {self.glossary_hit_count} 次")
        logger.info(f"   翻译次数: {self.translation_count} 次")
        logger.info(f"   错误次数: {self.error_count} 次")
        
        return translated_texts
    
    def _contains_chinese(self, text: str) -> bool:
        """检查文本是否包含中文字符"""
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    

    
    def print_stats(self):
        """打印翻译统计信息"""
        logger.info("📊 翻译统计信息:")
        logger.info(f"   翻译次数: {self.translation_count}")
        logger.info(f"   词表命中: {self.glossary_hit_count}")
        logger.info(f"   错误次数: {self.error_count}")
        logger.info(f"   词表大小: {len(self.translation_glossary)} 条记录")
    
    def get_stats(self):
        """获取翻译统计信息"""
        return {
            'total_translations': self.translation_count,
            'glossary_hits': self.glossary_hit_count,
            'error_count': self.error_count,
            'glossary_size': len(self.translation_glossary)
        }
    
    def _test_api_connection(self):
        """测试API连接是否正常"""
        try:
            # 翻译一个简单的文本测试API连接
            result = self.translate("test", from_lang="en", to_lang="zh")
            logger.info("✅ API连接测试成功")
            return True
        except Exception as e:
            logger.error(f"❌ API测试失败 [{e.error_code if hasattr(e, 'error_code') else 'UNKNOWN'}]: {str(e)}") # type: ignore
            return False
    
    def translate_keyword_with_retry(self, keyword):
        """带重试的关键词翻译"""
        try:
            result = self.translate(keyword)
            return result, True
        except Exception as e:
            logger.warning(f"⚠️ 关键词翻译失败: {keyword} - {e}")
            return keyword, False
    
    def batch_translate_safe(self, keywords):
        """安全的批量翻译方法"""
        try:
            return self.batch_translate(keywords)
        except Exception as e:
            logger.warning(f"⚠️ 批量翻译失败: {e}")
            # 返回原始关键词
            return keywords
    
    def __del__(self):
        """析构函数"""
        # 保存词表
        self._save_glossary()


class ApiError(Exception):
    """百度翻译API错误异常类"""
    
    def __init__(self, error_code: str, error_msg: str):
        self.error_code = error_code
        self.error_msg = error_msg
        super().__init__(f"[{error_code}] {error_msg}")


# 示例用法
if __name__ == "__main__":
    try:
        # 创建翻译器实例
        translator = NewBaiduTranslator()
        
        # 测试单个翻译
        logger.info("\n1. 测试单个翻译:")
        result = translator.translate("Hello, World!")
        logger.info(f"   'Hello, World!' -> '{result}'")
        
        # 测试批量翻译
        logger.info("\n2. 测试批量翻译:")
        keywords = ["machine learning", "artificial intelligence", "大数据", "深度学习", "blockchain"]
        results = translator.batch_translate(keywords)
        for keyword, result in zip(keywords, results):
            logger.info(f"   '{keyword}' -> '{result}'")
        
        # 打印统计信息
        logger.info("\n3. 翻译统计信息:")
        translator.print_stats()
        
    except Exception as e:
        logger.error(f"❌ 示例运行失败: {e}")