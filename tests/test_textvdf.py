"""Tests for the text KeyValues (config.vdf) reader/writer."""
from deckport import textvdf

SAMPLE = '''\
"InstallConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"CompatToolMapping"
\t\t\t\t{
\t\t\t\t\t"3858907385"
\t\t\t\t\t{
\t\t\t\t\t\t"name"\t\t"proton_experimental"
\t\t\t\t\t\t"config"\t\t""
\t\t\t\t\t\t"priority"\t\t"250"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
'''


def test_parse_structure():
    d = textvdf.loads(SAMPLE)
    mapping = d["InstallConfigStore"]["Software"]["Valve"]["Steam"]["CompatToolMapping"]
    assert mapping["3858907385"]["name"] == "proton_experimental"
    assert mapping["3858907385"]["priority"] == "250"
    assert mapping["3858907385"]["config"] == ""


def test_round_trip_reparses_equal():
    d = textvdf.loads(SAMPLE)
    assert textvdf.loads(textvdf.dumps(d)) == d  # semantic round-trip


def test_nested_and_values():
    d = {"Root": {"a": "1", "Sub": {"b": "two", "c": ""}}}
    out = textvdf.dumps(d)
    assert textvdf.loads(out) == d
    assert '"Root"' in out and out.count("{") == 2


def test_escaping_quotes_and_backslashes():
    d = {"k": 'a "quoted" \\path\\'}
    assert textvdf.loads(textvdf.dumps(d)) == d


def test_comments_and_whitespace_tolerated():
    text = '"A" {  // a comment\n  "x" "1"\n }\n'
    assert textvdf.loads(text) == {"A": {"x": "1"}}


def test_empty_input():
    assert textvdf.loads("") == {}
