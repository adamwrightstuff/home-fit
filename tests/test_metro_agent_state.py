from scripts.metro_agent import state_data as sd


def test_report_flags_states_with_no_2024_join_and_missing_files():
    il = sd.report("IL")          # IL precincts exist but 2024 results were never joined
    assert il["election"]["file"] and il["election"]["share_2024"] < sd.MIN_2024_SHARE and il["issues"]
    tx = sd.report("TX")
    assert tx["election"]["share_2024"] > 0.9 and tx["issues"] == [] and tx["crime_map_entries"] >= 1
    co = sd.report("CO")          # not built, not registered
    assert not co["election"]["file"] and "not registered" in co["issues"][0]


def test_build_runs_the_downloader_for_that_state():
    seen = []
    sd.build("co", runner=lambda cmd, **kw: seen.append(cmd) or 0, log=lambda s: None)
    assert seen and seen[0][-3:] == ["--states", "CO", "--build"]
