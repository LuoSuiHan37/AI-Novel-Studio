from __future__ import annotations

from typing import Mapping


WORK_TAG_CATALOG: dict[str, tuple[str, ...]] = {
    "style": ("热血", "轻松", "暗黑", "现实题材", "虐恋", "治愈", "甜宠", "悬疑", "种田", "清穿", "宅斗", "宫斗", "中短篇", "青春", "军事", "爽文", "恐怖", "烧脑", "正剧", "商战", "权谋", "励志", "搞笑", "日常", "短篇", "短故事", "买股文", "第一人称", "纯爱", "快节奏", "反套路", "新闻现实题材", "国安现实题材"),
    "role": ("豪门总裁", "男主", "女主", "兵王", "护花高手", "仙帝", "学生", "婆妈", "神豪", "奶爸", "皇帝", "道士", "女总裁", "校花", "皇后", "王妃", "医妃", "公主", "嫡女", "庶女", "王爷", "太子", "首辅", "丑女", "大叔", "医生", "律师", "吸血鬼", "特工", "法医", "作死", "女配", "全能", "杀伐果断", "霸道", "偏执", "忠犬", "残疾", "毒舌", "傲娇", "病娇", "萌宝", "龙", "僵尸", "欢喜冤家", "师徒恋", "弃少", "战神", "强强", "魔尊", "团宠", "特种兵", "暴君", "皇叔", "皇子", "摄政王", "奸臣", "世子", "锦衣卫", "太监", "女帝", "明星", "老师", "校草", "侦探", "警察", "主播", "少年", "师兄", "领主", "温柔", "呆萌", "可盐可甜", "娇媚", "绿茶", "铁血", "败家子", "弃妇", "女扮男装", "女尊", "女强", "替身", "二婚", "姐姐", "学霸", "天才", "杀手", "将军", "腹黑", "废柴", "反派", "扮猪吃虎", "智商在线", "真假千金", "咸鱼", "锦鲤", "小众职业", "双女主", "后妈", "哥哥", "黑莲花", "黑月光", "白月光", "书生", "糙汉", "老干部", "渔女", "丞相", "驸马", "双洁", "作精", "外卖员", "丫鬟", "恶婆婆", "幕后BOSS", "奶团", "大女主", "主母", "妾室", "人间清醒", "无节操", "嘴炮", "痴情", "超A", "高冷", "财迷", "醋王", "万人迷", "戏精", "炮灰", "吃货", "旺夫", "美强惨", "顶流", "小狼狗", "反差萌", "心机", "暖男", "逗比", "毒医", "厨娘", "冰山", "古灵精怪", "宠妻", "黑化", "独宠", "御姐", "佛系", "神医", "真假少爷"),
    "plot": ("鉴宝", "剑道", "透视", "美食", "无敌流", "争霸", "召唤", "盗墓", "快穿", "穿书", "随身空间", "契约婚姻", "娱乐圈", "穿越", "荒岛求生", "家族崛起", "豪门恩怨", "身份反转", "逆袭", "强者回归", "一统天下", "直播", "聊天群", "红包", "御兽", "血脉", "武魂", "丹药", "风水", "青梅竹马", "破镜重圆", "替嫁", "闪婚", "隐婚", "进化", "吞噬", "影视", "无限流", "马甲", "开局流", "签到", "同人", "体育", "官场", "神祇", "修仙", "古穿今", "性转", "HE", "BE", "1V1", "姐弟恋", "相爱相杀", "追妻火葬场", "打脸虐渣", "暗恋", "日久生情", "一见钟情", "带球跑", "职场", "金手指", "异能", "技术流", "全球", "基建", "求生", "丧尸", "机甲", "网游", "游戏", "电竞", "篮球", "足球", "推理", "探险", "怪谈", "长生流", "国术", "古武", "战争", "魔法", "经典衍生", "奇闻异事", "前世今生", "重生", "系统", "复仇", "读心术", "恋综", "双男主", "无CP", "非典型修仙", "双重生", "诡异流", "爱国流", "单元故事", "迪化流", "灵魂互换", "克苏鲁", "稳健流", "扮演", "双向奔赴", "科技", "男二上位", "无女主", "单女主", "离婚后", "逃荒", "国运", "钓鱼", "恋爱", "群穿", "都市脑洞", "玄幻脑洞", "历史脑洞", "港综", "记忆曝光", "囤物资", "玄学", "模拟器", "相亲", "综艺", "规则怪谈", "黑道", "军婚", "谍战", "股海风云", "综武", "全家火葬场", "多女主", "多重人格", "全民", "宠夫", "NBA", "通古今", "全民领主", "草根崛起", "氪金", "荒野求生", "死对头", "天才之合", "婚恋", "双向救赎", "萌宠", "爆红", "失忆", "倒追", "修罗场", "崩人设", "偷听心声", "父子火葬场", "后悔流", "弹幕文", "万物沟通", "影视原著", "现代言情"),
    "background": ("都市", "现代言情", "诸天万界", "三国", "大唐", "水浒", "西游", "漫威", "火影", "海贼王", "英雄联盟", "绝地求生", "王者荣耀", "武侠", "灵气复苏", "神奇宝贝", "奥特曼", "末世", "洪荒", "玄幻", "仙侠", "异界", "西幻", "奇幻", "年代", "民国", "校园", "古代", "架空历史", "远古", "星际", "历史", "大明", "乡村", "未来世界", "科幻", "精灵鬼怪", "红楼", "封神", "天庭", "卡牌", "神话", "哈利波特", "假面骑士", "龙珠", "游戏衍生", "动漫衍生", "影视衍生", "古代言情", "幻想言情", "高武", "四合院", "兽世", "大秦", "原神", "我的世界", "铠甲勇士", "超神学院", "柯南", "抗战", "宋朝", "赛博朋克", "惊悚世界", "崩坏星穹铁道", "衍生言情", "传统玄幻"),
}


