from chatnec.metrics import Metrics


def test_inc_and_render():
    m = Metrics()
    m.inc("messages_received_total", "slack")
    m.inc("messages_received_total", "slack")
    m.inc("messages_received_total", "telegram")

    output = m.render_prometheus()

    assert 'chatnec_messages_received_total{platform="slack"} 2' in output
    assert 'chatnec_messages_received_total{platform="telegram"} 1' in output
    assert "# TYPE chatnec_messages_received_total counter" in output


def test_render_includes_all_known_counters_even_when_empty():
    m = Metrics()
    output = m.render_prometheus()

    assert "chatnec_replies_sent_total" in output
    assert "chatnec_agent_errors_total" in output
