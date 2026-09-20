"""서비스키 없이 공개 파일의 실제 다운로드 계약을 확인하는 선택적 live 테스트."""

from __future__ import annotations

import os

import pytest

from kric import KricFileClient


pytestmark = pytest.mark.live


@pytest.mark.skipif(
    os.getenv("KRIC_LIVE_FILES") != "1",
    reason="KRIC_LIVE_FILES=1일 때만 공개 XLSX live 검증을 실행합니다.",
)
async def test_nationwide_station_file_downloads_without_service_key():
    async with KricFileClient(timeout=60) as client:
        rows = await client.get_nationwide_station_info()

    assert rows
    assert any(row.station_name and row.rail_operator_name for row in rows)
