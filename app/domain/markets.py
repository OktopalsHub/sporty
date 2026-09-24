from enum import StrEnum


class Market(StrEnum):
    OVER_2_5 = "over_2_5"
    BTTS = "btts"
    UNDER_2_5 = "under_2_5"
    UNDER_4_5 = "under_4_5"
    OVER_1_5 = "over_1_5"
    DOUBLE_CHANCE = "double_chance"
    MATCH_RESULT = "match_result"
    ALL = "all"