def validate_work_tags(value: Mapping[str, list[str]] | None, *, allow_empty: bool = True) -> dict[str, list[str]]:
    """Normalize optional work tags without letting stale catalog values block creation.

    Tags can be persisted in drafts or returned by an older model/catalog version.
    Unknown values and categories are intentionally dropped. Structural validation
    still applies to known values, and a genuinely missing required category remains
    an error when ``allow_empty`` is false.
    """
    tags = value or {}
    normalized: dict[str, list[str]] = {}
    for category, catalog in WORK_TAG_CATALOG.items():
        raw_selected = list(dict.fromkeys(item.strip() for item in tags.get(category, []) if item.strip()))
        selected = [item for item in raw_selected if item in catalog]
        if len(selected) > 3:
            raise ValueError(f"{category} 标签最多选择 3 个")
        if not allow_empty and not selected and not raw_selected:
            raise ValueError(f"{category} 标签必须选择 1–3 个")
        normalized[category] = selected
    return normalized


def default_work_tags(genre: str) -> dict[str, list[str]]:
    if genre == "billionaire_romance":
        return {"style": ["甜宠"], "role": ["豪门总裁"], "plot": ["豪门恩怨"], "background": ["都市"]}
    if genre == "sci_fi_apocalypse":
        return {"style": ["爽文"], "role": ["全能"], "plot": ["末世", "求生", "进化"], "background": ["科幻", "末世"]}
    if genre == "mystery_what_if":
        return {"style": ["悬疑", "烧脑"], "role": ["侦探"], "plot": ["规则怪谈", "求生"], "background": ["惊悚世界"]}
    if genre == "showbiz_romance":
        return {"style": ["甜宠", "轻松"], "role": ["明星"], "plot": ["娱乐圈", "恋爱"], "background": ["都市"]}
    if genre == "workplace_romance":
        return {"style": ["甜宠", "现实题材"], "role": ["女主"], "plot": ["职场", "婚恋"], "background": ["都市", "现代言情"]}
    if genre == "republican_romance":
        return {"style": ["正剧", "虐恋"], "role": ["将军"], "plot": ["军婚", "身份反转"], "background": ["民国"]}
    if genre == "youth_sweet":
        return {"style": ["青春", "甜宠"], "role": ["学生"], "plot": ["青梅竹马", "恋爱"], "background": ["校园"]}
    if genre == "ancient_romance_what_if":
        return {"style": ["爽文", "宅斗"], "role": ["王爷"], "plot": ["穿书", "重生"], "background": ["古代言情"]}
    if "romance" in genre:
        return {"style": ["甜宠"], "role": ["女主"], "plot": ["现代言情"], "background": ["都市"]}
    return {"style": ["爽文"], "role": ["男主"], "plot": ["身份反转"], "background": ["都市"]}


_GENRE_TAG_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "sci_fi_apocalypse": {"style": ("爽文", "烧脑", "快节奏"), "role": ("全能", "领主", "天才"), "plot": ("末世", "求生", "进化", "囤物资", "科技", "机甲"), "background": ("科幻", "末世", "未来世界", "星际")},
    "mystery_what_if": {"style": ("悬疑", "烧脑", "恐怖"), "role": ("侦探", "法医", "全能"), "plot": ("规则怪谈", "求生", "推理", "诡异流", "无限流"), "background": ("惊悚世界", "未来世界", "科幻")},
    "showbiz_romance": {"style": ("甜宠", "轻松", "爽文"), "role": ("明星", "顶流", "女主"), "plot": ("娱乐圈", "影视", "综艺", "恋爱"), "background": ("都市", "现代言情")},
    "workplace_romance": {"style": ("甜宠", "现实题材", "爽文"), "role": ("女主", "豪门总裁", "女总裁"), "plot": ("职场", "婚恋", "离婚后", "追妻火葬场", "闪婚"), "background": ("都市", "现代言情")},
    "republican_romance": {"style": ("正剧", "虐恋", "爽文"), "role": ("太子", "将军", "女主"), "plot": ("军婚", "谍战", "战争", "身份反转"), "background": ("民国", "年代")},
    "youth_sweet": {"style": ("青春", "甜宠", "轻松"), "role": ("学生", "学霸", "校草"), "plot": ("青梅竹马", "恋爱", "暗恋", "团宠"), "background": ("校园", "现代言情")},
    "ancient_romance_what_if": {"style": ("爽文", "甜宠", "宅斗"), "role": ("王爷", "太子", "主母", "女主"), "plot": ("穿书", "重生", "身份反转", "复仇"), "background": ("古代", "古代言情", "架空历史")},
}


def derive_work_tags(genre: str, text: str = "", tropes: list[str] | None = None) -> dict[str, list[str]]:
    """Select only catalogued tags from the genre and generated creative brief."""
    haystack = " ".join([genre, text, *(tropes or [])])
    hints = _GENRE_TAG_HINTS.get(genre)
    if hints is None:
        return default_work_tags(genre)
    defaults = default_work_tags(genre)
    selected: dict[str, list[str]] = {}
    for category in WORK_TAG_CATALOG:
        matches = [tag for tag in hints.get(category, ()) if tag in haystack and tag in WORK_TAG_CATALOG[category]]
        selected[category] = list(dict.fromkeys((matches + defaults.get(category, []))[:3]))
    return validate_work_tags(selected, allow_empty=False)
