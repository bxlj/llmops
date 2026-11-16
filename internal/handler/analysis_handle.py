"""
@Time    : 2026-11-15 22:20
@Author  : JiaChengJie
@File    : analysis_handle.py
"""
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from flask_login import current_user
from injector import inject

from internal.service.analysis_service import AnalysisService
from pkg.response import success_json


@inject
@dataclass
class AnalysisHandle:
    """统计分析控制器"""
    analysis_service: AnalysisService

    def get_app_analysis(self, app_id: UUID) -> dict[str, Any]:
        """获取指定应用的统计分析数据"""
        app_analysis = self.analysis_service.get_app_analysis(app_id, current_user)
        return success_json(app_analysis)
