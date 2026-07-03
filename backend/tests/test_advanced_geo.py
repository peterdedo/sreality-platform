from app.analytics.advanced.geo import grid_cell, haversine_km


def test_haversine_zero_distance():
    assert haversine_km(50.08, 14.43, 50.08, 14.43) == 0


def test_haversine_known_approx_distance():
    # Prague (50.0755, 14.4378) to Brno (49.1951, 16.6068) is ~185km in reality
    d = haversine_km(50.0755, 14.4378, 49.1951, 16.6068)
    assert 180 < d < 190


def test_grid_cell_same_bin_for_nearby_points():
    id1, _, _ = grid_cell(50.0751, 14.4211)
    id2, _, _ = grid_cell(50.0755, 14.4215)
    assert id1 == id2


def test_grid_cell_different_bin_for_distant_points():
    id1, _, _ = grid_cell(50.0751, 14.4211)
    id2, _, _ = grid_cell(49.1951, 16.6068)
    assert id1 != id2


def test_grid_cell_center_is_within_step_of_input():
    _, center_lat, center_lon = grid_cell(50.0751, 14.4211, step_degrees=0.01)
    assert abs(center_lat - 50.0751) < 0.01
    assert abs(center_lon - 14.4211) < 0.01
