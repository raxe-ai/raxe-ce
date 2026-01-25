"""Dashboard widgets - visual components."""

from raxe.cli.dashboard.widgets.alert_list import AlertListWidget
from raxe.cli.dashboard.widgets.ascii_box import AsciiBox
from raxe.cli.dashboard.widgets.latency_gauge import LatencyGaugeWidget
from raxe.cli.dashboard.widgets.sparkline import SparklineWidget
from raxe.cli.dashboard.widgets.status_panel import StatusPanelWidget
from raxe.cli.dashboard.widgets.threat_bar import ThreatBarWidget

__all__ = [
    "AlertListWidget",
    "AsciiBox",
    "LatencyGaugeWidget",
    "SparklineWidget",
    "StatusPanelWidget",
    "ThreatBarWidget",
]
