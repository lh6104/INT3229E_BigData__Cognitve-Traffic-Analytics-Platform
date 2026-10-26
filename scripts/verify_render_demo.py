"""Read-only post-deployment HTTP smoke for the Render contest demo.

Usage: python scripts/verify_render_demo.py https://<dashboard>.onrender.com
No polling or traffic observations are generated.
"""
import json
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

EXPECTED = {
    "HN_HK_001", "HN_BD_001", "HN_CG_001", "HN_TX_001", "HN_RR3_001", "HN_VNG_001",
    "HCMC_D1_001", "HCMC_D3_001", "HCMC_BT_001", "HCMC_TD_001", "HCMC_Q7_001", "HCMC_CL_001",
}


def get(url):
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=180) as response:
        return response.status, response.read(), response.geturl()


def main(url):
    url = url.rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path:
        raise ValueError("Provide an HTTPS dashboard origin, without a path")
    status, body, final_url = get(f"{url}/")
    assert status == 200 and urlparse(final_url).scheme == "https", (status, final_url)
    assert b"<html" in body.lower(), "Dashboard root did not return HTML"
    print("PASS HTTPS dashboard root:", final_url)

    status, body, _ = get(f"{url}/api/system/health")
    health = json.loads(body)
    assert status == 200 and health["status"] == "healthy", health
    assert health["dependencies"]["postgres"] == "up", health
    print("PASS same-origin /api/system/health: healthy; PostgreSQL up")

    status, body, _ = get(f"{url}/api/monitoring/points")
    points = json.loads(body)
    ids = [point["road_id"] for point in points]
    assert status == 200 and len(points) == len(EXPECTED) and set(ids) == EXPECTED, ids
    for point in points:
        if point["event_time"] is None:
            assert point["status"] == "missing", point
            assert point["speed_kmh"] is None, point
    print(f"PASS 12 configured points; {sum(p['status'] == 'missing' for p in points)} unobserved")
    print("NEXT MANUAL: inspect browser Network requests and Render cold-start/service logs")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/verify_render_demo.py https://<dashboard>.onrender.com")
    main(sys.argv[1])
