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
        operations = await client.get_domestic_ship_operations(
            departure_port_id=ports[0].port_id, departure_date=date.today(), num_of_rows=1
        )
        if not operations or not operations[0].vessel_name:
            pytest.skip("live 조회에서 국내선박 운항을 찾지 못했습니다.")
        schedules = await client.get_coastal_ferry_schedules(
            schedule_date=date.today(), vessel_name=operations[0].vessel_name, num_of_rows=1
        )

    assert isinstance(schedules, tuple)
