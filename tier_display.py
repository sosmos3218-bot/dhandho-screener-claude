# -*- coding: utf-8 -*-
"""무료/유료 티어 표시 규칙 (대시보드·뉴스레터 공통)."""
from __future__ import annotations

import config


def free_preview_list(sorted_passes: list) -> list:
    """Dhandho 점수 내림차순 통과 종목에서 무료 미리보기 구간(기본 4~6위) 반환."""
    start = config.FREE_TIER_SKIP
    end = start + config.FREE_TIER_LIMIT
    return list(sorted_passes[start:end])


def free_preview_count(n_passing: int) -> int:
    return min(config.FREE_TIER_LIMIT, max(0, n_passing - config.FREE_TIER_SKIP))


def free_hidden_pass_count(n_passing: int) -> int:
    return max(0, n_passing - free_preview_count(n_passing))


def free_preview_rank_label() -> str:
    lo = config.FREE_TIER_SKIP + 1
    hi = config.FREE_TIER_SKIP + config.FREE_TIER_LIMIT
    return f"{lo}~{hi}위"


def free_preview_caption() -> str:
    return (
        f"무료 미리보기: 통과 종목 중 Dhandho 순 **{free_preview_rank_label()}** "
        f"({config.FREE_TIER_LIMIT}종목). **1~{config.FREE_TIER_SKIP}위·전체 순위**는 유료판."
    )


def free_preview_list_title() -> str:
    return f"미리보기 ({free_preview_rank_label()})"