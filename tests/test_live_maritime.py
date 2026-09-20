"""공공데이터포털 여객선 API의 최소 호출 계약을 확인하는 선택적 live 테스트."""

from __future__ import annotations

from datetime import date
import os

import pytest

from kric import DataGoKrMaritimeClient


pytestmark = pytest.mark.live


@pytest.mark.skipif(
    os.getenv("DATA_GO_KR_LIVE_MARITIME") != "1",
    reason="DATA_GO_KR_LIVE_MARITIME=1일 때만 공공데이터포털 여객선 live 검증을 실행합니다.",
)
async def test_maritime_api_accepts_the_configured_data_go_service_key():
    key = os.getenv("DATA_GO_KR_SERVICE_KEY")
    if not key:
        pytest.skip("DATA_GO_KR_SERVICE_KEY가 필요합니다.")

    async with DataGoKrMaritimeClient(key, timeout=60) as client:
        ports = await client.search_ports(name="인천", num_of_rows=1)
        if not ports or not ports[0].port_id:
            pytest.skip("live 조회에서 출항 항구를 찾지 못했습니다.")
        schedules = await client.get_coastal_ferry_schedules(
            schedule_date=date.today(),
            vessel_name=os.getenv("DATA_GO_KR_LIVE_MARITIME_VESSEL_NAME", "코리아프라이드"),
            num_of_rows=1,
        )

    if not schedules:
        pytest.skip("live 조회일에 검증 대상 여객선의 스케줄이 없습니다.")
    assert all(
        row.schedule_date and row.departure_time and row.vessel_code and row.vessel_name
        for row in schedules
    )
