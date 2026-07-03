from app.core.config import settings


def test_current_sreality_endpoints_point_at_live_v1_api():
    assert settings.sreality_api_base == "https://www.sreality.cz/api/v1/estates/search"
    assert settings.sreality_detail_base == "https://www.sreality.cz/api/v1/estates"
