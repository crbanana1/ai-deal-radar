# coding=utf-8
"""AI 羊毛关键词规则的回归测试。"""

import unittest
from pathlib import Path

from trendradar.core.frequency import load_frequency_words, matches_word_groups

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = ROOT / "config" / "frequency_words.txt"


class AiWoolKeywordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups, cls.filters, cls.global_filters = load_frequency_words(str(KEYWORDS))

    def assert_deal(self, title):
        self.assertTrue(
            matches_word_groups(title, self.groups, self.filters, self.global_filters),
            title,
        )

    def assert_noise(self, title):
        self.assertFalse(
            matches_word_groups(title, self.groups, self.filters, self.global_filters),
            title,
        )

    def test_free_credits_and_trials(self):
        self.assert_deal("WorkBuddy国际版接入DeepSeek新模型，限时免费至10月31日")
        self.assert_deal("通义千问 API 免费额度翻倍")
        self.assert_deal("腾讯云：2027年1月1日起正式开启按实例维度免费赠送标准带宽")

    def test_student_and_developer_benefits(self):
        self.assert_deal("智谱 GLM 学生认证免费领取额度")
        self.assert_deal("讯飞星火开发者计划赠送算力券")

    def test_price_cuts(self):
        self.assert_deal("DeepSeek API 降价 50%")
        self.assert_deal("豆包大模型限时优惠，充值送额度")

    def test_editorial_and_policy_noise(self):
        self.assert_noise("科大讯飞1024将展示全国产AI赋能教育、医疗、办公等领域新进展")
        self.assert_noise("商汤前副总裁创业押注企业智能体，成立三个月融资超千万美元")
        self.assert_noise("青岛实施留学人员创新创业“千帆行动”")
        self.assert_noise("百行Python代码打造本地代理：用上免费模型")

    def test_hiring_and_roundups(self):
        self.assert_noise("招聘 AI 工程师，免费三餐")
        self.assert_noise("【每日瞰AI】DeepSeek恢复，向用户赠送补偿金")


if __name__ == "__main__":
    unittest.main()
